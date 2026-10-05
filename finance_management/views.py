from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.core.paginator import Paginator
from datetime import datetime
from django.utils import timezone
from django.db.models import DecimalField, Value
from django.db.models.functions import Coalesce, TruncDate
from django.template.loader import render_to_string
from django.http import HttpResponse

import sys
import os
# Ensure macOS Homebrew libraries (like libgobject for WeasyPrint) are searchable
if sys.platform == 'darwin':
    os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = '/opt/homebrew/lib:' + os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')

from weasyprint import HTML


from core.functions import get_auto_id, log_activity
from client_management.api_views import get_user_from_token
from .models import Invoice, Receipt, InvoiceItem
from booking_management.models import Booking
from client_management.models import Branch
from service_management.models import ServiceType
from master.models import ExpenseEntry, ExpenseHead


@login_required
def invoice_list(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    today = timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')

    from_date_param = request.GET.get('from_date') if 'from_date' in request.GET else request.GET.get('fromdate')
    to_date_param = request.GET.get('to_date') if 'to_date' in request.GET else request.GET.get('todate')

    if from_date_param is None:
        from_date = today_str
    else:
        from_date = from_date_param.strip()

    if to_date_param is None:
        to_date = today_str
    else:
        to_date = to_date_param.strip()

    invoices = Invoice.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).prefetch_related('items').order_by('-date', '-auto_id')

    branches = None
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)
        branches = Branch.objects.filter(company=user.profile.company, is_deleted=False)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)

    branch_id = request.GET.get('branch_id') or request.GET.get('branch')
    if branch_id:
        invoices = invoices.filter(branch_id=branch_id)

    # Filter by date range (defaults to today)
    if from_date:
        try:
            parsed_from = datetime.strptime(from_date, '%Y-%m-%d').date()
            invoices = invoices.filter(date__gte=parsed_from)
        except ValueError:
            invoices = invoices.filter(date__gte=from_date)

    if to_date:
        try:
            parsed_to = datetime.strptime(to_date, '%Y-%m-%d').date()
            invoices = invoices.filter(date__lte=parsed_to)
        except ValueError:
            invoices = invoices.filter(date__lte=to_date)

    search = request.GET.get('search', '').strip()
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )

    payment_mode = request.GET.get('payment_mode', '').strip()
    if payment_mode:
        invoices = invoices.filter(receipts__payment_mode=payment_mode).distinct()

    totals = invoices.aggregate(
        total_subtotal=Sum('subtotal'),
        total_discount=Sum('discount'),
        total_tax=Sum('tax_amount'),
        total_total=Sum('total'),
        total_collected=Sum('amount_collected')
    )
    for key in totals:
        if totals[key] is None:
            totals[key] = Decimal('0.00')

    return render(request, 'invoice/list.html', {
        'invoices': invoices,
        'search': search,
        'payment_mode': payment_mode,
        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'branches': branches,
        'title': 'Invoices',
        'totals': totals
    })


