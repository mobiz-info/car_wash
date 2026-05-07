from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.contrib import messages
from decimal import Decimal

from core.functions import get_auto_id, log_activity
from django.views.decorators.csrf import csrf_exempt
from client_management.api_views import get_user_from_token
from .models import Invoice, Receipt


@login_required
def invoice_list(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    invoices = Invoice.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).prefetch_related('items').order_by('-date', '-auto_id')

    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)

    search = request.GET.get('search', '').strip()
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )

    return render(request, 'invoice/list.html', {
        'invoices': invoices,
        'search': search,
        'title': 'Invoices'
    })


def api_list_invoices(request):
    """Mobile API: list invoices with optional date filters."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    invoices = Invoice.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).prefetch_related('items').order_by('-date', '-auto_id')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    if from_date:
        invoices = invoices.filter(date__gte=from_date)
    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    results = []
    for inv in invoices:
        results.append({
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'date': str(inv.date),
            'subtotal': str(inv.subtotal),
            'discount': str(inv.discount),
            'tax_amount': str(inv.tax_amount),
            'total': str(inv.total),
            'amount_collected': str(inv.amount_collected),
            'customer': {
                'name': inv.customer.name,
                'phone': inv.customer.phone,
            },
            'vehicle': {
                'number': inv.vehicle.vehicle_number,
                'model': inv.vehicle.vehicle_type_model.name if inv.vehicle.vehicle_type_model else '',
                'type': inv.vehicle.vehicle_type_model.vehicle_type.name if inv.vehicle.vehicle_type_model and inv.vehicle.vehicle_type_model.vehicle_type else '',
            },
            'branch': inv.branch.name if inv.branch else '',
            'services': [
                {'name': item.service_name, 'rate': str(item.rate)}
                for item in inv.items.all()
            ],
        })

    return JsonResponse({'success': True, 'invoices': results})



@login_required
def sales_report(request):

    invoices = Invoice.objects.filter(is_deleted=False).order_by('-date')

    # Filters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch = request.GET.get('branch')

    if from_date:
        invoices = invoices.filter(date__gte=from_date)

    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    if branch:
        invoices = invoices.filter(branch_id=branch)

    # Balance Calculation
    invoices = invoices.annotate(
        balance=ExpressionWrapper(
            F('total') - F('amount_collected'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )

    # Totals
    total_amount = invoices.aggregate(
        total=Sum('total')
    )['total'] or 0

    total_collection = invoices.aggregate(
        collected=Sum('amount_collected')
    )['collected'] or 0

    total_balance = total_amount - total_collection

    context = {
        'invoices': invoices,
        'total_amount': total_amount,
        'total_collection': total_collection,
        'total_balance': total_balance,
    }

    return render(request, 'reports/sales_report.html', context)


@login_required
def invoice_receipt(request, pk):

    invoice = get_object_or_404(
        Invoice.objects.prefetch_related('items'),
        pk=pk,
        is_deleted=False
    )

    balance = invoice.total - invoice.amount_collected

    context = {
        'invoice': invoice,
        'balance': balance,
    }

    return render(request, 'invoice/invoice_receipt.html', context)


@login_required
def receipt_list(request):

    receipts = Receipt.objects.filter(
        is_deleted=False
    ).select_related(
        'invoice',
        'invoice__customer'
    ).order_by('-created_at')

    search = request.GET.get('search')
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if search:
        receipts = receipts.filter(
            Q(receipt_number__icontains=search) |
            Q(invoice__invoice_number__icontains=search) |
            Q(invoice__customer__name__icontains=search)
        )

    if from_date:
        receipts = receipts.filter(created_at__date__gte=from_date)

    if to_date:
        receipts = receipts.filter(created_at__date__lte=to_date)

    context = {
        'receipts': receipts,
        'search': search,
    }

    return render(request, 'receipt/list.html', context)


@login_required
def receipt_create(request, invoice_id=None):

    invoices = Invoice.objects.filter(
        is_deleted=False
    ).order_by('-id')

    selected_invoice = None

    if invoice_id:
        selected_invoice = get_object_or_404(
            Invoice,
            pk=invoice_id,
            is_deleted=False
        )

    if request.method == 'POST':

        invoice = get_object_or_404(
            Invoice,
            pk=request.POST.get('invoice')
        )

        amount = Decimal(request.POST.get('amount') or 0)

        payment_mode = request.POST.get('payment_mode')
        remarks = request.POST.get('remarks')

        cheque_no = request.POST.get('cheque_no')
        cheque_date = request.POST.get('cheque_date')
        bank_name = request.POST.get('bank_name')

        # Generate Receipt Number
        last_receipt = Receipt.objects.order_by('-id').first()

        if last_receipt:
            try:
                last_no = int(last_receipt.receipt_number.split('-')[-1])
            except:
                last_no = last_receipt.id
        else:
            last_no = 0

        receipt_number = f"RCPT-{str(last_no + 1).zfill(5)}"

        # Create Receipt
        receipt = Receipt.objects.create(
            auto_id=get_auto_id(Receipt),
            receipt_number=receipt_number,
            invoice=invoice,
            amount=amount,
            payment_mode=payment_mode,
            remarks=remarks,
            cheque_no=cheque_no,
            cheque_date=cheque_date if cheque_date else None,
            bank_name=bank_name,
        )

        # Update Invoice Collection
        invoice.amount_collected += amount
        invoice.save()

        messages.success(
            request,
            "Receipt created successfully."
        )

        return redirect('receipt_list')

    context = {
        'invoices': invoices,
        'selected_invoice': selected_invoice,
        'title': 'Create Receipt',
    }

    return render(request, 'receipt/create.html', context)