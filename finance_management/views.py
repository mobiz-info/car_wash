from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.views.decorators.csrf import csrf_exempt
from core.functions import get_auto_id, log_activity
from client_management.api_views import get_user_from_token
from .models import Invoice, Receipt
from booking_management.models import Booking
from client_management.models import Branch
from service_management.models import ServiceType
from decimal import Decimal


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


@login_required
def outstanding_list(request):
    """Show all invoices where amount_collected < total (customer has balance due)."""
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    # Only invoices with outstanding balance
    invoices = Invoice.objects.filter(
        is_deleted=False,
    ).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).order_by('customer__name', '-date')

    # Scope by role
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)

    # Filter only outstanding (balance > 0)
    invoices = invoices.filter(amount_collected__lt=F('total'))

    # Search
    search = request.GET.get('search', '').strip()
    if search:
        invoices = invoices.filter(
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(invoice_number__icontains=search)
        )

    # Annotate outstanding on each invoice
    invoice_list_data = []
    total_outstanding = Decimal('0.00')
    for inv in invoices:
        outstanding = inv.total - inv.amount_collected
        total_outstanding += outstanding
        invoice_list_data.append({
            'invoice': inv,
            'outstanding': outstanding,
        })

    # Group by customer for summary
    from collections import defaultdict
    customer_summary = defaultdict(lambda: {'customer': None, 'total_outstanding': Decimal('0'), 'invoices': []})
    for item in invoice_list_data:
        cid = str(item['invoice'].customer.id)
        customer_summary[cid]['customer'] = item['invoice'].customer
        customer_summary[cid]['total_outstanding'] += item['outstanding']
        customer_summary[cid]['invoices'].append(item)

    return render(request, 'invoice/outstanding.html', {
        'customer_summary': list(customer_summary.values()),
        'invoice_list': invoice_list_data,
        'total_outstanding': total_outstanding,
        'search': search,
        'title': 'Customer Outstanding',
    })


@login_required
def collect_payment(request, invoice_id):
    """Collect partial or full payment for an outstanding invoice."""
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    invoice = get_object_or_404(Invoice, id=invoice_id, is_deleted=False)

    # Scope check
    if role == 'COMPANY_ADMIN':
        if not invoice.branch.company == user.profile.company:
            messages.error(request, "Access denied.")
            return redirect('outstanding_list')
    elif role == 'BRANCH_ADMIN':
        if invoice.branch != user.managed_branch:
            messages.error(request, "Access denied.")
            return redirect('outstanding_list')

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0').strip()
        try:
            amount = Decimal(amount_str)
            outstanding = invoice.total - invoice.amount_collected
            if amount <= 0:
                messages.error(request, "Amount must be greater than 0.")
            elif amount > outstanding:
                currency = invoice.branch.company.country.currency_symbol if invoice.branch.company.country else '₹'
                messages.error(request, f"Amount {currency}{amount} exceeds outstanding {currency}{outstanding}.")
            else:
                invoice.amount_collected += amount
                invoice.save()
                remaining = invoice.total - invoice.amount_collected
                if remaining == 0:
                    messages.success(request, f"Full payment collected for Invoice #{invoice.invoice_number}. ✓ Fully settled.")
                else:
                    currency = invoice.branch.company.country.currency_symbol if invoice.branch.company.country else '₹'
                    messages.success(request, f"{currency}{amount} collected. Remaining outstanding: {currency}{remaining}.")
                return redirect('outstanding_list')
        except Exception as e:
            messages.error(request, f"Invalid amount: {e}")

    return redirect('outstanding_list')


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

    # COMPANY FILTER

    user = request.user

    role = None

    if hasattr(user, 'profile') and user.profile.role:
        role = user.profile.role.name

    if role == 'COMPANY_ADMIN':

        if hasattr(user.profile, 'company') and user.profile.company:

            company = user.profile.company

            invoices = invoices.filter(
                branch__company=company
            )

            branches = Branch.objects.filter(
                company=company,
                is_deleted=False
            )

        else:

            branches = Branch.objects.filter(
                is_deleted=False
            )

    else:

        branches = Branch.objects.filter(
            is_deleted=False
        )
    print("branches",branches)
    
    # Filters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    invoice_number = request.GET.get('invoice_number')

    if from_date:
        invoices = invoices.filter(date__gte=from_date)

    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    if invoice_number:
        invoices = invoices.filter(invoice_number=invoice_number)

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