@login_required
def outstanding_list(request):
    """Show all invoices where amount_collected < total (customer has balance due)."""
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    # Only invoices with outstanding balance
    invoices = Invoice.objects.filter(
        is_deleted=False,
        customer__is_deleted=False,
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
    ).prefetch_related('items', 'items__service_detail', 'reminder_plans').order_by('-date', '-auto_id')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)

    invoice_id = request.GET.get('invoice_id') or request.GET.get('id')
    if invoice_id:
        invoices = invoices.filter(id=invoice_id)
    else:
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        if from_date:
            invoices = invoices.filter(date__gte=from_date)
        if to_date:
            invoices = invoices.filter(date__lte=to_date)

    payment_mode = request.GET.get('payment_mode')
    if payment_mode:
        invoices = invoices.filter(receipts__payment_mode=payment_mode).distinct()

    results = []
    for inv in invoices:
        services_data = []
        extras_data = []
        for item in inv.items.all():
            if item.stock_item:
                continue
            is_ext = False
            ext_id = None
            if hasattr(item, 'extra') and item.extra:
                is_ext = True
                ext_id = str(item.extra.id)
            elif not item.service and not item.stock_item and item.service_name:
                from client_management.models import Extra
                from django.db.models import Q
                clean_name = item.service_name.strip()
                base_name = clean_name.split('(')[0].strip()
                company_obj = inv.branch.company if inv.branch else None
                extra_match = Extra.objects.filter(
                    Q(company=company_obj) | Q(company__isnull=True),
                    name__iexact=base_name,
                    is_deleted=False
                ).first()
                if extra_match:
                    is_ext = True
                    ext_id = str(extra_match.id)

            s_item = {
                'id': ext_id if is_ext else (str(item.service.id) if item.service else str(item.id)),
                'service_id': str(item.service.id) if item.service else None,
                'extra_id': ext_id,
                'is_extra': is_ext,
                'name': item.service_name,
                'rate': str(item.rate),
                'discount': str(item.discount),
                'qty': float(item.qty) if item.qty else 1.0,
                'net_taxable_amount': str(item.net_taxable_amount) if item.net_taxable_amount else str(item.rate),
                'service_category': item.service_detail.service_category if hasattr(item, 'service_detail') and item.service_detail else '',
                'smoke_test_period_months': item.service_detail.smoke_test_period_months if hasattr(item, 'service_detail') and item.service_detail else None,
                'warranty_value': item.service_detail.warranty_value if hasattr(item, 'service_detail') and item.service_detail else None,
                'warranty_unit': item.service_detail.warranty_unit if hasattr(item, 'service_detail') and item.service_detail else None,
                'service_detail': {
                    'service_category': item.service_detail.service_category,
                    'smoke_test_period_months': item.service_detail.smoke_test_period_months,
                    'warranty_value': item.service_detail.warranty_value,
                    'warranty_unit': item.service_detail.warranty_unit,
                    'odometer_at_service': item.service_detail.odometer_at_service,
                    'next_oil_change_km': item.service_detail.next_oil_change_km,
                    'next_tyre_change_km': item.service_detail.next_tyre_change_km,
                    'next_alignment_km': item.service_detail.next_alignment_km,
                    'alignment_done': item.service_detail.alignment_done,
                    'balancing_done': item.service_detail.balancing_done,
                    'alignment_notes': item.service_detail.alignment_notes,
                } if hasattr(item, 'service_detail') and item.service_detail else None,
            }
            services_data.append(s_item)
            if is_ext:
                extras_data.append(s_item)

        reminders_data = []
        custom_reminders_data = []
        try:
            sorted_plans = sorted(
                [rp for rp in inv.reminder_plans.all() if not rp.is_deleted],
                key=lambda x: (x.reminder_no, x.scheduled_date or datetime.min.date())
            )
            for rp in sorted_plans:
                days_after = (rp.scheduled_date - inv.date).days if (rp.scheduled_date and inv.date) else 0
                is_custom = (rp.template_name or '') not in ('insurancereminder', 'smoketest')
                rem_dict = {
                    'id': str(rp.id),
                    'days_after': days_after,
                    'days': days_after,
                    'scheduled_date': str(rp.scheduled_date) if rp.scheduled_date else '',
                    'template_name': rp.template_name or '',
                    'reminder_no': rp.reminder_no,
                    'is_sent': rp.is_sent,
                    'is_custom': is_custom,
                }
                reminders_data.append(rem_dict)
                if is_custom:
                    custom_reminders_data.append(rem_dict)
        except Exception:
            pass

        results.append({
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'date': str(inv.date),
            'subtotal': str(inv.subtotal),
            'discount': str(inv.discount),
            'tax_amount': str(inv.tax_amount),
            'total': str(inv.total),
            'amount_collected': str(inv.amount_collected),
            'invoice_type': inv.invoice_type,
            'remarks': inv.remarks or '',
            'show_warranty_in_pdf': inv.show_warranty_in_pdf,
            'customer': {
                'id': str(inv.customer.id) if inv.customer else '',
                'name': inv.customer.name if inv.customer else '',
                'phone': inv.customer.phone if inv.customer else '',
            },
            'vehicle': {
                'id': str(inv.vehicle.id) if inv.vehicle else '',
                'number': inv.vehicle.vehicle_number if inv.vehicle else '',
                'model': inv.vehicle.vehicle_type_model.name if inv.vehicle and inv.vehicle.vehicle_type_model else '',
                'type': inv.vehicle.vehicle_type_model.vehicle_type.name if inv.vehicle and inv.vehicle.vehicle_type_model and inv.vehicle.vehicle_type_model.vehicle_type else '',
            },
            'branch': inv.branch.name if inv.branch else '',
            'branch_logo': request.build_absolute_uri(inv.branch.logo.url) if inv.branch and inv.branch.logo else '',
            'company_logo': request.build_absolute_uri(inv.branch.company.logo_color.url) if inv.branch and inv.branch.company and inv.branch.company.logo_color else '',
            'company_seal': request.build_absolute_uri(inv.branch.company.company_seal.url) if inv.branch and inv.branch.company and getattr(inv.branch.company, 'company_seal', None) else '',
            'services': services_data,
            'extras': extras_data,
            'trading_items': [
                {
                    'id': str(item.stock_item.id),
                    'item_name': item.service_name,
                    'qty': float(item.qty) if item.qty else 1.0,
                    'rate': str(item.rate),
                    'discount': str(item.discount),
                    'is_operational': item.is_operational,
                    'remarks': item.remarks or '',
                }
                for item in inv.items.all() if item.stock_item
            ],
            'assigned_staffs': [
                {'id': str(st.id), 'name': st.name} for st in inv.assigned_staffs.all()
            ],
            'reminders': reminders_data,
            'custom_reminders': custom_reminders_data,
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

    elif role == 'BRANCH_ADMIN':
        if hasattr(user, 'managed_branch') and user.managed_branch:
            invoices = invoices.filter(branch=user.managed_branch)
        branches = None
    else:
        branches = Branch.objects.filter(is_deleted=False)
    print("branches",branches)
    
    # Filters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    invoice_number = request.GET.get('invoice_number')
    payment_mode = request.GET.get('payment_mode', '').strip()

    if from_date:
        invoices = invoices.filter(date__gte=from_date)

    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    if invoice_number:
        invoices = invoices.filter(invoice_number=invoice_number)

    if payment_mode:
        invoices = invoices.filter(receipts__payment_mode=payment_mode).distinct()

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
        'invoice_number': invoice_number,
        'payment_mode': payment_mode,
        'branches': branches,
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

    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        receipts = receipts.filter(invoice__branch__company=user.profile.company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        receipts = receipts.filter(invoice__branch=user.managed_branch)

    search = request.GET.get('search')
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    payment_mode = request.GET.get('payment_mode', '').strip()

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

    if payment_mode:
        receipts = receipts.filter(payment_mode=payment_mode)

    context = {
        'receipts': receipts,
        'search': search,
        'payment_mode': payment_mode,
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
        customer__is_deleted=False,
    ).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).filter(amount_collected__lt=F('total')).order_by('customer__name', '-date')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)
        branch_id = request.GET.get('branch_id')
        if branch_id:
            invoices = invoices.filter(branch_id=branch_id)

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
                'id': str(inv.customer.id),
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
        branch_id = request.GET.get('branch_id')
        if branch_id:
            receipts = receipts.filter(invoice__branch_id=branch_id)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    payment_mode = request.GET.get('payment_mode')
    if from_date:
        receipts = receipts.filter(created_at__date__gte=from_date)
    if to_date:
        receipts = receipts.filter(created_at__date__lte=to_date)
    if payment_mode:
        receipts = receipts.filter(payment_mode=payment_mode)

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


@csrf_exempt
def api_delete_invoice(request):
    """
    Mobile + Web API: Soft-delete an invoice.
    - Marks invoice as is_deleted=True
    - Soft-deletes all associated Receipts
    - Resets invoice.amount_collected to 0
    """
    import json
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id') or data.get('id')
        if not invoice_id:
            return JsonResponse({'success': False, 'message': 'invoice_id is required'}, status=400)

        invoice = Invoice.objects.get(id=invoice_id, is_deleted=False)

        # Scope check
        role = user.profile.role.name if user.profile.role else None
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            if invoice.branch != user.managed_branch:
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
        elif role == 'COMPANY_ADMIN' and user.profile.company:
            if invoice.branch.company != user.profile.company:
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

        # Soft-delete all receipts linked to this invoice
        Receipt.objects.filter(invoice=invoice, is_deleted=False).update(is_deleted=True)

        # Reset collected amount and soft-delete invoice
        invoice.amount_collected = Decimal('0.00')
        invoice.is_deleted = True
        invoice.updater = user
        invoice.save()

        return JsonResponse({'success': True, 'message': 'Invoice deleted successfully'})

    except Invoice.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_delete_receipt(request):
    """
    Mobile + Web API: Soft-delete a receipt and restore outstanding balance.
    - Marks receipt as is_deleted=True
    - Decrements invoice.amount_collected by the receipt amount
    """
    import json
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        receipt_id = data.get('receipt_id') or data.get('id')
        if not receipt_id:
            return JsonResponse({'success': False, 'message': 'receipt_id is required'}, status=400)

        receipt = Receipt.objects.select_related('invoice').get(id=receipt_id, is_deleted=False)
        invoice = receipt.invoice

        # Scope check
        role = user.profile.role.name if user.profile.role else None
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            if invoice.branch != user.managed_branch:
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
        elif role == 'COMPANY_ADMIN' and user.profile.company:
            if invoice.branch.company != user.profile.company:
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

        receipt_amount = receipt.amount

        # Soft-delete receipt
        receipt.is_deleted = True
        receipt.save()

        # Restore the outstanding balance by decrementing amount_collected
        invoice.amount_collected = max(Decimal('0.00'), invoice.amount_collected - receipt_amount)
        invoice.save()

        new_outstanding = invoice.total - invoice.amount_collected
        return JsonResponse({
            'success': True,
            'message': 'Receipt deleted. Amount restored to outstanding.',
            'new_outstanding': str(new_outstanding),
            'new_amount_collected': str(invoice.amount_collected),
        })

    except Receipt.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Receipt not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_customer_outstanding_list(request):
    """Mobile API: list all customers who have outstanding invoices."""

    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    invoices = Invoice.objects.filter(
        is_deleted=False,
        customer__is_deleted=False,
    ).select_related(
        'customer', 'branch'
    ).filter(amount_collected__lt=F('total')).order_by('date', 'auto_id')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        invoices = invoices.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        invoices = invoices.filter(branch__company=user.profile.company)
        branch_id = request.GET.get('branch_id')
        if branch_id:
            invoices = invoices.filter(branch_id=branch_id)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    if from_date:
        invoices = invoices.filter(date__gte=from_date)
    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    from collections import defaultdict
    customer_data = defaultdict(lambda: {
        'customer_id': '',
        'customer_name': '',
        'customer_phone': '',
        'total_outstanding': Decimal('0.00'),
        'invoices_count': 0
    })

    for inv in invoices:
        cid = str(inv.customer.id)
        outstanding = inv.total - inv.amount_collected
        customer_data[cid]['customer_id'] = cid
        customer_data[cid]['customer_name'] = inv.customer.name
        customer_data[cid]['customer_phone'] = inv.customer.phone
        customer_data[cid]['total_outstanding'] += outstanding
        customer_data[cid]['invoices_count'] += 1

    results = []
    total_outstanding_sum = Decimal('0.00')
    for item in customer_data.values():
        total_outstanding_sum += item['total_outstanding']
        results.append({
            'customer_id': item['customer_id'],
            'customer_name': item['customer_name'],
            'customer_phone': item['customer_phone'],
            'total_outstanding': str(item['total_outstanding']),
            'invoices_count': item['invoices_count'],
        })

    # Sort by customer name
    results.sort(key=lambda x: x['customer_name'].lower())

    return JsonResponse({
        'success': True,
        'customers': results,
        'total_outstanding': str(total_outstanding_sum),
        'count': len(results),
    })


@csrf_exempt
def api_collect_customer_outstanding(request):
    """Mobile API: collect bulk payment and apply it sequentially to a customer's oldest outstanding invoices."""
    import json
    from django.db import transaction
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        amount = Decimal(str(data.get('amount', 0)))
        payment_mode = data.get('payment_mode') or 'cash'
        remarks = data.get('remarks') or 'Bulk outstanding collection'

        if not customer_id:
            return JsonResponse({'success': False, 'message': 'customer_id is required'}, status=400)
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Amount must be greater than 0'}, status=400)

        with transaction.atomic():
            invoices = Invoice.objects.select_for_update().filter(
                customer_id=customer_id,
                is_deleted=False,
                amount_collected__lt=F('total')
            ).order_by('date', 'auto_id')

            role = user.profile.role.name if user.profile.role else None
            if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
                invoices = invoices.filter(branch=user.managed_branch)
            elif role == 'COMPANY_ADMIN' and user.profile.company:
                invoices = invoices.filter(branch__company=user.profile.company)

            total_outstanding = sum(inv.total - inv.amount_collected for inv in invoices)
            if amount > total_outstanding:
                return JsonResponse({
                    'success': False,
                    'message': f'Collection amount exceeds total outstanding balance ({total_outstanding})'
                }, status=400)

            amount_left = amount
            receipts_created = []

            for inv in invoices:
                if amount_left <= 0:
                    break

                inv_outstanding = inv.total - inv.amount_collected
                payment_to_apply = min(amount_left, inv_outstanding)

                inv.amount_collected += payment_to_apply
                inv.save()

                receipt_auto_id = get_auto_id(Receipt)
                rcpt = Receipt.objects.create(
                    auto_id=receipt_auto_id,
                    creator=user,
                    receipt_number=f"RCPT-{str(receipt_auto_id).zfill(5)}",
                    invoice=inv,
                    amount=payment_to_apply,
                    payment_mode=payment_mode,
                    remarks=remarks,
                )

                receipts_created.append({
                    'id': str(rcpt.id),
                    'receipt_number': rcpt.receipt_number,
                    'invoice_number': inv.invoice_number,
                    'amount_applied': str(payment_to_apply),
                })

                amount_left -= payment_to_apply

            return JsonResponse({
                'success': True,
                'message': 'Bulk payment applied sequentially successfully',
                'amount_collected': str(amount),
                'receipts': receipts_created,
            })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def job_report(request):

    from django.db.models import Sum, Count, Q, ExpressionWrapper, F, DecimalField
    from finance_management.models import Invoice
    from service_management.models import ServiceType, BranchServiceCategory

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')
    category_param = request.GET.get('category')
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
    elif role == 'BRANCH_ADMIN':
        if hasattr(user, 'managed_branch') and user.managed_branch:
            invoices = invoices.filter(branch=user.managed_branch)
        branches = None
    else:
        branches = Branch.objects.filter(is_deleted=False)

    # Fetch Enabled Categories for Category Filter
    all_types = ServiceType.objects.filter(is_deleted=False).order_by('name')

    target_branch_id = branch_id
    if not target_branch_id and role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        target_branch_id = user.managed_branch.id

    if target_branch_id:
        bsc_qs = BranchServiceCategory.objects.filter(branch_id=target_branch_id, is_deleted=False)
        if bsc_qs.filter(is_enabled=True).exists():
            enabled_slugs = set(bsc_qs.filter(is_enabled=True).values_list('service_type__slug', flat=True))
            categories = [st for st in all_types if st.slug and st.slug in enabled_slugs]
        else:
            disabled_slugs = set(bsc_qs.filter(is_enabled=False).values_list('service_type__slug', flat=True))
            categories = [st for st in all_types if not (st.slug and st.slug in disabled_slugs)]
    else:
        company_obj = None
        if role == 'COMPANY_ADMIN' and hasattr(user, 'profile') and hasattr(user.profile, 'company') and user.profile.company:
            company_obj = user.profile.company

        if company_obj:
            bsc_qs = BranchServiceCategory.objects.filter(branch__company=company_obj, is_deleted=False)
            if bsc_qs.filter(is_enabled=True).exists():
                enabled_slugs = set(bsc_qs.filter(is_enabled=True).values_list('service_type__slug', flat=True))
                categories = [st for st in all_types if st.slug and st.slug in enabled_slugs]
            else:
                disabled_slugs = set(bsc_qs.filter(is_enabled=False).values_list('service_type__slug', flat=True))
                categories = [st for st in all_types if not (st.slug and st.slug in disabled_slugs)]
        else:
            bsc_qs = BranchServiceCategory.objects.filter(is_deleted=False)
            if bsc_qs.filter(is_enabled=True).exists():
                enabled_slugs = set(bsc_qs.filter(is_enabled=True).values_list('service_type__slug', flat=True))
                categories = [st for st in all_types if st.slug and st.slug in enabled_slugs]
            else:
                categories = list(all_types)

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

    # CATEGORY FILTER
    if category_param:
        is_uuid = False
        try:
            import uuid
            uuid.UUID(str(category_param))
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        if is_uuid:
            cat_q = Q(items__service__service_type__id=category_param) | Q(items__service__service_type__slug=category_param)
        else:
            cat_q = Q(items__service__service_type__slug=category_param) | Q(items__service_detail__service_category=category_param)

        invoices = invoices.filter(cat_q).distinct()

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
        'categories': categories,
        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'category': category_param,
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


@login_required
def booking_report(request):

    bookings = Booking.objects.select_related('customer','vehicle','branch').filter(is_deleted=False)

    role = request.user.profile.role.name if request.user.profile.role else None

    if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):

        bookings = bookings.filter(
            branch=request.user.managed_branch
        )

    elif role == 'COMPANY_ADMIN' and request.user.profile.company:

        bookings = bookings.filter(
            branch__company=request.user.profile.company
        )

    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    if search:

        bookings = bookings.filter(
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )

    # STATUS

    if status:

        bookings = bookings.filter(
            status=status
        )

    if from_date:

        bookings = bookings.filter(
            booking_date__gte=from_date
        )

    if to_date:

        bookings = bookings.filter(
            booking_date__lte=to_date
        )

    bookings = bookings.order_by('-booking_date','-id')

    paginator = Paginator(bookings, 20)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'from_date': from_date,
        'to_date': to_date,
        'status_choices': Booking.STATUS_CHOICES,
    }

    return render(request, 'reports/booking_report.html', context)


@login_required
def cancellation_report(request):

    cancellations = Booking.objects.select_related(
        'customer',
        'vehicle',
        'branch'
    ).filter(
        is_deleted=False,
        status='cancelled'
    )

    role = request.user.profile.role.name if request.user.profile.role else None

    if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):

        cancellations = cancellations.filter(
            branch=request.user.managed_branch
        )

    elif role == 'COMPANY_ADMIN' and request.user.profile.company:

        cancellations = cancellations.filter(
            branch__company=request.user.profile.company
        )

    search = request.GET.get('search', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    if search:

        cancellations = cancellations.filter(
            Q(customer__name__icontains=search) |
            Q(customer__mobile__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )

    if from_date:

        cancellations = cancellations.filter(
            booking_date__gte=from_date
        )

    if to_date:

        cancellations = cancellations.filter(
            booking_date__lte=to_date
        )

    cancellations = cancellations.order_by(
        '-booking_date',
        '-id'
    )

    paginator = Paginator(cancellations, 20)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    total_cancelled = cancellations.count()

    context = {
        'page_obj': page_obj,
        'search': search,
        'from_date': from_date,
        'to_date': to_date,
        'total_cancelled': total_cancelled,
    }

    return render(request,'reports/cancellation_report.html',context)



@login_required
def profit_report(request):

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')

    income_rows = []
    expense_rows = []

    total_income = 0
    total_expense = 0
    net_profit = 0
    total_outstanding = 0

    role = request.user.profile.role.name if request.user.profile.role else None

    branches = Branch.objects.filter(is_deleted=False)

    if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):

        branches = branches.filter(
            id=request.user.managed_branch.id
        )

    elif role == 'COMPANY_ADMIN' and request.user.profile.company:

        branches = branches.filter(
            company=request.user.profile.company
        )

    if from_date and to_date:

        invoice_filter = {
            'invoice__is_deleted': False,
            'invoice__date__gte': from_date,
            'invoice__date__lte': to_date,
        }

        invoice_direct_filter = {
            'is_deleted': False,
            'date__gte': from_date,
            'date__lte': to_date,
        }

        expense_filter = {
            'is_deleted': False,
            'expense_date__gte': from_date,
            'expense_date__lte': to_date,
        }

        if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):

            invoice_filter['invoice__branch'] = (
                request.user.managed_branch
            )
            invoice_direct_filter['branch'] = (
                request.user.managed_branch
            )

            expense_filter['branch'] = (
                request.user.managed_branch
            )

        elif role == 'COMPANY_ADMIN' and request.user.profile.company:

            invoice_filter['invoice__branch__company'] = (
                request.user.profile.company
            )
            invoice_direct_filter['branch__company'] = (
                request.user.profile.company
            )

            expense_filter['branch__company'] = (
                request.user.profile.company
            )

        if branch_id:

            if branches.filter(id=branch_id).exists():

                invoice_filter['invoice__branch_id'] = branch_id
                invoice_direct_filter['branch_id'] = branch_id
                expense_filter['branch_id'] = branch_id

        income_rows = (
            InvoiceItem.objects
            .filter(**invoice_filter)
            .values('service_name')
            .annotate(
                amount=Sum(
                    F('rate') - F('discount')
                )
            )
            .order_by('-amount')
        )

        total_income = sum(
            float(item['amount'] or 0)
            for item in income_rows
        )
        
        expense_rows = (
            ExpenseEntry.objects
            .filter(**expense_filter)
            .values(
                'expense__expense_head__name'
            )
            .annotate(
                amount=Sum('amount')
            )
            .order_by('-amount')
        )

        total_expense = sum(
            float(item['amount'] or 0)
            for item in expense_rows
        )

        net_profit = total_income - total_expense
        invoices = Invoice.objects.filter(**invoice_direct_filter)
        total_outstanding = sum(float((inv.total or 0) - (inv.amount_collected or 0)) for inv in invoices)

    context = {
        'branches': branches,
        'branch_id': branch_id,
        'from_date': from_date,
        'to_date': to_date,
        'income_rows': income_rows,
        'expense_rows': expense_rows,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'total_outstanding': total_outstanding,
    }

    return render(
        request,
        'reports/profit_report.html',
        context
    )
    