@csrf_exempt
def api_outstanding_list(request):
    """Mobile API: list all invoices with outstanding balance (amount_collected < total)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    invoices = Invoice.objects.filter(
        is_deleted=False,
    ).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).filter(amount_collected__lt=F('total')).order_by('customer__name', '-date')

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
    total_outstanding = Decimal('0.00')
    for inv in invoices:
        outstanding = inv.total - inv.amount_collected
        total_outstanding += outstanding
        results.append({
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'date': str(inv.date),
            'total': str(inv.total),
            'amount_collected': str(inv.amount_collected),
            'outstanding': str(outstanding),
            'customer': {
                'name': inv.customer.name,
                'phone': inv.customer.phone,
            },
            'vehicle': {
                'number': inv.vehicle.vehicle_number,
                'model': inv.vehicle.vehicle_type_model.name if inv.vehicle.vehicle_type_model else '',
            },
            'branch': inv.branch.name if inv.branch else '',
        })

    return JsonResponse({
        'success': True,
        'invoices': results,
        'total_outstanding': str(total_outstanding),
        'count': len(results),
    })


@csrf_exempt
def api_collect_payment(request):
    """Mobile API: collect partial or full payment for an outstanding invoice."""
    import json
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id')
        amount = Decimal(str(data.get('amount', 0)))

        invoice = Invoice.objects.get(id=invoice_id, is_deleted=False)

        # Scope check
        role = user.profile.role.name if user.profile.role else None
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            if invoice.branch != user.managed_branch:
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
        elif role == 'COMPANY_ADMIN' and user.profile.company:
            if invoice.branch.company != user.profile.company:
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

        outstanding = invoice.total - invoice.amount_collected
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Amount must be greater than 0'}, status=400)
        if amount > outstanding:
            currency = invoice.branch.company.country.currency_symbol if invoice.branch.company.country else '₹'
            return JsonResponse({'success': False, 'message': f'Amount exceeds outstanding balance of {currency}{outstanding}'}, status=400)

        invoice.amount_collected += amount
        invoice.save()

        receipt_auto_id = get_auto_id(Receipt)
        receipt = Receipt.objects.create(
            auto_id=receipt_auto_id,
            creator=user,
            receipt_number=f"RCPT-{str(receipt_auto_id).zfill(5)}",
            invoice=invoice,
            amount=amount,
            payment_mode=data.get('payment_mode') or 'cash',
            remarks=data.get('remarks') or 'Outstanding collection',
        )

        remaining = invoice.total - invoice.amount_collected
        return JsonResponse({
            'success': True,
            'message': 'Payment collected successfully',
            'new_collected': str(invoice.amount_collected),
            'remaining_outstanding': str(remaining),
            'fully_settled': remaining == 0,
            'receipt': {
                'id': str(receipt.id),
                'receipt_number': receipt.receipt_number,
                'amount': str(receipt.amount),
            },
        })

    except Invoice.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def api_receipt_list(request):
    """Mobile API: list receipts created from outstanding collections."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    receipts = Receipt.objects.filter(is_deleted=False).select_related(
        'invoice',
        'invoice__customer',
        'invoice__vehicle',
        'invoice__vehicle__vehicle_type_model',
        'invoice__branch',
    ).order_by('-created_at', '-auto_id')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        receipts = receipts.filter(invoice__branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        receipts = receipts.filter(invoice__branch__company=user.profile.company)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    if from_date:
        receipts = receipts.filter(created_at__date__gte=from_date)
    if to_date:
        receipts = receipts.filter(created_at__date__lte=to_date)

    results = []
    total_collected = Decimal('0.00')
    for receipt in receipts:
        invoice = receipt.invoice
        balance = invoice.total - invoice.amount_collected
        total_collected += receipt.amount
        results.append({
            'id': str(receipt.id),
            'receipt_number': receipt.receipt_number,
            'date': receipt.created_at.date().isoformat(),
            'time': receipt.created_at.strftime('%I:%M %p'),
            'amount': str(receipt.amount),
            'payment_mode': receipt.payment_mode,
            'remarks': receipt.remarks or '',
            'invoice': {
                'id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'date': str(invoice.date),
                'total': str(invoice.total),
                'amount_collected': str(invoice.amount_collected),
                'balance': str(balance),
            },
            'customer': {
                'name': invoice.customer.name,
                'phone': invoice.customer.phone,
            },
            'vehicle': {
                'number': invoice.vehicle.vehicle_number,
                'model': invoice.vehicle.vehicle_type_model.name if invoice.vehicle.vehicle_type_model else '',
            },
            'branch': invoice.branch.name if invoice.branch else '',
        })

    return JsonResponse({
        'success': True,
        'receipts': results,
        'total_collected': str(total_collected),
        'count': len(results),
    })

@login_required
def job_report(request):

    from django.db.models import Sum, Count, Q
    from finance_management.models import Invoice
   

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')
    search = request.GET.get('search')

    invoices = Invoice.objects.filter(
        is_deleted=False
    ).select_related(
        'customer',
        'vehicle',
        'branch'
    ).prefetch_related(
        'items'
    )

    # COMPANY FILTER

    user = request.user

    role = None

    if hasattr(user, 'profile') and user.profile.role:
        role = user.profile.role.name

    if role == 'COMPANY_ADMIN':

        if hasattr(user.profile, 'company') and user.profile.company:

            company = user.profile.company

            invoices = invoices.filter(
                branch__company=company
            )

            branches = Branch.objects.filter(
                company=company,
                is_deleted=False
            )

        else:

            branches = Branch.objects.filter(
                is_deleted=False
            )

    else:

        branches = Branch.objects.filter(
            is_deleted=False
        )

    # SEARCH

    if search:

        invoices = invoices.filter(

            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)

        )

    # DATE FILTER

    if from_date:

        invoices = invoices.filter(
            date__gte=from_date
        )

    if to_date:

        invoices = invoices.filter(
            date__lte=to_date
        )

    # BRANCH FILTER

    if branch_id:

        invoices = invoices.filter(
            branch_id=branch_id
        )

    invoices = invoices.order_by(
        '-date',
        '-id'
    )
    for invoice in invoices:
        invoice.balance = invoice.total - invoice.amount_collected

    # SUMMARY

    summary = invoices.aggregate(

        total_jobs=Count('id'),

        total_revenue=Sum('total'),

        total_collected=Sum('amount_collected'),

        total_balance=Sum(
            ExpressionWrapper(
                F('total') - F('amount_collected'),
                output_field=DecimalField()
            )
        ),


        total_discount=Sum('discount'),

    )

    context = {

        'invoices': invoices,

        'branches': branches,

        'from_date': from_date,
        'to_date': to_date,

        'branch_id': branch_id,
        'search': search,

        'total_jobs': summary['total_jobs'] or 0,

        'total_revenue': summary['total_revenue'] or 0,

        'total_collected': summary['total_collected'] or 0,

        'total_balance': summary['total_balance'] or 0,

        'total_discount': summary['total_discount'] or 0,

    }

    return render(
        request,
        'reports/job_report.html',
        context
    )