@login_required
def profit_report_pdf(request):

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')

    income_rows = []
    expense_rows = []

    total_income = 0
    total_expense = 0
    net_profit = 0

    role = request.user.profile.role.name if request.user.profile.role else None

    branches = Branch.objects.filter(is_deleted=False)
    print("companny",request.user.profile.company)

    if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):
        branches = branches.filter(
            id=request.user.managed_branch.id
        )

    elif role == 'COMPANY_ADMIN' and request.user.profile.company:
        branches = branches.filter(
            company=request.user.profile.company
        )

    invoice_filter = {
        'invoice__is_deleted': False,
    }

    invoice_direct_filter = {
        'is_deleted': False,
    }

    expense_filter = {
        'is_deleted': False,
    }

    if from_date:
        invoice_filter['invoice__date__gte'] = from_date
        invoice_direct_filter['date__gte'] = from_date
        expense_filter['expense_date__gte'] = from_date

    if to_date:
        invoice_filter['invoice__date__lte'] = to_date
        invoice_direct_filter['date__lte'] = to_date
        expense_filter['expense_date__lte'] = to_date

    if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):

        invoice_filter['invoice__branch'] = request.user.managed_branch
        invoice_direct_filter['branch'] = request.user.managed_branch
        expense_filter['branch'] = request.user.managed_branch

    elif role == 'COMPANY_ADMIN' and request.user.profile.company:

        invoice_filter['invoice__branch__company'] = request.user.profile.company
        invoice_direct_filter['branch__company'] = request.user.profile.company
        expense_filter['branch__company'] = request.user.profile.company

    if branch_id and branches.filter(id=branch_id).exists():

        invoice_filter['invoice__branch_id'] = branch_id
        invoice_direct_filter['branch_id'] = branch_id
        expense_filter['branch_id'] = branch_id

    income_rows = (
        InvoiceItem.objects
        .filter(**invoice_filter)
        .values('service_name')
        .annotate(
            amount=Sum(F('rate') - F('discount'))
        )
        .order_by('-amount')
    )

    total_income = sum(
        float(item['amount'] or 0)
        for item in income_rows
    )

    expense_rows = (
        ExpenseEntry.objects
        .filter(**expense_filter)
        .values(
            'expense__expense_head__name'
        )
        .annotate(
            amount=Sum('amount')
        )
        .order_by('-amount')
    )

    total_expense = sum(
        float(item['amount'] or 0)
        for item in expense_rows
    )

    net_profit = total_income - total_expense
    invoices = Invoice.objects.filter(**invoice_direct_filter)
    total_outstanding = sum(float((inv.total or 0) - (inv.amount_collected or 0)) for inv in invoices)

    context = {
        'from_date': from_date,
        'to_date': to_date,
        'income_rows': income_rows,
        'expense_rows': expense_rows,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'total_outstanding': total_outstanding,
        "company": request.user.profile.company,
    }

    html_string = render_to_string(
        'reports/profit_report_pdf.html',
        context
    )

    html = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')
    )

    pdf = html.write_pdf()

    response = HttpResponse(
        pdf,
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        'inline; filename="profit_report.pdf"'
    )

    return response

@login_required
def expense_report(request):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')
    expense_head_id = request.GET.get('expense_head')


    today = timezone.now().date()

    if not from_date:
        from_date = today

    if not to_date:
        to_date = today


    if role_name == 'COMPANY_ADMIN':

        company = getattr(
            request.user.profile,
            'company',
            None
        )

        branches = Branch.objects.filter(
            company=company,
            is_deleted=False
        )

        expenses = ExpenseEntry.objects.filter(
            company=company,
            expense_date__gte=from_date,
            expense_date__lte=to_date,
            is_deleted=False
        ).select_related(
            'branch',
            'expense',
            'expense__expense_head'
        )

        if branch_id:

            expenses = expenses.filter(
                branch_id=branch_id
            )


    else:

        branch = getattr(
            request.user,
            'managed_branch',
            None
        )

        branches = None

        expenses = ExpenseEntry.objects.filter(
            branch=branch,
            expense_date__gte=from_date,
            expense_date__lte=to_date,
            is_deleted=False
        ).select_related(
            'branch',
            'expense',
            'expense__expense_head'
        )


    if expense_head_id:

        expenses = expenses.filter(
            expense__expense_head_id=expense_head_id
        )

    total_expense = expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    expense_heads = ExpenseHead.objects.filter(
        company=company,
        is_deleted=False
    )

    context = {

        'expenses': expenses,
        'branches': branches,
        'expense_heads': expense_heads,

        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'expense_head_id': expense_head_id,

        'total_expense': total_expense,

        'title': 'Expense Report'
    }

    return render(request,'reports/expense_report.html',context)


@login_required
def expense_head_report(request):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')

    today = timezone.now().date()

    if not from_date:
        from_date = today

    if not to_date:
        to_date = today

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

        branches = Branch.objects.filter(
            company=company,
            is_deleted=False
        )

        expenses = ExpenseEntry.objects.filter(
            company=company,
            expense_date__gte=from_date,
            expense_date__lte=to_date,
            is_deleted=False
        )

        if branch_id:

            expenses = expenses.filter(
                branch_id=branch_id
            )

    else:

        branch = request.user.managed_branch

        branches = None

        expenses = ExpenseEntry.objects.filter(
            branch=branch,
            expense_date__gte=from_date,
            expense_date__lte=to_date,
            is_deleted=False
        )
        
    expense_head_data = expenses.values(
        'expense__expense_head__id',
        'expense__expense_head__name'
    ).annotate(
        total_amount=Coalesce(
        Sum('amount'),
        Value(0),
        output_field=DecimalField()
    )
    ).order_by(
        '-total_amount'
    )

    total_expense = expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    context = {

        'expense_head_data': expense_head_data,
        'branches': branches,

        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,

        'total_expense': total_expense,
        'title': 'Expense Head Report'
    }

    return render(request,'reports/expense_head_report.html',context)
    
    
@login_required
def expense_head_detail_report(request, pk):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

    else:

        branch = request.user.managed_branch
        company = branch.company

    expense_head = get_object_or_404(
        ExpenseHead,
        pk=pk,
        company=company,
        is_deleted=False
    )

   
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch')

    try:
        if from_date:
            from_date = datetime.strptime(
                from_date,
                '%Y-%m-%d'
            ).date()
    except:
        from_date = None

    try:
        if to_date:
            to_date = datetime.strptime(
                to_date,
                '%Y-%m-%d'
            ).date()
    except:
        to_date = None

    expenses = ExpenseEntry.objects.filter(
        is_deleted=False,
        expense__expense_head=expense_head
    ).select_related(
        'expense',
        'branch'
    ).order_by('-expense_date')

    branches = None

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

        expenses = expenses.filter(
            company=company
        )

        branches = Branch.objects.filter(
            company=company,
            is_deleted=False
        )

    else:

        branch = request.user.managed_branch

        expenses = expenses.filter(
            branch=branch
        )

    if from_date:

        expenses = expenses.filter(
            expense_date__gte=from_date
        )

    if to_date:

        expenses = expenses.filter(
            expense_date__lte=to_date
        )

    if branch_id:

        expenses = expenses.filter(
            branch_id=branch_id
        )

    total_expense = expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    context = {

        'expense_head': expense_head,

        'expenses': expenses,

        'total_expense': total_expense,

        'from_date': from_date,
        'to_date': to_date,

        'branches': branches,
        'branch_id': branch_id,

    }

    return render(request,'reports/expense_head_detail_report.html',context)


def generate_invoice_pdf_file(invoice, base_url):
    import sys
    import os
    from django.template.loader import render_to_string
    from django.conf import settings
    
    if sys.platform == 'darwin':
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = '/opt/homebrew/lib:' + os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
    from weasyprint import HTML
    
    balance = invoice.total - invoice.amount_collected
    currency = '₹'
    if invoice.branch and invoice.branch.company and invoice.branch.company.country:
        currency = getattr(invoice.branch.company.country, 'currency_symbol', '₹') or '₹'
        
    context = {
        'invoice': invoice,
        'balance': balance,
        'currency': currency,
    }
    
    html_string = render_to_string('invoice/invoice_pdf.html', context)
    
    media_dir = os.path.join(settings.BASE_DIR, 'media', 'invoices')
    os.makedirs(media_dir, exist_ok=True)
    
    clean_no = str(invoice.invoice_number).replace('/', '_')
    pdf_filename = f"invoice-{clean_no}.pdf"
    pdf_path = os.path.join(media_dir, pdf_filename)
    
    # Render PDF using WeasyPrint
    html = HTML(string=html_string, base_url=base_url)
    html.write_pdf(target=pdf_path)

    # Also save with raw filename if it does not contain slashes and differs
    raw_filename = f"invoice-{invoice.invoice_number}.pdf"
    if '/' not in str(invoice.invoice_number):
        raw_pdf_path = os.path.join(media_dir, raw_filename)
        if raw_pdf_path != pdf_path:
            try:
                import shutil
                shutil.copyfile(pdf_path, raw_pdf_path)
            except Exception:
                pass
    
    # Return the absolute public URL
    if not base_url or '127.0.0.1' in base_url or 'localhost' in base_url:
        base_url = 'http://68.183.94.11:78'

    if not base_url.endswith('/'):
        base_url += '/'
    return f"{base_url}media/invoices/{pdf_filename}"


def generate_quotation_pdf_file(quotation, base_url):
    import sys
    import os
    from django.template.loader import render_to_string
    from django.conf import settings
    
    if sys.platform == 'darwin':
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = '/opt/homebrew/lib:' + os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
    from weasyprint import HTML
    
    currency = '₹'
    if quotation.branch and quotation.branch.company and quotation.branch.company.country:
        currency = getattr(quotation.branch.company.country, 'currency_symbol', '₹') or '₹'
        
    context = {
        'quotation': quotation,
        'currency': currency,
    }
    
    html_string = render_to_string('quotation/quotation_pdf.html', context)
    
    media_dir = os.path.join(settings.BASE_DIR, 'media', 'quotations')
    os.makedirs(media_dir, exist_ok=True)
    
    pdf_filename = f"quotation-{quotation.quotation_number}.pdf"
    pdf_path = os.path.join(media_dir, pdf_filename)
    
    html = HTML(string=html_string, base_url=base_url)
    html.write_pdf(target=pdf_path)
    
    if not base_url or '127.0.0.1' in base_url or 'localhost' in base_url:
        base_url = 'http://68.183.94.11:78'

    if not base_url.endswith('/'):
        base_url += '/'
    return f"{base_url}media/quotations/{pdf_filename}"


@login_required
def payment_type_report(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    from finance_management.models import Receipt
    from django.db.models import Sum

    receipts = Receipt.objects.filter(is_deleted=False).select_related(
        'invoice', 'invoice__customer', 'invoice__vehicle', 'invoice__branch'
    ).order_by('-created_at')

    # Scope filtering
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        receipts = receipts.filter(invoice__branch__company=user.profile.company)
        branches = Branch.objects.filter(company=user.profile.company, is_deleted=False)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        receipts = receipts.filter(invoice__branch=user.managed_branch)
        branches = None
    else:
        branches = Branch.objects.filter(is_deleted=False)

    # Date filters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch_id = request.GET.get('branch_id')

    if from_date:
        receipts = receipts.filter(created_at__date__gte=from_date)
    if to_date:
        receipts = receipts.filter(created_at__date__lte=to_date)
    if branch_id:
        receipts = receipts.filter(invoice__branch_id=branch_id)

    # Calculate payment type totals
    grouped = receipts.values('payment_mode').annotate(total_amount=Sum('amount')).order_by('-total_amount')
    
    PAYMENT_LABELS = dict(Receipt.PAYMENT_CHOICES)
    summary = []
    total_collected = 0
    for item in grouped:
        mode = item['payment_mode']
        amt = item['total_amount'] or 0
        total_collected += amt
        summary.append({
            'payment_mode': mode,
            'payment_mode_display': PAYMENT_LABELS.get(mode, mode.title()),
            'total_amount': amt,
        })

    # Fill in missing modes
    existing_modes = {item['payment_mode'] for item in grouped}
    for mode, label in Receipt.PAYMENT_CHOICES:
        if mode not in existing_modes:
            summary.append({
                'payment_mode': mode,
                'payment_mode_display': label,
                'total_amount': Decimal('0.00'),
            })

    context = {
        'receipts': receipts,
        'summary': summary,
        'total_collected': total_collected,
        'branches': branches,
        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'title': 'Payment Type Report',
    }

    return render(request, 'reports/payment_type_report.html', context)


@login_required
def staff_income_report(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    from client_management.models import Branch, Staff
    from finance_management.models import Invoice
    from datetime import datetime, date

    from_date_str = request.GET.get('from_date', '')
    to_date_str = request.GET.get('to_date', '')
    branch_id = request.GET.get('branch_id', '')
    staff_id = request.GET.get('staff_id', '')

    today = date.today()
    def parse_d(d_str, default):
        if not d_str:
            return default
        try:
            return datetime.strptime(d_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(d_str, '%d-%m-%Y').date()
            except ValueError:
                return default

    from_date = parse_d(from_date_str, today)
    to_date = parse_d(to_date_str, today)


    invoices = Invoice.objects.filter(
        is_deleted=False,
        date__gte=from_date,
        date__lte=to_date,
        assigned_staffs__isnull=False
    ).prefetch_related('assigned_staffs', 'customer', 'vehicle', 'branch').distinct()

    staff_qs = Staff.objects.filter(is_deleted=False)
    branches = None

    if role == 'COMPANY_ADMIN':
        if hasattr(user.profile, 'company') and user.profile.company:
            company = user.profile.company
            invoices = invoices.filter(branch__company=company)
            staff_qs = staff_qs.filter(company=company)
            branches = Branch.objects.filter(company=company, is_deleted=False)
        else:
            branches = Branch.objects.filter(is_deleted=False)
    elif role == 'BRANCH_ADMIN':
        if hasattr(user, 'managed_branch') and user.managed_branch:
            invoices = invoices.filter(branch=user.managed_branch)
            staff_qs = staff_qs.filter(branch=user.managed_branch)
        branches = None

    if branch_id:
        invoices = invoices.filter(branch_id=branch_id)
        staff_qs = staff_qs.filter(branch_id=branch_id)

    if staff_id:
        invoices = invoices.filter(assigned_staffs__id=staff_id)
        staff_qs = staff_qs.filter(id=staff_id)

    staff_map = {}
    for st in staff_qs:
        desig = st.get_designation_display() if hasattr(st, 'get_designation_display') else (st.designation or '')
        staff_map[str(st.id)] = {
            'id': str(st.id),
            'name': st.name,
            'employee_id': st.employee_id or '',
            'designation': desig,
            'branch_name': st.branch.name if st.branch else '',
            'invoice_count': 0,
            'total_income': 0.0,
            'split_income': 0.0,
            'invoices': [],
        }

    total_invoices_set = set()

    for inv in invoices.order_by('-date', '-auto_id'):
        assigned = list(inv.assigned_staffs.all())
        if not assigned:
            continue

        total_invoices_set.add(inv.id)
        staff_count = len(assigned)
        inv_total = float(inv.total or 0.0)
        split_share = inv_total / staff_count if staff_count > 0 else 0.0

        for st in assigned:
            st_id = str(st.id)
            if st_id not in staff_map:
                desig = st.get_designation_display() if hasattr(st, 'get_designation_display') else (st.designation or '')
                staff_map[st_id] = {
                    'id': st_id,
                    'name': st.name,
                    'employee_id': st.employee_id or '',
                    'designation': desig,
                    'branch_name': st.branch.name if st.branch else '',
                    'invoice_count': 0,
                    'total_income': 0.0,
                    'split_income': 0.0,
                    'invoices': [],
                }

            sdata = staff_map[st_id]
            sdata['invoice_count'] += 1
            sdata['total_income'] += inv_total
            sdata['split_income'] += split_share
            sdata['invoices'].append({
                'id': str(inv.id),
                'invoice_number': inv.invoice_number,
                'date': inv.date,
                'customer_name': inv.customer.name if inv.customer else 'N/A',
                'vehicle_number': inv.vehicle.vehicle_number if inv.vehicle else 'N/A',
                'total': inv_total,
                'assigned_staff_count': staff_count,
                'share_amount': split_share,
            })

    staff_rows = sorted(list(staff_map.values()), key=lambda x: x['total_income'], reverse=True)

    grand_total_income = sum(float(inv.total or 0.0) for inv in invoices)
    grand_split_income = sum(r['split_income'] for r in staff_rows)

    context = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'branch_id': branch_id,
        'staff_id': staff_id,
        'branches': branches,
        'all_staffs': staff_qs,
        'staff_rows': staff_rows,
        'total_staffs': len(staff_rows),
        'total_invoices': len(total_invoices_set),
        'grand_total_income': grand_total_income,
        'grand_split_income': grand_split_income,
        'title': 'Staff Income Report',
    }

    return render(request, 'reports/staff_income_report.html', context)


@login_required

def ajax_get_customer_vehicles(request, customer_id):
    from client_management.models import CustomerVehicle
    vehicles = CustomerVehicle.objects.filter(customer_id=customer_id, is_deleted=False).select_related('vehicle_type_model')
    data = []
    for v in vehicles:
        data.append({
            'id': str(v.id),
            'vehicle_number': v.vehicle_number,
            'model_name': v.vehicle_type_model.name if v.vehicle_type_model else '',
            'wheel_type': v.wheel_type or 'normal_wheel',
            'current_odometer_km': v.current_odometer_km or 0,
        })
    return JsonResponse({'success': True, 'vehicles': data})


@login_required
def invoice_create(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    if request.method == 'POST':
        import json
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            payload_str = request.POST.get('payload')
            if payload_str:
                data = json.loads(payload_str)
            else:
                data = request.POST.dict()

        customer_id = data.get('customer_id')
        vehicle_id = data.get('vehicle_id')
        
        if not customer_id or not vehicle_id:
            return JsonResponse({'success': False, 'message': 'Customer and Vehicle are required'}, status=400)

        from client_management.api_views import api_create_invoice
        request._body = json.dumps(data).encode('utf-8')
        response = api_create_invoice(request)
        return response

    from client_management.models import Customer, Stock, Scheme, Extras
    from tax_management.models import CompanyTax
    from service_management.models import Service
    from master.models import OilProduct, OilFilter, TyreBrand, Tyre

    customer_qs = Customer.objects.filter(is_deleted=False).order_by('name')
    service_qs = Service.objects.filter(is_deleted=False).order_by('name')
    stock_qs = Stock.objects.filter(is_deleted=False).order_by('item_name')
    extras_qs = Extras.objects.filter(is_deleted=False).order_by('name')
    scheme_qs = Scheme.objects.filter(is_deleted=False).order_by('name')
    
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        customer_qs = customer_qs.filter(company=user.profile.company)
        service_qs = service_qs.filter(company=user.profile.company)
        stock_qs = stock_qs.filter(company=user.profile.company)
        extras_qs = extras_qs.filter(company=user.profile.company)
        scheme_qs = scheme_qs.filter(company=user.profile.company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        customer_qs = customer_qs.filter(branch=user.managed_branch)
        service_qs = service_qs.filter(company=user.managed_branch.company)
        stock_qs = stock_qs.filter(company=user.managed_branch.company)
        extras_qs = extras_qs.filter(company=user.managed_branch.company)
        scheme_qs = scheme_qs.filter(company=user.managed_branch.company)

    oil_products = OilProduct.objects.filter(is_deleted=False).order_by('name')
    oil_filters = OilFilter.objects.filter(is_deleted=False).order_by('name')
    tyre_brands = TyreBrand.objects.filter(is_deleted=False).order_by('brand')
    tyres = Tyre.objects.filter(is_deleted=False).select_related('brand').order_by('name')
    
    company_taxes = []
    if hasattr(user.profile, 'company') and user.profile.company:
        company_taxes = CompanyTax.objects.filter(company=user.profile.company, is_deleted=False)

    context = {
        'customers': customer_qs,
        'services': service_qs,
        'stock_items': stock_qs,
        'extras': extras_qs,
        'schemes': scheme_qs,
        'oil_products': oil_products,
        'oil_filters': oil_filters,
        'tyre_brands': tyre_brands,
        'tyres': tyres,
        'company_taxes': company_taxes,
        'title': 'Create Invoice',
    }

    return render(request, 'invoice/create.html', context)


@login_required
def collection_report(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    from finance_management.models import Receipt
    from django.db.models import Sum

    today = timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')

    from_date_param = request.GET.get('from_date') if 'from_date' in request.GET else request.GET.get('fromdate')
    to_date_param = request.GET.get('to_date') if 'to_date' in request.GET else request.GET.get('todate')

    if from_date_param is None:
        from_date = today_str
    else:
        from_date = from_date_param.strip()

    if to_date_param is None:
        to_date = today_str
    else:
        to_date = to_date_param.strip()

    receipts = Receipt.objects.filter(is_deleted=False).select_related(
        'invoice', 'invoice__customer', 'invoice__vehicle', 'invoice__vehicle__vehicle_type_model', 'invoice__branch'
    ).order_by('-created_at')

    branches = None
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        receipts = receipts.filter(invoice__branch__company=user.profile.company)
        branches = Branch.objects.filter(company=user.profile.company, is_deleted=False)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        receipts = receipts.filter(invoice__branch=user.managed_branch)

    branch_id = request.GET.get('branch_id') or request.GET.get('branch')
    if branch_id:
        receipts = receipts.filter(invoice__branch_id=branch_id)

    # Date filter
    if from_date:
        try:
            parsed_from = datetime.strptime(from_date, '%Y-%m-%d').date()
            receipts = receipts.filter(created_at__date__gte=parsed_from)
        except ValueError:
            receipts = receipts.filter(created_at__date__gte=from_date)

    if to_date:
        try:
            parsed_to = datetime.strptime(to_date, '%Y-%m-%d').date()
            receipts = receipts.filter(created_at__date__lte=parsed_to)
        except ValueError:
            receipts = receipts.filter(created_at__date__lte=to_date)

    search = request.GET.get('search', '').strip()
    if search:
        receipts = receipts.filter(
            Q(receipt_number__icontains=search) |
            Q(invoice__invoice_number__icontains=search) |
            Q(invoice__customer__name__icontains=search) |
            Q(invoice__customer__phone__icontains=search) |
            Q(invoice__vehicle__vehicle_number__icontains=search)
        )

    # Summary by payment mode
    summary_grouped = receipts.values('payment_mode').annotate(total_amount=Sum('amount')).order_by('-total_amount')
    PAYMENT_LABELS = dict(Receipt.PAYMENT_CHOICES)
    mode_totals = {item['payment_mode']: item['total_amount'] or Decimal('0.00') for item in summary_grouped}

    total_collected = sum(mode_totals.values(), Decimal('0.00'))
    total_cash = mode_totals.get('cash', Decimal('0.00'))
    total_card = mode_totals.get('card', Decimal('0.00'))
    total_digital = mode_totals.get('digital_payments', Decimal('0.00'))
    total_cheque = mode_totals.get('cheque', Decimal('0.00'))
    total_online = mode_totals.get('online', Decimal('0.00'))

    summary = []
    seen_modes = set()
    for item in summary_grouped:
        mode = item['payment_mode']
        amt = item['total_amount'] or Decimal('0.00')
        seen_modes.add(mode)
        summary.append({
            'payment_mode': mode,
            'payment_mode_display': PAYMENT_LABELS.get(mode, mode.replace('_', ' ').title()),
            'total_amount': amt,
        })
    for mode, label in Receipt.PAYMENT_CHOICES:
        if mode not in seen_modes:
            summary.append({
                'payment_mode': mode,
                'payment_mode_display': label,
                'total_amount': Decimal('0.00'),
            })

    # Optional table filter by payment_mode
    payment_mode = request.GET.get('payment_mode', '').strip()
    if payment_mode:
        receipts = receipts.filter(payment_mode=payment_mode)

    table_total = receipts.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    context = {
        'receipts': receipts,
        'summary': summary,
        'total_collected': total_collected,
        'total_cash': total_cash,
        'total_card': total_card,
        'total_digital': total_digital,
        'total_cheque': total_cheque,
        'total_online': total_online,
        'table_total': table_total,
        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'branches': branches,
        'search': search,
        'payment_mode': payment_mode,
        'title': 'Collection Report',
    }
    return render(request, 'reports/collection_report.html', context)


@login_required
def tax_report(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    from tax_management.models import Tax, CompanyTax
    from master.models import PurchaseInvoice, Country

    today = timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date()
    first_of_month = today.replace(day=1)

    from_date_param = request.GET.get('from_date')
    to_date_param = request.GET.get('to_date')

    if from_date_param is None and to_date_param is None:
        from_date = first_of_month.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    else:
        from_date = (from_date_param or '').strip()
        to_date = (to_date_param or '').strip()

    branch_id = (request.GET.get('branch_id') or request.GET.get('branch') or '').strip()
    tax_filter = request.GET.get('tax_filter', 'all').strip()
    tax_mode = request.GET.get('tax_mode', 'intrastate').strip()
    search = request.GET.get('search', '').strip()
    active_tab = request.GET.get('tab', 'sales').strip()

    company = None
    branches = None
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        company = user.profile.company
        branches = Branch.objects.filter(company=company, is_deleted=False)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        company = user.managed_branch.company
    else:
        branches = Branch.objects.filter(is_deleted=False)

    # Resolve Country based on company or user
    country = None
    if company and company.country:
        country = company.country
    elif hasattr(user, 'profile') and hasattr(user.profile, 'country') and user.profile.country:
        country = user.profile.country
    else:
        country = Country.objects.filter(name__iexact='India').first()

    country_name = country.name if country else 'India'
    is_india = (country_name.strip().lower() == 'india')

    # Query taxes for country from Settings -> Taxes
    country_taxes = []
    if country:
        country_taxes = Tax.objects.filter(country=country, is_deleted=False).order_by('name')
    elif is_india:
        india_obj = Country.objects.filter(name__iexact='India').first()
        if india_obj:
            country_taxes = Tax.objects.filter(country=india_obj, is_deleted=False).order_by('name')

    # Detect CGST, SGST, IGST rates if India
    cgst_rate = Decimal('9.00')
    sgst_rate = Decimal('9.00')
    igst_rate = Decimal('18.00')
    single_tax_rate = Decimal('0.00')
    single_tax_name = 'Tax'

    for t in country_taxes:
        tname = t.name.strip().upper()
        if 'CGST' in tname:
            cgst_rate = t.percent
        elif 'SGST' in tname:
            sgst_rate = t.percent
        elif 'IGST' in tname:
            igst_rate = t.percent
        else:
            single_tax_rate = t.percent
            single_tax_name = t.name

    # 1. Sales Invoices (Output Tax)
    invoices = Invoice.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).order_by('-date', '-auto_id')

    if role == 'COMPANY_ADMIN' and company:
        invoices = invoices.filter(branch__company=company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        invoices = invoices.filter(branch=user.managed_branch)

    if branch_id:
        invoices = invoices.filter(branch_id=branch_id)

    if from_date:
        invoices = invoices.filter(date__gte=from_date)
    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )

    # Aggregate before tax filter for complete KPI summary
    sales_all_agg = invoices.aggregate(
        total_tax=Sum('tax_amount'),
        total_subtotal=Sum('subtotal'),
        total_discount=Sum('discount'),
        total_gross=Sum('total'),
        total_collected=Sum('amount_collected'),
    )
    total_sales_tax = sales_all_agg['total_tax'] or Decimal('0.00')
    total_sales_subtotal = sales_all_agg['total_subtotal'] or Decimal('0.00')
    total_sales_discount = sales_all_agg['total_discount'] or Decimal('0.00')
    total_taxable_sales = max(Decimal('0.00'), total_sales_subtotal - total_sales_discount)
    total_gross_sales = sales_all_agg['total_gross'] or Decimal('0.00')
    total_invoices_count = invoices.count()
    taxed_invoices_count = invoices.filter(tax_amount__gt=0).count()
    zero_tax_invoices_count = total_invoices_count - taxed_invoices_count

    # Calculate overall CGST, SGST, IGST totals
    if is_india:
        if tax_mode == 'interstate':
            total_cgst = Decimal('0.00')
            total_sgst = Decimal('0.00')
            total_igst = total_sales_tax
        else:
            total_cgst = (total_sales_tax / Decimal('2.0')).quantize(Decimal('0.01'))
            total_sgst = total_sales_tax - total_cgst
            total_igst = Decimal('0.00')
    else:
        total_cgst = Decimal('0.00')
        total_sgst = Decimal('0.00')
        total_igst = Decimal('0.00')

    # Apply tax filter to list
    if tax_filter == 'taxed':
        invoices = invoices.filter(tax_amount__gt=0)
    elif tax_filter == 'zero':
        invoices = invoices.filter(tax_amount=0)

    # Evaluate invoice list and separate tax amounts per row
    table_sales_taxable = Decimal('0.00')
    table_sales_tax = Decimal('0.00')
    table_sales_total = Decimal('0.00')
    table_cgst = Decimal('0.00')
    table_sgst = Decimal('0.00')
    table_igst = Decimal('0.00')

    invoices_list = list(invoices)
    for inv in invoices_list:
        taxable = max(Decimal('0.00'), (inv.subtotal or Decimal('0.00')) - (inv.discount or Decimal('0.00')))
        tax_amt = inv.tax_amount or Decimal('0.00')
        inv.taxable_amount = taxable

        if is_india:
            if tax_mode == 'interstate':
                c = Decimal('0.00')
                s = Decimal('0.00')
                i = tax_amt
            else:
                c = (tax_amt / Decimal('2.0')).quantize(Decimal('0.01'))
                s = tax_amt - c
                i = Decimal('0.00')
            inv.cgst_amount = c
            inv.sgst_amount = s
            inv.igst_amount = i
            table_cgst += c
            table_sgst += s
            table_igst += i
        else:
            inv.cgst_amount = Decimal('0.00')
            inv.sgst_amount = Decimal('0.00')
            inv.igst_amount = Decimal('0.00')

        table_sales_taxable += taxable
        table_sales_tax += tax_amt
        table_sales_total += (inv.total or Decimal('0.00'))

    # 2. Purchase Invoices (Input Tax)
    purchases = PurchaseInvoice.objects.filter(is_deleted=False).select_related(
        'supplier', 'branch'
    ).order_by('-invoice_date')

    if role == 'COMPANY_ADMIN' and company:
        purchases = purchases.filter(company=company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        purchases = purchases.filter(branch=user.managed_branch)

    if branch_id:
        purchases = purchases.filter(branch_id=branch_id)

    if from_date:
        purchases = purchases.filter(invoice_date__gte=from_date)
    if to_date:
        purchases = purchases.filter(invoice_date__lte=to_date)

    if search:
        purchases = purchases.filter(
            Q(purchase_inv_number__icontains=search) |
            Q(supplier__name__icontains=search)
        )

    purchase_agg = purchases.aggregate(
        total_tax=Sum('tax_total'),
        total_subtotal=Sum('subtotal'),
        total_grand=Sum('grand_total'),
    )
    total_purchase_tax = purchase_agg['total_tax'] or Decimal('0.00')
    total_taxable_purchases = purchase_agg['total_subtotal'] or Decimal('0.00')
    total_purchase_grand = purchase_agg['total_grand'] or Decimal('0.00')
    total_purchases_count = purchases.count()

    total_purchase_cgst = Decimal('0.00')
    total_purchase_sgst = Decimal('0.00')
    total_purchase_igst = Decimal('0.00')

    purchases_list = list(purchases)
    for p in purchases_list:
        ptax = p.tax_total or Decimal('0.00')
        if is_india:
            if tax_mode == 'interstate':
                pc = Decimal('0.00')
                ps = Decimal('0.00')
                pi = ptax
            else:
                pc = (ptax / Decimal('2.0')).quantize(Decimal('0.01'))
                ps = ptax - pc
                pi = Decimal('0.00')
            p.cgst_amount = pc
            p.sgst_amount = ps
            p.igst_amount = pi
            total_purchase_cgst += pc
            total_purchase_sgst += ps
            total_purchase_igst += pi
        else:
            p.cgst_amount = Decimal('0.00')
            p.sgst_amount = Decimal('0.00')
            p.igst_amount = Decimal('0.00')

    # Net Tax Position: Output Tax - Input Tax
    net_tax_payable = total_sales_tax - total_purchase_tax
    net_cgst = total_cgst - total_purchase_cgst
    net_sgst = total_sgst - total_purchase_sgst
    net_igst = total_igst - total_purchase_igst

    # Configured Company Taxes from Settings -> Taxes
    company_taxes = []
    if company:
        company_taxes = CompanyTax.objects.filter(
            company=company, is_enabled=True, is_deleted=False
        ).select_related('tax').order_by('tax__name')

    currency_symbol = country.currency_symbol if country and country.currency_symbol else '₹'

    context = {
        'invoices': invoices_list,
        'purchases': purchases_list,
        'country': country,
        'country_name': country_name,
        'is_india': is_india,
        'cgst_rate': cgst_rate,
        'sgst_rate': sgst_rate,
        'igst_rate': igst_rate,
        'single_tax_rate': single_tax_rate,
        'single_tax_name': single_tax_name,
        'country_taxes': country_taxes,
        'company_taxes': company_taxes,
        'currency_symbol': currency_symbol,
        'total_sales_tax': total_sales_tax,
        'total_taxable_sales': total_taxable_sales,
        'total_gross_sales': total_gross_sales,
        'total_invoices_count': total_invoices_count,
        'taxed_invoices_count': taxed_invoices_count,
        'zero_tax_invoices_count': zero_tax_invoices_count,
        'total_cgst': total_cgst,
        'total_sgst': total_sgst,
        'total_igst': total_igst,
        'table_sales_tax': table_sales_tax,
        'table_sales_taxable': table_sales_taxable,
        'table_sales_total': table_sales_total,
        'table_cgst': table_cgst,
        'table_sgst': table_sgst,
        'table_igst': table_igst,
        'total_purchase_tax': total_purchase_tax,
        'total_taxable_purchases': total_taxable_purchases,
        'total_purchase_grand': total_purchase_grand,
        'total_purchases_count': total_purchases_count,
        'total_purchase_cgst': total_purchase_cgst,
        'total_purchase_sgst': total_purchase_sgst,
        'total_purchase_igst': total_purchase_igst,
        'net_tax_payable': net_tax_payable,
        'net_cgst': net_cgst,
        'net_sgst': net_sgst,
        'net_igst': net_igst,
        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'branches': branches,
        'tax_filter': tax_filter,
        'tax_mode': tax_mode,
        'search': search,
        'active_tab': active_tab,
        'title': 'Tax Report',
    }
    return render(request, 'reports/tax_report.html', context)


@login_required
def outstanding_report(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    today = timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date()

    company = None
    branches = None
    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        company = user.profile.company
        branches = Branch.objects.filter(company=company, is_deleted=False)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        company = user.managed_branch.company
    else:
        branches = Branch.objects.filter(is_deleted=False)

    # Invoices where amount_collected < total (customer has unpaid balance)
    invoices = Invoice.objects.filter(
        is_deleted=False,
        customer__is_deleted=False,
        amount_collected__lt=F('total')
    ).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).order_by('-date', '-auto_id')

    # Scope by role
    if role == 'COMPANY_ADMIN' and company:
        invoices = invoices.filter(branch__company=company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        invoices = invoices.filter(branch=user.managed_branch)

    # Filters
    branch_id = (request.GET.get('branch_id') or request.GET.get('branch') or '').strip()
    if branch_id:
        invoices = invoices.filter(branch_id=branch_id)

    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()
    if from_date:
        invoices = invoices.filter(date__gte=from_date)
    if to_date:
        invoices = invoices.filter(date__lte=to_date)

    search = (request.GET.get('search') or '').strip()
    if search:
        invoices = invoices.filter(
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(invoice_number__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )

    aging_filter = (request.GET.get('aging') or 'all').strip()

    # Process invoice list, calculate balance and days passed
    invoice_list_data = []
    total_inv_amount = Decimal('0.00')
    total_paid_amount = Decimal('0.00')
    total_balance_amount = Decimal('0.00')
    total_days_passed = 0

    for inv in invoices:
        inv_amt = inv.total or Decimal('0.00')
        paid_amt = inv.amount_collected or Decimal('0.00')
        balance = inv_amt - paid_amt

        # Days passed from invoice date to today
        if inv.date:
            days_passed = max(0, (today - inv.date).days)
        else:
            days_passed = 0

        # Apply aging filter
        if aging_filter == '0_30' and not (0 <= days_passed <= 30):
            continue
        elif aging_filter == '31_60' and not (31 <= days_passed <= 60):
            continue
        elif aging_filter == '61_90' and not (61 <= days_passed <= 90):
            continue
        elif aging_filter == '90_plus' and not (days_passed > 90):
            continue

        total_inv_amount += inv_amt
        total_paid_amount += paid_amt
        total_balance_amount += balance
        total_days_passed += days_passed

        invoice_list_data.append({
            'invoice': inv,
            'customer_name': inv.customer.name if inv.customer else '-',
            'customer_phone': inv.customer.phone if inv.customer else '-',
            'vehicle_number': inv.vehicle.vehicle_number if inv.vehicle else '-',
            'vehicle_model': inv.vehicle.vehicle_type_model.name if inv.vehicle and inv.vehicle.vehicle_type_model else '',
            'branch_name': inv.branch.name if inv.branch else '',
            'inv_date': inv.date,
            'inv_amount': inv_amt,
            'paid': paid_amt,
            'balance': balance,
            'days_passed': days_passed,
        })

    count = len(invoice_list_data)
    avg_days_passed = round(total_days_passed / count) if count > 0 else 0

    currency_symbol = '₹'
    if company and company.country and company.country.currency_symbol:
        currency_symbol = company.country.currency_symbol

    context = {
        'invoices': invoice_list_data,
        'total_inv_amount': total_inv_amount,
        'total_paid_amount': total_paid_amount,
        'total_balance_amount': total_balance_amount,
        'total_count': count,
        'avg_days_passed': avg_days_passed,
        'currency_symbol': currency_symbol,
        'from_date': from_date,
        'to_date': to_date,
        'branch_id': branch_id,
        'branches': branches,
        'aging': aging_filter,
        'search': search,
        'title': 'Outstanding Report',
    }
    return render(request, 'reports/outstanding_report.html', context)
