import json
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.utils import timezone
from core.models import APIToken
from core.functions import get_auto_id
from .models import Customer, CustomerVehicle, Scheme, CustomerType, SchemeVoucher, Subscription
from service_management.models import Service


def _index_to_invoice_prefix(index):
    index = max(index, 0)
    chars = []

    while True:
        index, remainder = divmod(index, 26)
        chars.append(chr(65 + remainder))
        if index == 0:
            break
        index -= 1

    return ''.join(reversed(chars))


def _resolve_branch_invoice_prefix(branch):
    company_branches = list(
        branch.company.branches.all()
        .order_by('date_added', 'auto_id')
        .values('id', 'invoice_prefix')
    )

    branch_ids = [item['id'] for item in company_branches]
    try:
        branch_index = branch_ids.index(branch.id)
    except ValueError:
        branch_index = len(branch_ids)

    used_prefixes = {
        (item['invoice_prefix'] or '').strip().upper()
        for item in company_branches
        if item['id'] != branch.id and (item['invoice_prefix'] or '').strip()
    }

    current_prefix = (branch.invoice_prefix or '').strip().upper()
    preferred_prefix = _index_to_invoice_prefix(branch_index)
    resolved_prefix = current_prefix

    if not resolved_prefix or resolved_prefix in used_prefixes:
        resolved_prefix = preferred_prefix
        next_index = branch_index
        while resolved_prefix in used_prefixes:
            next_index += 1
            resolved_prefix = _index_to_invoice_prefix(next_index)

    if resolved_prefix != current_prefix:
        branch.invoice_prefix = resolved_prefix
        branch.save(update_fields=['invoice_prefix'])

    return resolved_prefix


@csrf_exempt
def api_login(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(username=username, password=password)
        if user is not None:
            if not hasattr(user, 'profile'):
                return JsonResponse({'success': False, 'message': 'User profile not found'}, status=403)
            
            role = user.profile.role.name if user.profile.role else None
            allowed_roles = ['COMPANY_ADMIN', 'BRANCH_ADMIN', 'BRANCH_MANAGER', 'MARKETING', 'CLERICAL', 'SERVICE']
            if role not in allowed_roles:
                return JsonResponse({'success': False, 'message': 'Unauthorized role'}, status=403)
                
            token_obj, created = APIToken.objects.get_or_create(user=user)
            
            company_name = user.profile.company.company_name if user.profile.company else ''
            branch_name = ''
            if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
                branch_name = user.managed_branch.name
            elif role in ['BRANCH_MANAGER', 'MARKETING', 'CLERICAL', 'SERVICE'] and hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.branch:
                branch_name = user.staff_profile.branch.name

            # Display name: staff name for staff, branch name for BRANCH_ADMIN, company name for COMPANY_ADMIN
            if role in ['BRANCH_MANAGER', 'MARKETING', 'CLERICAL', 'SERVICE'] and hasattr(user, 'staff_profile') and user.staff_profile:
                display_name = user.staff_profile.name
            else:
                display_name = branch_name if role == 'BRANCH_ADMIN' else company_name

            currency_symbol = '₹'
            if user.profile.company and user.profile.company.country and user.profile.company.country.currency_symbol:
                currency_symbol = user.profile.company.country.currency_symbol

            company = user.profile.company
            subscription_active = True
            subscription_days_left = 999
            subscription_end_date = None
            
            if company:
                subscription = Subscription.objects.filter(
                    company=company,
                    is_deleted=False
                ).order_by('-end_date').first()
                
                if subscription:
                    today = timezone.now().date()
                    subscription_days_left = (subscription.end_date - today).days
                    subscription_active = (subscription.start_date <= today <= subscription.end_date)
                    subscription_end_date = subscription.end_date.strftime('%Y-%m-%d')
                else:
                    subscription_active = False
                    subscription_days_left = -1

            company_logo = request.build_absolute_uri(company.logo_color.url) if company and company.logo_color else ''

            return JsonResponse({
                'success': True,
                'token': token_obj.token,
                'role': role,
                'company_name': company_name,
                'branch_name': branch_name,
                'display_name': display_name,
                'currency_symbol': currency_symbol,
                'username': user.username,
                'subscription_active': subscription_active,
                'subscription_days_left': subscription_days_left,
                'subscription_end_date': subscription_end_date,
                'company_logo': company_logo,
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid username or password'}, status=401)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def get_user_from_token(request):
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            token_obj = APIToken.objects.get(token=token)
            user = token_obj.user
            # Handle staff members
            if hasattr(user, 'staff_profile') and user.staff_profile:
                # Scope to their branch
                user.managed_branch = user.staff_profile.branch
                # In-memory role override to 'BRANCH_ADMIN' to reuse all branch scoping logic
                if hasattr(user, 'profile') and user.profile and user.profile.role:
                    user.profile.role.name = 'BRANCH_ADMIN'
            elif hasattr(user, 'profile') and user.profile and user.profile.role:
                # For non-staff BRANCH_ADMIN users logging in via the app,
                # set managed_branch from the database so all branch-scoped APIs work
                if user.profile.role.name == 'BRANCH_ADMIN' and not hasattr(user, 'managed_branch'):
                    from client_management.models import Branch
                    branch = Branch.objects.filter(
                        branch_admins=user, is_deleted=False
                    ).first()
                    if branch:
                        user.managed_branch = branch
            return user
        except APIToken.DoesNotExist:
            return None
    return None



def api_dashboard_stats(request):
    """Returns key dashboard stats for the mobile home screen."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from django.utils import timezone
    from django.db.models import Sum, F, DecimalField, ExpressionWrapper
    from finance_management.models import Invoice
    from decimal import Decimal

    today = timezone.now().date()
    role = user.profile.role.name if user.profile.role else None

    # Base queryset scoped to user's branch/company
    all_invoices = Invoice.objects.filter(is_deleted=False)
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        all_invoices = all_invoices.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        all_invoices = all_invoices.filter(branch__company=user.profile.company)

    today_invoices = all_invoices.filter(date=today)

    # Today stats
    today_jobs   = today_invoices.count()
    today_revenue = today_invoices.aggregate(t=Sum('total'))['t'] or Decimal('0')
    today_collected = today_invoices.aggregate(c=Sum('amount_collected'))['c'] or Decimal('0')

    # Today Net Profit (Revenue - Expense)
    from master.models import ExpenseEntry
    today_expenses_qs = ExpenseEntry.objects.filter(expense_date=today, is_deleted=False)
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        today_expenses_qs = today_expenses_qs.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        today_expenses_qs = today_expenses_qs.filter(company=user.profile.company)
    
    today_expense = today_expenses_qs.aggregate(e=Sum('amount'))['e'] or Decimal('0')
    today_net_profit = today_revenue - today_expense

    # Total outstanding (all time)
    outstanding_qs = all_invoices.annotate(
        bal=ExpressionWrapper(F('total') - F('amount_collected'), output_field=DecimalField())
    ).filter(bal__gt=0)
    total_outstanding = outstanding_qs.aggregate(o=Sum('bal'))['o'] or Decimal('0')
    outstanding_count = outstanding_qs.count()

    # Total customers
    from client_management.models import Customer
    customers_qs = Customer.objects.filter(is_deleted=False)
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        customers_qs = customers_qs.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        customers_qs = customers_qs.filter(company=user.profile.company)

    # Recent 3 invoices today
    recent = []
    for inv in today_invoices.select_related('customer', 'vehicle').order_by('-id')[:3]:
        recent.append({
            'invoice_number': inv.invoice_number,
            'customer': inv.customer.name if inv.customer else '',
            'vehicle': inv.vehicle.vehicle_number if inv.vehicle else '',
            'total': str(inv.total),
            'collected': str(inv.amount_collected),
        })

    company = user.profile.company
    subscription_active = True
    subscription_days_left = 999
    subscription_end_date = None
    
    if company:
        subscription = Subscription.objects.filter(
            company=company,
            is_deleted=False
        ).order_by('-end_date').first()
        
        if subscription:
            subscription_days_left = (subscription.end_date - today).days
            subscription_active = (subscription.start_date <= today <= subscription.end_date)
            subscription_end_date = subscription.end_date.strftime('%Y-%m-%d')
        else:
            subscription_active = False
            subscription_days_left = -1

    return JsonResponse({
        'success': True,
        'today_jobs': today_jobs,
        'total_jobs': today_jobs,        # backward compat
        'today_revenue': str(today_revenue),
        'today_collected': str(today_collected),
        'today_expense': str(today_expense),
        'today_net_profit': str(today_net_profit),
        'total_outstanding': str(total_outstanding),
        'outstanding_count': outstanding_count,
        'total_customers': customers_qs.count(),
        'recent_invoices': recent,
        'subscription_active': subscription_active,
        'subscription_days_left': subscription_days_left,
        'subscription_end_date': subscription_end_date,
    })


def _company_branch_from_request(user, branch_id):
    if not branch_id:
        return None
    company = user.profile.company
    if not company:
        return None
    from .models import Branch
    return Branch.objects.filter(
        id=branch_id,
        company=company,
        is_deleted=False,
    ).first()


def api_company_branches(request):
    """Mobile API: branches available to the logged-in company/branch user."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        branches = [user.managed_branch]
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        branches = user.profile.company.branches.filter(is_deleted=False).order_by('name')
    else:
        branches = []

    return JsonResponse({
        'success': True,
        'branches': [
            {
                'id': str(branch.id),
                'name': branch.name,
                'phone': branch.phone or '',
                'address': branch.address or '',
            }
            for branch in branches
        ],
    })

@csrf_exempt
def api_customer_search_list(request):
    """Partial phone/name/whatsapp search for suggestions in New Job screen."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized or invalid token'}, status=401)
        
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 3:
        return JsonResponse({'success': True, 'customers': []})
        
    company = user.profile.company
    customers = Customer.objects.filter(is_deleted=False, company=company)
    
    if user.profile.role.name == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        customers = customers.filter(branch=user.managed_branch)
        
    from django.db.models import Q
    customers = customers.filter(
        Q(phone__icontains=q) | 
        Q(whatsapp_number__icontains=q) | 
        Q(name__icontains=q)
    )[:20]
    
    results = []
    for c in customers:
        results.append({
            'id': str(c.id),
            'name': c.name,
            'phone': c.phone,
            'whatsapp_number': c.whatsapp_number,
            'customer_type': c.customer_type.name if c.customer_type else '',
            'branch_name': c.branch.name if c.branch else '',
        })
        
    return JsonResponse({'success': True, 'customers': results})


@csrf_exempt
def api_customer_search(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized or invalid token'}, status=401)
        
    mobile = request.GET.get('mobile', '').strip()
    if not mobile:
        return JsonResponse({'success': False, 'message': 'Mobile number is required'}, status=400)
        
    # Get user scope
    company = user.profile.company
    
    # Filter customers by scope and mobile number
    customers = Customer.objects.filter(is_deleted=False, company=company)
    
    if user.profile.role.name == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        customers = customers.filter(branch=user.managed_branch)
        
    # Search by phone or whatsapp
    customer = customers.filter(phone=mobile).first()
    if not customer:
        customer = customers.filter(whatsapp_number=mobile).first()
        
    if not customer:
        return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
        
    # Format vehicle data
    today = timezone.now().date()
    vehicles_data = []
    
    for v in customer.vehicles.filter(is_deleted=False):
        scheme_name = None
        paid_visits = 0
        free_visits = 0
        visits_count = 0
        is_eligible = False
        
        from finance_management.models import Invoice
        visits_count = Invoice.objects.filter(vehicle=v, is_deleted=False).count()

        # Check if customer's branch has scheme facility
        if customer.branch and customer.branch.scheme_types.exists() and customer.customer_type and v.vehicle_type_model and v.vehicle_type_model.vehicle_type:
            # Find active scheme
            scheme = Scheme.objects.filter(
                company=company,
                start_date__lte=today,
                end_date__gte=today,
                customer_types=customer.customer_type,
                vehicle_types=v.vehicle_type_model.vehicle_type,
                is_deleted=False
            ).first()
            
            if scheme:
                scheme_name = scheme.name
                paid_visits = scheme.paid_visits or 0
                free_visits = scheme.free_visits or 0
                
                if paid_visits > 0 and visits_count >= paid_visits:
                    is_eligible = True
                
        vehicles_data.append({
            'id': str(v.id),
            'no': v.vehicle_number,
            'type': v.vehicle_type_model.name if v.vehicle_type_model else 'Unknown',
            'vehicle_type': v.vehicle_type_model.vehicle_type.name if (v.vehicle_type_model and v.vehicle_type_model.vehicle_type) else '',
            'scheme_name': scheme_name,
            'paid_visits': paid_visits,
            'free_visits': free_visits,
            'visits': visits_count,
            'is_eligible': is_eligible
        })
        
    data = {
        'success': True,
        'customer': {
            'id': str(customer.id),
            'name': customer.name,
            'type': customer.customer_type.name if customer.customer_type else 'Regular',
            'phone': customer.phone,
            'vehicles': vehicles_data
        }
    }
    
    return JsonResponse(data)

from master.models import VehicleType
from service_management.models import BranchService, BranchVehiclePrice, ServiceVehicleTypePrice
from tax_management.models import Tax
from finance_management.models import Invoice, InvoiceItem

@csrf_exempt
def api_get_services(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    customer_id = request.GET.get('customer_id')
    vehicle_id = request.GET.get('vehicle_id')
    
    if not customer_id or not vehicle_id:
        return JsonResponse({'success': False, 'message': 'customer_id and vehicle_id are required'}, status=400)
        
    try:
        customer = Customer.objects.get(id=customer_id, is_deleted=False)
        vehicle = CustomerVehicle.objects.get(id=vehicle_id, customer=customer, is_deleted=False)
        
        branch = customer.branch
        vehicle_type = vehicle.vehicle_type_model.vehicle_type if vehicle.vehicle_type_model else None
        
        if not branch or not vehicle_type:
            return JsonResponse({'success': False, 'message': 'Customer branch or vehicle type is missing'}, status=400)
            
        # Get enabled Service IDs for this branch
        from service_management.models import Service as ServiceModel
        enabled_service_ids = BranchService.objects.filter(
            branch=branch, is_enabled=True, is_deleted=False
        ).values_list('service_id', flat=True)

        # Get individual Service objects
        individual_services = ServiceModel.objects.filter(
            id__in=enabled_service_ids,
            is_active=True,
            is_deleted=False,
        ).select_related('service_type').order_by('service_type__name', 'name')

        services_data = []
        for svc in individual_services:
            # Look up price: branch + individual service + vehicle model
            price_obj = ServiceVehicleTypePrice.objects.filter(
                branch=branch,
                service=svc,
                vehicle_model=vehicle.vehicle_type_model,
                is_active=True,
                is_deleted=False,
            ).first()

            rate = float(price_obj.price) if price_obj else 0.0

            if price_obj is not None and rate > 0:
                services_data.append({
                    'id': str(svc.id),
                    'name': svc.name,
                    'service_type': svc.service_type.name,
                    'rate': rate,
                    'has_price': True,
                })
            
        # Tax - get company-enabled taxes only
        from tax_management.models import CompanyTax
        company = customer.company
        taxes_data = []
        if company:
            enabled_company_taxes = CompanyTax.objects.filter(
                company=company, is_enabled=True
            ).select_related('tax')
            for ct in enabled_company_taxes:
                taxes_data.append({
                    'id': str(ct.tax.id),
                    'name': ct.tax.name,
                    'percent': float(ct.tax.percent),
                })

        return JsonResponse({
            'success': True,
            'services': services_data,
            'taxes': taxes_data,
            'vehicle_type': vehicle_type.name if vehicle_type else '',
        })
        
    except (Customer.DoesNotExist, CustomerVehicle.DoesNotExist) as e:
        return JsonResponse({'success': False, 'message': 'Customer or Vehicle not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def send_invoice_whatsapp_background(invoice_id, base_url):
    try:
        from finance_management.models import Invoice
        from finance_management.views import generate_invoice_pdf_file
        from booking_management.api_views import send_whatsapp_simple
        from client_management.models import WhatsAppSetting
        
        invoice = Invoice.objects.get(id=invoice_id)
        
        # 1. Generate the PDF
        pdf_url = generate_invoice_pdf_file(invoice, base_url)
        
        # 2. Get customer details
        customer = invoice.customer
        phone_to_send = customer.whatsapp_number or customer.phone
        if not phone_to_send:
            return
            
        # Normalize the number (keep digits only, prepend 91 if 10 digits)
        cleaned_num = ''.join(filter(str.isdigit, str(phone_to_send)))
        if len(cleaned_num) == 10:
            cleaned_num = "91" + cleaned_num
        elif len(cleaned_num) > 10 and cleaned_num.startswith("0"):
            cleaned_num = cleaned_num[1:]
            
        # 3. Format message text
        company_name = invoice.branch.company.company_name if invoice.branch and invoice.branch.company else "Wash Pilot"
        currency = "₹"
        if invoice.branch and invoice.branch.company and invoice.branch.company.country:
            currency = getattr(invoice.branch.company.country, 'currency_symbol', '₹') or '₹'
            
        # Services summary
        services_list = []
        for item in invoice.items.all():
            services_list.append(f"- {item.service_name}")
        services_str = "\n".join(services_list)
        
        message_text = (
            f"Dear {customer.name},\n\n"
            f"Your invoice *{invoice.invoice_number}* has been generated successfully at {company_name}.\n\n"
            f"*Invoice Details:*\n"
            f"Vehicle: {invoice.vehicle.vehicle_number}\n"
            f"Services:\n{services_str}\n"
            f"Total: {currency}{invoice.total}\n"
            f"Paid: {currency}{invoice.amount_collected}\n"
            f"Balance: {currency}{invoice.total - invoice.amount_collected}\n\n"
            f"Please find the attached PDF invoice for your reference.\n"
            f"Thank you for choosing us!"
        )
        
        # 4. Fetch branch/company whatsapp setting
        company = invoice.branch.company if invoice.branch else None
        setting = None
        if company:
            setting = WhatsAppSetting.objects.filter(company=company).first()
            
        # Only dispatch WhatsApp message if setting exists and has configured credentials
        if not setting or not setting.username or not setting.password:
            return
            
        # 5. Dispatch
        if setting.sender_id == '919496007007':
            from booking_management.api_views import send_whatsapp_template
            # The 'newjobcash' template expects:
            # {{1}} = Customer Name
            # {{2}} = Invoice Number
            # {{3}} = Company Name
            # {{4}} = Vehicle Number
            # {{5}} = Services list string
            # {{6}} = Total
            # {{7}} = Paid
            # {{8}} = Balance
            values = [
                customer.name,
                invoice.invoice_number,
                company_name,
                invoice.vehicle.vehicle_number if invoice.vehicle else "your vehicle",
                services_str,
                f"{currency}{invoice.total}",
                f"{currency}{invoice.amount_collected}",
                f"{currency}{invoice.total - invoice.amount_collected}"
            ]
            send_whatsapp_template(
                to_number=cleaned_num,
                template_name='invoice',
                values=values,
                doc_url=pdf_url,
                setting=setting
            )
        else:
            send_whatsapp_simple(
                to_number=cleaned_num,
                message=message_text,
                setting=setting,
                media_url=pdf_url
            )
        
    except Exception as e:
        import traceback
        try:
            with open('/tmp/whatsapp_webhook.log', 'a') as f:
                from datetime import datetime
                f.write(f"[{datetime.now()}] BG ERROR for invoice {invoice_id}: {str(e)}\n{traceback.format_exc()}\n")
        except Exception:
            pass


@csrf_exempt
def api_create_invoice(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        vehicle_id = data.get('vehicle_id')
        
        if not customer_id or not vehicle_id:
            return JsonResponse({'success': False, 'message': 'customer_id and vehicle_id are required'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        customer_qs = Customer.objects.filter(id=customer_id, is_deleted=False)
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            customer_qs = customer_qs.filter(branch=user.managed_branch)
        elif role == 'COMPANY_ADMIN' and user.profile.company:
            customer_qs = customer_qs.filter(company=user.profile.company)

        customer = customer_qs.get()
        vehicle = CustomerVehicle.objects.get(id=vehicle_id, customer=customer, is_deleted=False)
        
        # Generate invoice number using a unique branch-specific prefix and sequence.
        branch = user.managed_branch if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') else customer.branch
        prefix = _resolve_branch_invoice_prefix(branch)

        prefix_base = f"INV-{prefix}{branch.auto_id}-"
        last_invoice = (
            Invoice.objects.filter(branch=branch, invoice_number__startswith=prefix_base)
            .order_by('-auto_id')
            .first()
        )

        next_sequence = 1
        if last_invoice:
            try:
                next_sequence = int(last_invoice.invoice_number.rsplit('-', 1)[-1]) + 1
            except (TypeError, ValueError):
                next_sequence = (
                    Invoice.objects.filter(
                        branch=branch,
                        invoice_number__startswith=prefix_base,
                    ).count()
                    + 1
                )

        inv_number = f"{prefix_base}{next_sequence}"
        while Invoice.objects.filter(invoice_number=inv_number).exists():
            next_sequence += 1
            inv_number = f"{prefix_base}{next_sequence}"
        
        scheme_id = data.get('scheme_id')
        scheme_obj = None
        if scheme_id:
            from client_management.models import Scheme
            scheme_obj = Scheme.objects.filter(id=scheme_id).first()
            
        from decimal import Decimal
        total_val = Decimal(str(data.get('total', 0)))
        amt_collected_val = Decimal(str(data.get('amount_collected', 0)))
        inv_type = 'cashinvoice' if amt_collected_val >= total_val else 'creditinvoice'

        invoice = Invoice.objects.create(
            invoice_number=inv_number,
            customer=customer,
            vehicle=vehicle,
            branch=branch,
            scheme=scheme_obj,
            subtotal=data.get('subtotal', 0),
            discount=data.get('discount', 0),
            tax_amount=data.get('tax_amount', 0),
            total=data.get('total', 0),
            amount_collected=data.get('amount_collected', 0),
            invoice_type=inv_type,
            creator=user,
            auto_id=get_auto_id(Invoice)
        )
        
        # Create Receipt if amount_collected > 0
        from finance_management.models import Receipt
        from decimal import Decimal
        amount_collected = Decimal(str(data.get('amount_collected', 0)))
        if amount_collected > 0:
            receipt_auto_id = get_auto_id(Receipt)
            receipt_number = f"RCPT-{str(receipt_auto_id).zfill(5)}"
            Receipt.objects.create(
                auto_id=receipt_auto_id,
                creator=user,
                receipt_number=receipt_number,
                invoice=invoice,
                amount=amount_collected,
                payment_mode=data.get('payment_mode') or 'cash',
                remarks=data.get('remarks') or 'Invoice time collection'
            )
        
        # Create Items
        services_list = data.get('services', [])
        for svc in services_list:
            from service_management.models import Service
            try:
                service_obj = Service.objects.get(id=svc.get('id'))
            except Service.DoesNotExist:
                service_obj = None
                
            InvoiceItem.objects.create(
                invoice=invoice,
                service=service_obj,
                service_name=svc.get('name', 'Unknown Service'),
                rate=svc.get('rate', 0),
                discount=svc.get('discount', 0),  # per-item scheme/manual discount
                creator=user,
                auto_id=get_auto_id(InvoiceItem)
            )
            
        booking_id = data.get('booking_id')
        if booking_id:
            from booking_management.models import Booking
            try:
                booking = Booking.objects.get(id=booking_id)
                booking.status = Booking.STATUS_COMPLETED
                booking.save()
                
                # Trigger ready alert automatically on completion
                import threading
                from booking_management.api_views import send_booking_ready_alert_background
                threading.Thread(
                    target=send_booking_ready_alert_background,
                    args=(str(booking.id),),
                    daemon=True
                ).start()
            except Booking.DoesNotExist:
                pass
            
        # Trigger async WhatsApp send
        import threading
        base_url = request.build_absolute_uri('/')
        threading.Thread(
            target=send_invoice_whatsapp_background,
            args=(invoice.id, base_url),
            daemon=True
        ).start()
            
        company_logo = request.build_absolute_uri(invoice.branch.company.logo_color.url) if invoice.branch and invoice.branch.company and invoice.branch.company.logo_color else ''
        branch_logo = request.build_absolute_uri(invoice.branch.logo.url) if invoice.branch and invoice.branch.logo else ''

        return JsonResponse({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice_id': str(invoice.id),
            'invoice_number': invoice.invoice_number,
            'company_logo': company_logo,
            'branch_logo': branch_logo,
            'branch': invoice.branch.name if invoice.branch else '',
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_send_invoice_whatsapp(request):
    """Trigger WhatsApp invoice message manually for a given invoice_id."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        import json
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id', '')

        from finance_management.models import Invoice
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invoice not found'}, status=404)

        from client_management.models import WhatsAppSetting
        company = invoice.branch.company if invoice.branch else None
        setting = None
        if company:
            setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()

        has_api = bool(setting and setting.username and setting.password)

        if has_api:
            # Trigger background task
            import threading
            base_url = request.build_absolute_uri('/')
            threading.Thread(
                target=send_invoice_whatsapp_background,
                args=(invoice.id, base_url),
                daemon=True
            ).start()

            return JsonResponse({
                'success': True,
                'action': 'auto',
                'message': 'Invoice sent successfully via WhatsApp API'
            })
        else:
            return JsonResponse({
                'success': True,
                'action': 'manual',
                'message': 'WhatsApp API is not configured',
            })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_vehicle_search_list(request):
    """Partial vehicle number search — returns a list of matching vehicles (for auto-suggest)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    query = request.GET.get('q', '').strip().upper()
    if not query or len(query) < 2:
        return JsonResponse({'success': True, 'vehicles': []})

    company = user.profile.company

    from django.db.models.functions import Replace
    from django.db.models import Value

    clean_query = query.replace(' ', '')

    vehicles_qs = CustomerVehicle.objects.annotate(
        clean_vnum=Replace('vehicle_number', Value(' '), Value(''))
    ).filter(
        clean_vnum__icontains=clean_query,
        customer__company=company,
        is_deleted=False,
    ).select_related('customer', 'vehicle_type_model', 'vehicle_type_model__vehicle_type')

    if user.profile.role.name == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        vehicles_qs = vehicles_qs.filter(customer__branch=user.managed_branch)

    results = []
    for v in vehicles_qs[:20]:  # limit to 20 suggestions
        results.append({
            'vehicle_number': v.vehicle_number,
            'customer_name': v.customer.name if v.customer else '',
            'customer_phone': v.customer.phone if v.customer else '',
            'vehicle_model': v.vehicle_type_model.name if v.vehicle_type_model else '',
        })

    return JsonResponse({'success': True, 'vehicles': results})


@csrf_exempt
def api_vehicle_search(request):
    """Search a vehicle by its number and return owner + visit + scheme info."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    vehicle_number = request.GET.get('vehicle_number', '').strip().upper()
    if not vehicle_number:
        return JsonResponse({'success': False, 'message': 'vehicle_number is required'}, status=400)

    company = user.profile.company

    from django.db.models.functions import Replace
    from django.db.models import Value

    clean_query = vehicle_number.replace(' ', '')

    # Scope vehicles to the company's customers with space-insensitive match
    vehicles = CustomerVehicle.objects.annotate(
        clean_vehicle_number=Replace('vehicle_number', Value(' '), Value(''))
    ).filter(
        clean_vehicle_number__iexact=clean_query,
        customer__company=company,
        is_deleted=False,
    ).select_related('customer', 'customer__customer_type', 'customer__branch', 'vehicle_type_model', 'vehicle_type_model__vehicle_type')

    # Branch admin: only their branch
    if user.profile.role.name == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        vehicles = vehicles.filter(customer__branch=user.managed_branch)

    vehicle = vehicles.first()
    if not vehicle:
        return JsonResponse({'success': False, 'message': 'Vehicle not found'}, status=404)

    customer = vehicle.customer
    today = timezone.now().date()

    # Count visits from invoices
    from finance_management.models import Invoice
    visits_count = Invoice.objects.filter(vehicle=vehicle, is_deleted=False).count()

    # Scheme eligibility
    scheme_name = None
    paid_visits = 0
    free_visits = 0
    is_eligible = False

    if customer.branch and customer.branch.scheme_types.exists() and customer.customer_type and vehicle.vehicle_type_model and vehicle.vehicle_type_model.vehicle_type:
        scheme = Scheme.objects.filter(
            company=company,
            start_date__lte=today,
            end_date__gte=today,
            customer_types=customer.customer_type,
            vehicle_types=vehicle.vehicle_type_model.vehicle_type,
            is_deleted=False
        ).first()

        if scheme:
            scheme_name = scheme.name
            paid_visits = scheme.paid_visits or 0
            free_visits = scheme.free_visits or 0
            if paid_visits > 0 and visits_count >= paid_visits:
                is_eligible = True

    return JsonResponse({
        'success': True,
        'vehicle': {
            'id': str(vehicle.id),
            'number': vehicle.vehicle_number,
            'model': vehicle.vehicle_type_model.name if vehicle.vehicle_type_model else 'Unknown',
            'vehicle_type': vehicle.vehicle_type_model.vehicle_type.name if vehicle.vehicle_type_model and vehicle.vehicle_type_model.vehicle_type else '',
        },
        'customer': {
            'id': str(customer.id),
            'name': customer.name,
            'phone': customer.phone,
            'whatsapp': customer.whatsapp_number or '',
            'type': customer.customer_type.name if customer.customer_type else 'Regular',
            'branch': customer.branch.name if customer.branch else '',
        },
        'visits': {
            'total_visits': visits_count,
            'scheme_name': scheme_name,
            'paid_visits': paid_visits,
            'free_visits': free_visits,
            'is_eligible': is_eligible,
        }
    })


@csrf_exempt
def api_get_form_data(request):
    """Returns customer types and vehicle hierarchy data for the add-customer form."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from master.models import VehicleTypeModel, VehicleType, VehicleColor, VehicleBrandModel
    from .models import CustomerType, Branch

    customer_types = CustomerType.objects.filter(is_deleted=False)

    # --- Vehicle Types (branch-filtered) ---
    role = user.profile.role.name if user.profile.role else None
    branch = None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        branch = user.managed_branch

    if branch and branch.enabled_vehicle_types.exists():
        vehicle_types_qs = branch.enabled_vehicle_types.filter(is_active=True, is_deleted=False).order_by('name')
    else:
        vehicle_types_qs = VehicleType.objects.filter(is_active=True, is_deleted=False).order_by('name')

    # --- Vehicle Segments (per vehicle type) ---
    vehicle_type_models_qs = VehicleTypeModel.objects.filter(
        vehicle_type__in=vehicle_types_qs, is_active=True, is_deleted=False
    ).select_related('vehicle_type').order_by('vehicle_type__name', 'name')

    # --- Brand Models (per segment) ---
    brand_models_qs = VehicleBrandModel.objects.filter(
        vehicle_type_model__in=vehicle_type_models_qs, is_active=True, is_deleted=False
    ).select_related('vehicle_type_model', 'make').order_by('vehicle_type_model__name', 'name')

    # --- Makes ---
    from master.models import VehicleMake
    makes_qs = VehicleMake.objects.filter(is_active=True, is_deleted=False).order_by('name')

    # --- Colors ---
    colors_qs = VehicleColor.objects.filter(is_deleted=False).order_by('name')

    # Legacy vehicle_models for backward compatibility (segments grouped by type)
    legacy_vehicle_models = [
        {'id': str(vm.id), 'name': vm.name, 'vehicle_type': vm.vehicle_type.name, 'vehicle_type_id': str(vm.vehicle_type.id)}
        for vm in vehicle_type_models_qs
    ]

    branches_data = []
    if role == 'COMPANY_ADMIN' and user.profile.company:
        branches = user.profile.company.branches.filter(is_deleted=False).order_by('name')
        branches_data = [{'id': str(b.id), 'name': b.name} for b in branches]

    return JsonResponse({
        'success': True,
        'customer_types': [{'id': str(ct.id), 'name': ct.name} for ct in customer_types],
        # New hierarchy data
        'vehicle_types': [{'id': str(vt.id), 'name': vt.name} for vt in vehicle_types_qs],
        'vehicle_type_models': legacy_vehicle_models,
        'makes': [{'id': str(mk.id), 'name': mk.name} for mk in makes_qs],
        'brand_models': [
            {
                'id': str(bm.id),
                'name': bm.name,
                'vehicle_type_model_id': str(bm.vehicle_type_model.id),
                'make_id': str(bm.make.id) if bm.make else '',
            }
            for bm in brand_models_qs
        ],
        'colors': [{'id': str(c.id), 'name': c.name} for c in colors_qs],
        # Legacy field (still used by other screens)
        'vehicle_models': legacy_vehicle_models,
        'branches': branches_data,
    })




@csrf_exempt
def api_add_customer(request):
    """Creates a new customer with one or more vehicles."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)

        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        customer_type_id = data.get('customer_type_id')
        vehicles = data.get('vehicles', [])

        if not name or not phone or not customer_type_id:
            return JsonResponse({'success': False, 'message': 'Name, phone, and customer type are required'}, status=400)
        if not vehicles:
            return JsonResponse({'success': False, 'message': 'At least one vehicle is required'}, status=400)

        # Determine branch
        branch = None
        role = user.profile.role.name if user.profile.role else None
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            branch = user.managed_branch
        elif role == 'COMPANY_ADMIN':
            branch_id = data.get('branch_id')
            if branch_id:
                from .models import Branch
                branch = Branch.objects.filter(id=branch_id, is_deleted=False).first()
            else:
                branch = user.profile.company.branches.filter(is_deleted=False).first()

        if not branch:
            return JsonResponse({'success': False, 'message': 'No branch found for this user'}, status=400)

        company = user.profile.company

        if Customer.objects.filter(phone=phone, company=company, is_deleted=False).exists():
            return JsonResponse({'success': False, 'message': 'A customer with this phone number already exists'}, status=400)

        from .models import CustomerType, CustomerVehicle
        from master.models import VehicleTypeModel
        from core.functions import get_auto_id
        from django.db import transaction

        customer_type = CustomerType.objects.filter(id=customer_type_id, is_deleted=False).first()
        if not customer_type:
            return JsonResponse({'success': False, 'message': 'Invalid customer type'}, status=400)

        with transaction.atomic():
            customer = Customer.objects.create(
                company=company,
                branch=branch,
                name=name,
                phone=phone,
                customer_type=customer_type,
                whatsapp_number=data.get('whatsapp_number', '').strip() or None,
                email=data.get('email', '').strip() or None,
                address=data.get('address', '').strip() or None,
                creator=user,
                auto_id=get_auto_id(Customer),
            )

            vehicles_data = []
            for v in vehicles:
                vehicle_number = v.get('vehicle_number', '').strip().upper()
                vehicle_model_id = v.get('vehicle_model_id')
                brand_model_id = v.get('brand_model_id')
                make_id = v.get('make_id')
                color_id = v.get('color_id')
                if not vehicle_number or not vehicle_model_id:
                    continue
                vm = VehicleTypeModel.objects.filter(id=vehicle_model_id, is_deleted=False).first()
                if not vm:
                    continue

                # Optional brand model and make
                from master.models import VehicleBrandModel, VehicleColor, VehicleMake
                brand_model = None
                if brand_model_id:
                    brand_model = VehicleBrandModel.objects.filter(id=brand_model_id, is_deleted=False).first()

                make = None
                if make_id:
                    make = VehicleMake.objects.filter(id=make_id, is_deleted=False).first()

                # Optional color
                color = None
                if color_id:
                    color = VehicleColor.objects.filter(id=color_id, is_deleted=False).first()

                cv = CustomerVehicle.objects.create(
                    customer=customer,
                    vehicle_type_model=vm,
                    vehicle_type=vm.vehicle_type if vm else None,
                    vehicle_number=vehicle_number,
                    make=make,
                    brand_model=brand_model,
                    color=color,
                    creator=user,
                    auto_id=get_auto_id(CustomerVehicle),
                )
                vehicles_data.append({
                    'id': str(cv.id),
                    'no': cv.vehicle_number,
                    'type': vm.name,
                    'vehicle_type': vm.vehicle_type.name if vm.vehicle_type else '',
                    'make': make.name if make else '',
                    'brand_model': brand_model.name if brand_model else '',
                    'color': color.name if color else '',
                })

        # Check WhatsApp settings configuration
        from client_management.models import WhatsAppSetting
        has_api = False
        setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
        if setting and setting.username and setting.password:
            has_api = True

        if has_api:
            # Send automatically in background
            def send_welcome_message():
                try:
                    from booking_management.api_views import send_whatsapp_simple, send_whatsapp_template
                    import re
                    phone_to_send = customer.whatsapp_number or customer.phone
                    cleaned_num = re.sub(r'\D', '', str(phone_to_send))
                    if len(cleaned_num) == 10:
                        cleaned_num = "91" + cleaned_num
                    elif len(cleaned_num) > 10 and cleaned_num.startswith("0"):
                        cleaned_num = cleaned_num[1:]
                    
                    branch_name = branch.name or "our branch"
                    
                    # Fetch first vehicle number if available
                    vehicle_no = ""
                    first_vehicle = customer.vehicles.filter(is_deleted=False).first()
                    if first_vehicle:
                        vehicle_no = first_vehicle.vehicle_number
                    
                    if setting.sender_id == '919496007007':
                        values = [customer.name, branch_name, vehicle_no]
                        send_whatsapp_template(
                            to_number=cleaned_num,
                            template_name='welcoming',
                            values=values,
                            setting=setting
                        )
                    else:
                        message_text = f"Dear {customer.name}, Thank you for choosing {branch_name}."
                        send_whatsapp_simple(
                            to_number=cleaned_num,
                            message=message_text,
                            setting=setting
                        )
                except Exception as e:
                    with open('/tmp/welcome_message_error.log', 'a') as f:
                        f.write(f"Error sending welcome message for customer {customer.id}: {str(e)}\n")

            import threading
            threading.Thread(target=send_welcome_message, daemon=True).start()
            whatsapp_action = 'auto'
        else:
            whatsapp_action = 'manual'

        return JsonResponse({
            'success': True,
            'message': 'Customer added successfully',
            'whatsapp_action': whatsapp_action,
            'customer': {
                'id': str(customer.id),
                'name': customer.name,
                'phone': customer.phone,
                'whatsapp_number': customer.whatsapp_number or customer.phone,
                'branch_name': branch.name or "our branch",
                'type': customer_type.name,
                'vehicles': vehicles_data,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)



@csrf_exempt
def api_list_customers(request):
    """List all customers for the branch/company (for mobile customer list)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        company = user.profile.company
        role = user.profile.role.name if user.profile.role else None

        customers_qs = Customer.objects.filter(company=company, is_deleted=False).order_by('name')
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            customers_qs = customers_qs.filter(branch=user.managed_branch)

        from django.db.models import Max
        customers_qs = customers_qs.annotate(last_invoice_date=Max('invoices__date'))

        search = request.GET.get('search', '').strip()
        if search:
            from django.db.models import Q
            customers_qs = customers_qs.filter(
                Q(name__icontains=search) | Q(phone__icontains=search)
            )

        customers_data = []
        for c in customers_qs.select_related('customer_type'):
            customers_data.append({
                'id': str(c.id),
                'name': c.name,
                'phone': c.phone,
                'customer_type': c.customer_type.name if c.customer_type else '',
                'vehicle_count': c.vehicles.filter(is_deleted=False).count(),
                'date_added': c.date_added.strftime('%Y-%m-%d') if c.date_added else '',
                'last_invoice_date': c.last_invoice_date.strftime('%Y-%m-%d') if c.last_invoice_date else '',
            })

        return JsonResponse({'success': True, 'customers': customers_data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_inactive_customers(request):
    """Return customers who have not had any invoice in the last N days (default 60)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        from django.utils.timezone import now
        from datetime import timedelta
        from django.db.models import Max, Q

        company = user.profile.company
        role = user.profile.role.name if user.profile.role else None
        inactive_days = int(request.GET.get('days', 60))
        cutoff_date = now().date() - timedelta(days=inactive_days)

        customers_qs = Customer.objects.filter(
            company=company, is_deleted=False
        ).annotate(
            last_invoice_date=Max('invoices__date')
        ).filter(
            Q(last_invoice_date__lt=cutoff_date) | Q(last_invoice_date__isnull=True)
        ).order_by('name')

        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
            customers_qs = customers_qs.filter(branch=user.managed_branch)

        customers_data = []
        for c in customers_qs.prefetch_related('vehicles'):
            first_vehicle = c.vehicles.filter(is_deleted=False).first()
            customers_data.append({
                'id': str(c.id),
                'name': c.name,
                'phone': c.whatsapp_number or c.phone,
                'vehicle_number': first_vehicle.vehicle_number if first_vehicle else '',
                'branch': c.branch.name if c.branch else '',
                'last_invoice_date': c.last_invoice_date.strftime('%Y-%m-%d') if c.last_invoice_date else 'Never',
                'inactive_days': inactive_days,
            })

        return JsonResponse({
            'success': True,
            'customers': customers_data,
            'total': len(customers_data),
            'inactive_days': inactive_days,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_whatsapp_templates(request):
    """Return WhatsApp templates for the company (for mobile broadcast screen)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        from .models import WhatsAppTemplate, WhatsAppSetting
        company = user.profile.company

        templates = WhatsAppTemplate.objects.filter(
            company=company, is_deleted=False
        ).select_related('whatsapp_type').order_by('template_name')

        # Get booking WhatsApp number
        wa_number = ''
        try:
            setting = WhatsAppSetting.objects.get(company=company)
            wa_number = setting.whatsapp_number or setting.sender_id or ''
        except WhatsAppSetting.DoesNotExist:
            pass

        templates_data = [
            {
                'id': str(t.id),
                'name': t.template_name,
                'content': t.content,
                'type': t.whatsapp_type.name if t.whatsapp_type else '',
            }
            for t in templates
        ]

        return JsonResponse({
            'success': True,
            'templates': templates_data,
            'booking_wa_number': wa_number,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_whatsapp_broadcast(request):
    """
    Automatically send WhatsApp messages to customers using the wawy.org API.
    POST body:
      {
        "recipient_type": "all_customers" | "specific_customers" | "inactive_customers",
        "customer_ids": ["id1", "id2"],   // only for specific_customers
        "inactive_days": 60,              // only for inactive_customers
        "message": "Dear {{1}}, ...",     // raw template with {{1}}-{{5}} placeholders
        "var_2": "Car Wash"               // value for {{2}}
      }
    Returns:
      { "success": true, "sent": 12, "failed": 0, "errors": [] }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        import json
        from django.db.models import Max, Q
        from django.utils.timezone import now
        from datetime import timedelta
        from .models import WhatsAppSetting, WhatsAppMessage
        from booking_management.api_views import send_whatsapp_simple

        data = json.loads(request.body)
        recipient_type = data.get('recipient_type', 'all_customers')
        message_template = data.get('message', '').strip()
        var_2 = data.get('var_2', '').strip()

        if not message_template:
            return JsonResponse({'success': False, 'message': 'Message cannot be empty'}, status=400)

        company = user.profile.company

        # Get WhatsApp settings for this company
        wa_setting = None
        booking_wa_number = ''
        try:
            wa_setting = WhatsAppSetting.objects.get(company=company)
            booking_wa_number = wa_setting.whatsapp_number or wa_setting.sender_id or ''
        except WhatsAppSetting.DoesNotExist:
            pass

        # Build customer queryset
        base_qs = Customer.objects.filter(
            company=company, is_deleted=False
        ).prefetch_related('vehicles').select_related('branch')

        if recipient_type == 'specific_customers':
            customer_ids = data.get('customer_ids', [])
            if not customer_ids:
                return JsonResponse({'success': False, 'message': 'No customer IDs provided'}, status=400)
            customers = base_qs.filter(id__in=customer_ids)

        elif recipient_type == 'inactive_customers':
            inactive_days = int(data.get('inactive_days', 60))
            cutoff = now().date() - timedelta(days=inactive_days)
            customers = base_qs.annotate(
                last_inv=Max('invoices__date')
            ).filter(
                Q(last_inv__lt=cutoff) | Q(last_inv__isnull=True)
            )

        else:  # all_customers
            customers = base_qs

        # Helper to fill template variables per customer
        def fill_message(customer):
            name = customer.name or ''
            vehicle_no = ''
            first_v = customer.vehicles.filter(is_deleted=False).first()
            if first_v:
                vehicle_no = first_v.vehicle_number or ''
            branch = customer.branch.name if customer.branch else ''
            return (
                message_template
                .replace('{{1}}', name)
                .replace('{{2}}', var_2)
                .replace('{{3}}', vehicle_no)
                .replace('{{4}}', booking_wa_number)
                .replace('{{5}}', branch)
            )

        # Helper to normalise phone number
        def clean_phone(phone):
            phone = (phone or '').replace(' ', '').replace('+', '').replace('-', '')
            if len(phone) == 10:
                phone = '91' + phone
            return phone

        sent = 0
        failed = 0
        errors = []

        import time

        for customer in customers:
            # Use whatsapp_number first, fall back to phone
            raw_phone = customer.whatsapp_number or customer.phone or ''
            phone = clean_phone(raw_phone)
            if not phone:
                failed += 1
                errors.append(f"{customer.name}: no phone number")
                continue

            final_msg = fill_message(customer)

            try:
                result = send_whatsapp_simple(phone, final_msg, setting=wa_setting)

                # Log to WhatsAppMessage
                try:
                    from core.functions import get_auto_id as _get_auto_id
                    WhatsAppMessage.objects.create(
                        company=company,
                        auto_id=_get_auto_id(WhatsAppMessage),
                        recipient_name=customer.name,
                        recipient_number=phone,
                        message=final_msg,
                        status='sent',
                    )
                except Exception:
                    pass

                sent += 1

            except Exception as e:
                failed += 1
                errors.append(f"{customer.name} ({phone}): {str(e)}")

            # ⏱ Delay between messages to avoid rate limiting on wawy.org
            time.sleep(1)

        return JsonResponse({
            'success': True,
            'sent': sent,
            'failed': failed,
            'total': sent + failed,
            'errors': errors[:10],
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_get_customer(request):

    """Fetch full customer details for editing on mobile."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    customer_id = request.GET.get('customer_id', '').strip()
    if not customer_id:
        return JsonResponse({'success': False, 'message': 'customer_id is required'}, status=400)

    try:
        company = user.profile.company
        customer = Customer.objects.get(id=customer_id, company=company, is_deleted=False)

        vehicles_data = []
        for v in customer.vehicles.filter(is_deleted=False):
            vehicles_data.append({
                'id': str(v.id),
                'vehicle_number': v.vehicle_number,
                'vehicle_model_id': str(v.vehicle_type_model.id) if v.vehicle_type_model else None,
                'vehicle_model_name': v.vehicle_type_model.name if v.vehicle_type_model else '',
            })

        return JsonResponse({
            'success': True,
            'customer': {
                'id': str(customer.id),
                'name': customer.name,
                'phone': customer.phone,
                'whatsapp_number': customer.whatsapp_number or '',
                'email': customer.email or '',
                'address': customer.address or '',
                'customer_type_id': str(customer.customer_type.id) if customer.customer_type else None,
                'customer_type_name': customer.customer_type.name if customer.customer_type else '',
                'vehicles': vehicles_data,
            }
        })
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_edit_customer(request):
    """Update customer basic info, phone, existing vehicles, and add new vehicles."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id', '').strip()
        name = data.get('name', '').strip()
        customer_type_id = data.get('customer_type_id')
        new_vehicles = data.get('new_vehicles', [])
        updated_vehicles = data.get('updated_vehicles', [])  # list of {id, vehicle_number, vehicle_model_id}
        new_phone = data.get('phone', '').strip()

        if not customer_id or not name or not customer_type_id:
            return JsonResponse({'success': False, 'message': 'customer_id, name, and customer_type are required'}, status=400)

        company = user.profile.company
        customer = Customer.objects.get(id=customer_id, company=company, is_deleted=False)

        from .models import CustomerType, CustomerVehicle
        from master.models import VehicleTypeModel
        from core.functions import get_auto_id
        from django.db import transaction

        customer_type = CustomerType.objects.filter(id=customer_type_id, is_deleted=False).first()
        if not customer_type:
            return JsonResponse({'success': False, 'message': 'Invalid customer type'}, status=400)

        # Check phone uniqueness if changed
        if new_phone and new_phone != customer.phone:
            if Customer.objects.filter(phone=new_phone, company=company, is_deleted=False).exclude(id=customer_id).exists():
                return JsonResponse({'success': False, 'message': 'Another customer with this phone number already exists'}, status=400)

        with transaction.atomic():
            customer.name = name
            customer.customer_type = customer_type
            customer.whatsapp_number = data.get('whatsapp_number', '').strip() or None
            customer.email = data.get('email', '').strip() or None
            customer.address = data.get('address', '').strip() or None
            if new_phone:
                customer.phone = new_phone
            customer.save()

            # Update existing vehicles
            for v in updated_vehicles:
                vehicle_id = v.get('id')
                vehicle_number = v.get('vehicle_number', '').strip().upper()
                vehicle_model_id = v.get('vehicle_model_id')
                if not vehicle_id or not vehicle_number:
                    continue
                cv = CustomerVehicle.objects.filter(id=vehicle_id, customer=customer, is_deleted=False).first()
                if not cv:
                    continue
                if vehicle_number:
                    cv.vehicle_number = vehicle_number
                if vehicle_model_id:
                    vm = VehicleTypeModel.objects.filter(id=vehicle_model_id, is_deleted=False).first()
                    if vm:
                        cv.vehicle_type_model = vm
                        cv.vehicle_type = vm.vehicle_type
                cv.save()

            # Add new vehicles
            for v in new_vehicles:
                vehicle_number = v.get('vehicle_number', '').strip().upper()
                vehicle_model_id = v.get('vehicle_model_id')
                brand_model_id = v.get('brand_model_id')
                make_id = v.get('make_id')
                color_id = v.get('color_id')
                if not vehicle_number or not vehicle_model_id:
                    continue
                vm = VehicleTypeModel.objects.filter(id=vehicle_model_id, is_deleted=False).first()
                if not vm:
                    continue

                from master.models import VehicleBrandModel, VehicleColor, VehicleMake
                brand_model = None
                if brand_model_id:
                    brand_model = VehicleBrandModel.objects.filter(id=brand_model_id, is_deleted=False).first()
                make = None
                if make_id:
                    make = VehicleMake.objects.filter(id=make_id, is_deleted=False).first()
                color = None
                if color_id:
                    color = VehicleColor.objects.filter(id=color_id, is_deleted=False).first()

                CustomerVehicle.objects.create(
                    customer=customer,
                    vehicle_type_model=vm,
                    vehicle_type=vm.vehicle_type if vm else None,
                    vehicle_number=vehicle_number,
                    make=make,
                    brand_model=brand_model,
                    color=color,
                    creator=user,
                    auto_id=get_auto_id(CustomerVehicle),
                )


        return JsonResponse({'success': True, 'message': 'Customer updated successfully'})

    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_available_schemes(request):
    """Return available schemes for a customer + vehicle + service for invoice creation."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    customer_id = request.GET.get('customer_id')
    vehicle_id = request.GET.get('vehicle_id')
    service_id = request.GET.get('service_id')
    if not customer_id or not vehicle_id or not service_id:
        return JsonResponse({'success': False, 'message': 'customer_id, vehicle_id and service_id required'}, status=400)

    try:
        company = user.profile.company
        customer = Customer.objects.get(id=customer_id, company=company, is_deleted=False)
        vehicle = CustomerVehicle.objects.select_related(
            'vehicle_type_model', 'vehicle_type_model__vehicle_type'
        ).get(id=vehicle_id, customer=customer, is_deleted=False)
        service = Service.objects.get(id=service_id, is_deleted=False)

        from finance_management.models import Invoice
        today = timezone.now().date()

        # Eligible schemes: active, matches customer type + vehicle type + service
        schemes_qs = Scheme.objects.filter(
            company=company,
            start_date__lte=today,
            end_date__gte=today,
            services=service,
            is_deleted=False,
        )
        if customer.customer_type:
            schemes_qs = schemes_qs.filter(customer_types=customer.customer_type)
        if vehicle.vehicle_type_model and vehicle.vehicle_type_model.vehicle_type:
            schemes_qs = schemes_qs.filter(vehicle_types=vehicle.vehicle_type_model.vehicle_type)
        
        # Filter by selected service
        service_id = request.GET.get('service_id')
        if service_id:
            schemes_qs = schemes_qs.filter(services__id=service_id)

        # Total paid visits for this vehicle (all invoices, not just scheme-free ones)
        total_paid_visits = Invoice.objects.filter(
            vehicle=vehicle, is_deleted=False
        ).count()

        result = []
        for scheme in schemes_qs.distinct():
            scheme_type = scheme.scheme_type.name if scheme.scheme_type else 'Quantity'
            entry = {
                'id': str(scheme.id),
                'name': scheme.name,
                'scheme_type': scheme_type,  # 'Quantity', 'Discount', 'Voucher'
            }

            if scheme_type == 'Quantity' or scheme_type == scheme.SCHEME_BENEFIT_QTY:
                paid = scheme.paid_visits or 0
                free = scheme.free_visits or 0

                # How many free washes this vehicle has already redeemed for this scheme
                free_washes_taken = Invoice.objects.filter(
                    vehicle=vehicle, scheme=scheme, is_deleted=False
                ).count()

                # Progress within the current cycle:
                # Each cycle = paid_visits normal washes + 1 free wash
                # Current cycle starts after the last completed cycle
                cycle_length = paid + free  # e.g. 3 paid + 1 free = cycle of 4
                completed_cycles = free_washes_taken  # each free wash = one cycle done
                visits_in_current_cycle = total_paid_visits - (completed_cycles * paid)
                if visits_in_current_cycle < 0:
                    visits_in_current_cycle = 0

                is_eligible = paid > 0 and visits_in_current_cycle >= paid
                entry.update({
                    'description': f'Get {free} free wash after every {paid} paid washes',
                    'paid_visits': paid,
                    'free_visits': free,
                    'visits_count': min(visits_in_current_cycle, paid),  # cap at paid for UI bar
                    'is_eligible': is_eligible,
                })

            elif scheme_type == 'Discount' or scheme_type == scheme.SCHEME_BENEFIT_DISCOUNT:
                pct = float(scheme.discount_percentage or 0)
                entry.update({
                    'description': f'Get {pct}% off on total bill',
                    'discount_percentage': pct,
                    'is_eligible': True,
                })
            elif scheme_type == 'Voucher' or scheme_type == scheme.SCHEME_BENEFIT_VOUCHER:
                entry.update({
                    'description': 'Use voucher code and get discount',
                    'is_eligible': True,
                    'requires_voucher': True,
                })

            result.append(entry)

        return JsonResponse({'success': True, 'schemes': result})

    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
    except CustomerVehicle.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Vehicle not found'}, status=404)
    except Service.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Service not found'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_validate_voucher(request):
    """Validate a voucher number for a scheme and return the discount."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        scheme_id = data.get('scheme_id')
        voucher_number = data.get('voucher_number', '').strip()

        if not scheme_id or not voucher_number:
            return JsonResponse({'success': False, 'message': 'scheme_id and voucher_number required'}, status=400)

        from .models import SchemeVoucher
        voucher = SchemeVoucher.objects.filter(
            scheme_id=scheme_id,
            voucher_number=voucher_number,
            is_deleted=False,
        ).first()

        currency_symbol = user.profile.company.country.currency_symbol if user.profile.company.country else '₹'
        if voucher:
            return JsonResponse({
                'success': True,
                'voucher_id': str(voucher.id),
                'discount': float(voucher.discount),
                'message': f'Voucher applied! {currency_symbol}{voucher.discount} off',
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid or already used voucher'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
def api_branch_schemes(request):
    """Return all active schemes for the branch or company."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    role = user.profile.role.name if user.profile.role else None
    
    from .models import Scheme
    schemes_qs = Scheme.objects.filter(is_deleted=False)

    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        # Branch can access schemes of its company, filtered by its active scheme types
        schemes_qs = schemes_qs.filter(company=user.managed_branch.company)
        schemes_qs = schemes_qs.filter(scheme_type__in=user.managed_branch.scheme_types.all())
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        schemes_qs = schemes_qs.filter(company=user.profile.company)

    result = []
    for scheme in schemes_qs.distinct():
        scheme_type = scheme.scheme_type.name if scheme.scheme_type else 'Quantity'
        
        services = ", ".join(scheme.services.values_list('name', flat=True)) if scheme.services.exists() else 'All Services'
        vehicle_types = ", ".join(scheme.vehicle_types.values_list('name', flat=True)) if scheme.vehicle_types.exists() else 'All Vehicles'
        customer_types = ", ".join(scheme.customer_types.values_list('name', flat=True)) if scheme.customer_types.exists() else 'All Customers'

        result.append({
            'id': str(scheme.id),
            'name': scheme.name,
            'scheme_type': scheme_type,
            'description': '',
            'start_date': str(scheme.start_date) if scheme.start_date else '',
            'end_date': str(scheme.end_date) if scheme.end_date else '',
            'services': services,
            'vehicle_types': vehicle_types,
            'customer_types': customer_types,
            'paid_visits': scheme.paid_visits or 0,
            'free_visits': scheme.free_visits or 0,
            'discount_percentage': str(scheme.discount_percentage or 0),
            'voucher_amount': '0',
        })

    return JsonResponse({'success': True, 'schemes': result})


def api_scheme_options(request):
    """Mobile API: options needed to create a company scheme."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN' or not user.profile.company:
        return JsonResponse({'success': False, 'message': 'Only Company Admin can add schemes'}, status=403)

    from service_management.models import CompanyService
    from master.models import VehicleType

    company = user.profile.company
    enabled_service_ids = CompanyService.objects.filter(
        company=company,
        is_enabled=True,
    ).values_list('service_id', flat=True)

    services = Service.objects.filter(
        id__in=enabled_service_ids,
        is_deleted=False,
        is_active=True,
    ).order_by('name')
    customer_types = CustomerType.objects.filter(is_deleted=False).order_by('name')
    vehicle_types = VehicleType.objects.filter(is_deleted=False, is_active=True).order_by('name')

    def serialize(items):
        return [{'id': str(item.id), 'name': item.name} for item in items]

    return JsonResponse({
        'success': True,
        'scheme_types': serialize(company.scheme_types.all().order_by('name')),
        'services': serialize(services),
        'customer_types': serialize(customer_types),
        'vehicle_types': serialize(vehicle_types),
    })


@csrf_exempt
def api_create_scheme(request):
    """Mobile API: create a scheme for the logged-in company."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN' or not user.profile.company:
        return JsonResponse({'success': False, 'message': 'Only Company Admin can add schemes'}, status=403)

    try:
        from datetime import datetime
        from decimal import Decimal
        from master.models import VehicleType
        from service_management.models import CompanyService

        data = json.loads(request.body)
        company = user.profile.company
        scheme_type_id = data.get('scheme_type_id')
        scheme_type = company.scheme_types.filter(id=scheme_type_id).first()
        if not scheme_type:
            return JsonResponse({'success': False, 'message': 'Select a valid scheme type'}, status=400)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'success': False, 'message': 'Scheme name is required'}, status=400)

        def parse_date(field):
            value = data.get(field)
            if not value:
                raise ValueError(f'{field.replace("_", " ").title()} is required')
            return datetime.strptime(value, '%Y-%m-%d').date()

        start_date = parse_date('start_date')
        end_date = parse_date('end_date')
        if end_date < start_date:
            return JsonResponse({'success': False, 'message': 'End date cannot be before start date'}, status=400)

        type_name = scheme_type.name.lower()
        paid_visits = data.get('paid_visits')
        free_visits = data.get('free_visits')
        discount_percentage = data.get('discount_percentage')
        vouchers = data.get('vouchers') or []

        if 'quantity' in type_name and (not paid_visits or not free_visits):
            return JsonResponse({'success': False, 'message': 'Enter paid and free visits'}, status=400)
        if 'discount' in type_name and not discount_percentage:
            return JsonResponse({'success': False, 'message': 'Enter discount percentage'}, status=400)
        if 'voucher' in type_name and not vouchers:
            return JsonResponse({'success': False, 'message': 'Add at least one voucher'}, status=400)

        scheme = Scheme.objects.create(
            company=company,
            scheme_type=scheme_type,
            name=name,
            start_date=start_date,
            end_date=end_date,
            paid_visits=paid_visits or None,
            free_visits=free_visits or None,
            discount_percentage=discount_percentage or None,
            auto_id=get_auto_id(Scheme),
            creator=user,
        )

        enabled_service_ids = set(CompanyService.objects.filter(
            company=company,
            is_enabled=True,
        ).values_list('service_id', flat=True))

        service_ids = [item for item in data.get('service_ids', []) if item]
        if service_ids:
            scheme.services.set(Service.objects.filter(id__in=service_ids).filter(id__in=enabled_service_ids))
        customer_type_ids = [item for item in data.get('customer_type_ids', []) if item]
        if customer_type_ids:
            scheme.customer_types.set(CustomerType.objects.filter(id__in=customer_type_ids, is_deleted=False))
        vehicle_type_ids = [item for item in data.get('vehicle_type_ids', []) if item]
        if vehicle_type_ids:
            scheme.vehicle_types.set(VehicleType.objects.filter(id__in=vehicle_type_ids, is_deleted=False, is_active=True))

        if 'voucher' in type_name:
            for voucher in vouchers:
                voucher_number = (voucher.get('voucher_number') or '').strip()
                discount = voucher.get('discount')
                if voucher_number and discount is not None:
                    SchemeVoucher.objects.create(
                        scheme=scheme,
                        voucher_number=voucher_number,
                        discount=Decimal(str(discount)),
                        auto_id=get_auto_id(SchemeVoucher),
                        creator=user,
                    )

        return JsonResponse({
            'success': True,
            'message': 'Scheme created successfully',
            'scheme_id': str(scheme.id),
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ──────────────────────────────────────────────────────────────────────────────
# REPORTS API
# ──────────────────────────────────────────────────────────────────────────────

def _report_scope(user, branch_id=None):
    """Returns (company, branch_filter_kwargs) for the logged-in user."""
    company = user.profile.company
    role = user.profile.role.name if user.profile.role else None
    qs_filter = {}
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        qs_filter['branch'] = user.managed_branch
    elif role == 'COMPANY_ADMIN':
        branch = _company_branch_from_request(user, branch_id)
        if branch:
            qs_filter['branch'] = branch
        else:
            qs_filter['branch__company'] = company
    return company, qs_filter


def _parse_dates(request):
    from datetime import date, datetime
    from_date_str = request.GET.get('from_date', '')
    to_date_str = request.GET.get('to_date', '')
    today = date.today()

    def parse_dt(dt_str, default_dt):
        if not dt_str:
            return default_dt
        try:
            return datetime.strptime(dt_str, '%d-%m-%Y').date()
        except ValueError:
            try:
                return date.fromisoformat(dt_str)
            except ValueError:
                return default_dt

    from_date = parse_dt(from_date_str, today.replace(day=1))
    to_date = parse_dt(to_date_str, today)
    return from_date, to_date


@csrf_exempt
def api_report_jobs(request):
    """Job report: all invoices in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import Invoice
    from django.db.models import Sum

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    qs = Invoice.objects.filter(
        is_deleted=False, date__gte=from_date, date__lte=to_date, **scope
    ).select_related('customer', 'vehicle', 'branch').order_by('-date', '-auto_id')

    rows = []
    for inv in qs:
        services = ', '.join(inv.items.values_list('service_name', flat=True))
        rows.append({
            'invoice_number': inv.invoice_number,
            'date': inv.date.strftime('%d-%m-%Y'),
            'customer': inv.customer.name,
            'phone': inv.customer.phone,
            'vehicle': inv.vehicle.vehicle_number if inv.vehicle else '',
            'branch': inv.branch.name if inv.branch else '',
            'services': services,
            'subtotal': str(inv.subtotal),
            'discount': str(inv.discount),
            'tax': str(inv.tax_amount),
            'total': str(inv.total),
            'collected': str(inv.amount_collected),
            'invoice_type': inv.invoice_type,
        })

    totals = qs.aggregate(
        total_jobs=models.Count('id'),
        total_revenue=Sum('total'),
        total_collected=Sum('amount_collected'),
        total_discount=Sum('discount'),
    )

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_jobs': totals['total_jobs'] or 0,
        'total_revenue': str(totals['total_revenue'] or 0),
        'total_collected': str(totals['total_collected'] or 0),
        'total_discount': str(totals['total_discount'] or 0),
        'rows': rows,
    })


@csrf_exempt
def api_report_scheme_beneficiary(request):
    """Scheme beneficiary report: invoices where a scheme was redeemed."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import Invoice
    from django.db.models import Sum, Count

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    qs = Invoice.objects.filter(
        is_deleted=False, date__gte=from_date, date__lte=to_date,
        scheme__isnull=False, **scope
    ).select_related('customer', 'vehicle', 'scheme', 'branch').order_by('-date', '-auto_id')

    rows = []
    for inv in qs:
        rows.append({
            'invoice_number': inv.invoice_number,
            'date': inv.date.strftime('%d-%m-%Y'),
            'customer': inv.customer.name,
            'phone': inv.customer.phone,
            'vehicle': inv.vehicle.vehicle_number if inv.vehicle else '',
            'scheme': inv.scheme.name if inv.scheme else '',
            'scheme_type': inv.scheme.scheme_type.name if inv.scheme and inv.scheme.scheme_type else '',
            'discount': str(inv.discount),
            'total': str(inv.total),
            'branch': inv.branch.name if inv.branch else '',
        })

    totals = qs.aggregate(
        total_count=Count('id'),
        total_discount=Sum('discount'),
    )

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_count': totals['total_count'] or 0,
        'total_discount': str(totals['total_discount'] or 0),
        'rows': rows,
    })


@csrf_exempt
def api_report_collection(request):
    """Collection report: returns all receipts within date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import Receipt
    from django.db.models import Sum

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    receipt_scope = {}
    if 'branch' in scope:
        receipt_scope['invoice__branch'] = scope['branch']
    elif 'branch__company' in scope:
        receipt_scope['invoice__branch__company'] = scope['branch__company']

    rec_qs = Receipt.objects.filter(
        created_at__date__gte=from_date,
        created_at__date__lte=to_date,
        **receipt_scope
    )

    payment_mode = request.GET.get('payment_mode')
    if payment_mode:
        rec_qs = rec_qs.filter(payment_mode=payment_mode)

    # Group by payment mode for summary (using all matching receipts BEFORE filtering by specific payment mode if filtered, or after? Wait, if the user has selected a specific payment mode filter, the summary should still show all or only filtered? Showing all or filtered makes sense either way, let's calculate the summary from the main query but respecting the branch/date scope)
    # Let's compute the summary based on branch & date scope (before specific payment mode filter, so the user can see all totals even if filtering)
    summary_qs = Receipt.objects.filter(
        created_at__date__gte=from_date,
        created_at__date__lte=to_date,
        **receipt_scope
    )
    grouped = summary_qs.values('payment_mode').annotate(total_amount=Sum('amount')).order_by('-total_amount')
    
    PAYMENT_LABELS = dict(Receipt.PAYMENT_CHOICES)
    summary = []
    for item in grouped:
        mode = item['payment_mode']
        amt = item['total_amount'] or 0
        summary.append({
            'payment_mode': mode,
            'payment_mode_display': PAYMENT_LABELS.get(mode, mode.title()),
            'total_amount': str(amt),
        })

    existing_modes = {item['payment_mode'] for item in grouped}
    for mode, label in Receipt.PAYMENT_CHOICES:
        if mode not in existing_modes:
            summary.append({
                'payment_mode': mode,
                'payment_mode_display': label,
                'total_amount': '0.00',
            })

    rec_qs = rec_qs.select_related('invoice', 'invoice__customer', 'invoice__vehicle', 'invoice__branch').order_by('-created_at')

    rows = []
    for rec in rec_qs:
        rows.append({
            'receipt_number': rec.receipt_number,
            'date': rec.created_at.date().strftime('%d-%m-%Y'),
            'invoice_number': rec.invoice.invoice_number,
            'customer': rec.invoice.customer.name,
            'phone': rec.invoice.customer.phone,
            'vehicle': rec.invoice.vehicle.vehicle_number if rec.invoice.vehicle else '',
            'branch': rec.invoice.branch.name if rec.invoice.branch else '',
            'amount': str(rec.amount),
            'payment_mode': PAYMENT_LABELS.get(rec.payment_mode, rec.payment_mode.title()),
            'remarks': rec.remarks or '',
        })

    rec_total = rec_qs.aggregate(t=Sum('amount'))['t'] or 0

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_collected': str(rec_total),
        'count': len(rows),
        'summary': summary,
        'rows': rows,
    })


@csrf_exempt
def api_report_outstanding(request):
    """Outstanding report: invoices with unpaid balance."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import Invoice
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    qs = Invoice.objects.filter(
        is_deleted=False, date__gte=from_date, date__lte=to_date, **scope
    ).annotate(
        balance=ExpressionWrapper(F('total') - F('amount_collected'), output_field=DecimalField())
    ).filter(balance__gt=0).select_related('customer', 'vehicle', 'branch').order_by('-date', '-auto_id')

    rows = []
    for inv in qs:
        rows.append({
            'invoice_number': inv.invoice_number,
            'date': inv.date.strftime('%d-%m-%Y'),
            'customer': inv.customer.name,
            'phone': inv.customer.phone,
            'vehicle': inv.vehicle.vehicle_number if inv.vehicle else '',
            'branch': inv.branch.name if inv.branch else '',
            'total': str(inv.total),
            'collected': str(inv.amount_collected),
            'balance': str(inv.balance),
        })

    agg = qs.aggregate(
        total_outstanding=Sum(ExpressionWrapper(F('total') - F('amount_collected'), output_field=DecimalField())),
        count=models.Count('id'),
    )

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_outstanding': str(agg['total_outstanding'] or 0),
        'count': agg['count'] or 0,
        'rows': rows,
    })


@csrf_exempt
def api_report_bookings(request):
    """Booking report: all bookings in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from booking_management.models import Booking
    from django.db.models import Count

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    qs = Booking.objects.filter(
        is_deleted=False, booking_date__gte=from_date, booking_date__lte=to_date, **scope
    ).select_related('customer', 'vehicle', 'branch').order_by('-booking_date', '-auto_id')

    rows = []
    for b in qs:
        rows.append({
            'id': str(b.id),
            'auto_id': b.auto_id,
            'date': b.booking_date.strftime('%d-%m-%Y'),
            'time': b.booking_time.strftime('%I:%M %p') if b.booking_time else '',
            'customer': b.customer.name,
            'phone': b.customer.phone,
            'vehicle': b.vehicle.vehicle_number if b.vehicle else '',
            'branch': b.branch.name if b.branch else '',
            'status': b.status,
            'notes': b.notes or '',
        })

    totals = qs.aggregate(
        total_bookings=Count('id'),
        total_pending=Count('id', filter=models.Q(status='pending')),
        total_confirmed=Count('id', filter=models.Q(status='confirmed')),
        total_completed=Count('id', filter=models.Q(status='completed')),
        total_cancelled=Count('id', filter=models.Q(status='cancelled')),
    )

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_bookings': totals['total_bookings'] or 0,
        'total_pending': totals['total_pending'] or 0,
        'total_confirmed': totals['total_confirmed'] or 0,
        'total_completed': totals['total_completed'] or 0,
        'total_cancelled': totals['total_cancelled'] or 0,
        'rows': rows,
    })


@csrf_exempt
def api_report_cancellations(request):
    """Cancellation report: all cancelled bookings in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from booking_management.models import Booking
    from django.db.models import Count

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    qs = Booking.objects.filter(
        is_deleted=False, status='cancelled', booking_date__gte=from_date, booking_date__lte=to_date, **scope
    ).select_related('customer', 'vehicle', 'branch').order_by('-booking_date', '-auto_id')

    rows = []
    for b in qs:
        rows.append({
            'id': str(b.id),
            'auto_id': b.auto_id,
            'date': b.booking_date.strftime('%d-%m-%Y'),
            'time': b.booking_time.strftime('%I:%M %p') if b.booking_time else '',
            'customer': b.customer.name,
            'phone': b.customer.phone,
            'vehicle': b.vehicle.vehicle_number if b.vehicle else '',
            'branch': b.branch.name if b.branch else '',
            'status': b.status,
            'notes': b.notes or '',
        })

    totals = qs.aggregate(
        total_cancelled=Count('id'),
    )

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_cancelled': totals['total_cancelled'] or 0,
        'rows': rows,
    })


@csrf_exempt
def api_report_service_type(request):
    """Service type report: Summary of services performed in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import InvoiceItem
    from django.db.models import Sum, Count, F

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    # Map scope to parent invoice fields
    invoice_scope = {f'invoice__{k}': v for k, v in scope.items()}

    qs = InvoiceItem.objects.filter(
        invoice__is_deleted=False,
        invoice__date__gte=from_date,
        invoice__date__lte=to_date,
        **invoice_scope
    )

    # Group by service_name
    grouped = qs.values('service_name').annotate(
        count=Count('id'),
        revenue=Sum(F('rate') - F('discount'))
    ).order_by('-revenue')

    rows = []
    total_count = 0
    total_revenue = 0.0

    for item in grouped:
        service_name = item['service_name']
        count = item['count'] or 0
        revenue = float(item['revenue'] or 0.0)
        
        total_count += count
        total_revenue += revenue
        
        rows.append({
            'service_name': service_name,
            'count': count,
            'revenue': str(round(revenue, 2)),
        })

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_count': total_count,
        'total_revenue': str(round(total_revenue, 2)),
        'rows': rows,
    })


@csrf_exempt
def api_report_service_type_detail(request):
    """Detailed view of all invoice items under a specific service name in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import InvoiceItem

    service_name = request.GET.get('service_name')
    if not service_name:
        return JsonResponse({'success': False, 'message': 'service_name is required'}, status=400)

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    invoice_scope = {f'invoice__{k}': v for k, v in scope.items()}

    filters = {
        'service_name': service_name,
        'invoice__is_deleted': False,
        'invoice__date__gte': from_date,
        'invoice__date__lte': to_date,
    }

    vehicle_type_id = request.GET.get('vehicle_type_id')
    vehicle_type_model_id = request.GET.get('vehicle_type_model_id')

    if vehicle_type_id:
        if vehicle_type_id == 'null':
            filters['invoice__vehicle__vehicle_type__isnull'] = True
        else:
            filters['invoice__vehicle__vehicle_type_id'] = vehicle_type_id

    if vehicle_type_model_id:
        if vehicle_type_model_id == 'null':
            filters['invoice__vehicle__vehicle_type_model__isnull'] = True
        else:
            filters['invoice__vehicle__vehicle_type_model_id'] = vehicle_type_model_id

    qs = InvoiceItem.objects.filter(
        **filters,
        **invoice_scope
    ).select_related('invoice', 'invoice__customer', 'invoice__vehicle', 'invoice__vehicle__vehicle_type').order_by('-invoice__date', '-invoice__auto_id')

    details = []
    for idx, item in enumerate(qs, 1):
        rate = float(item.rate or 0.0)
        discount = float(item.discount or 0.0)
        net_amount = rate - discount
        
        details.append({
            'sl_no': idx,
            'date': item.invoice.date.strftime('%Y-%m-%d'),
            'invoice_number': item.invoice.invoice_number,
            'customer_name': item.invoice.customer.name,
            'customer_phone': item.invoice.customer.phone,
            'vehicle_number': item.invoice.vehicle.vehicle_number if item.invoice.vehicle else '',
            'vehicle_type': item.invoice.vehicle.vehicle_type.name if item.invoice.vehicle and item.invoice.vehicle.vehicle_type else '',
            'amount': str(round(net_amount, 2)),
        })

    return JsonResponse({
        'success': True,
        'service_name': service_name,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'details': details
    })


@csrf_exempt
def api_report_service_type_vehicle_breakdown(request):
    """Breakdown of a specific service's revenue grouped by vehicle type/model."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import InvoiceItem
    from django.db.models import Sum, Count, F

    service_name = request.GET.get('service_name')
    if not service_name:
        return JsonResponse({'success': False, 'message': 'service_name is required'}, status=400)

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    invoice_scope = {f'invoice__{k}': v for k, v in scope.items()}

    qs = InvoiceItem.objects.filter(
        service_name=service_name,
        invoice__is_deleted=False,
        invoice__date__gte=from_date,
        invoice__date__lte=to_date,
        **invoice_scope
    )

    # Group by vehicle type and model
    grouped = qs.values(
        'invoice__vehicle__vehicle_type__name',
        'invoice__vehicle__vehicle_type_model__name',
        'invoice__vehicle__vehicle_type_id',
        'invoice__vehicle__vehicle_type_model_id'
    ).annotate(
        count=Count('id'),
        revenue=Sum(F('rate') - F('discount'))
    ).order_by('-revenue')

    rows = []
    total_count = 0
    total_revenue = 0.0

    for item in grouped:
        type_name = item['invoice__vehicle__vehicle_type__name'] or ''
        model_name = item['invoice__vehicle__vehicle_type_model__name'] or ''
        type_id = item['invoice__vehicle__vehicle_type_id']
        model_id = item['invoice__vehicle__vehicle_type_model_id']
        
        display_name = ""
        if type_name and model_name:
            display_name = f"{type_name} - {model_name}"
        elif type_name:
            display_name = type_name
        elif model_name:
            display_name = model_name
        else:
            display_name = "Other"

        count = item['count'] or 0
        revenue = float(item['revenue'] or 0.0)
        
        total_count += count
        total_revenue += revenue
        
        rows.append({
            'vehicle_type_id': str(type_id) if type_id else 'null',
            'vehicle_type_model_id': str(model_id) if model_id else 'null',
            'vehicle_type_name': type_name,
            'vehicle_type_model_name': model_name,
            'display_name': display_name,
            'count': count,
            'revenue': str(round(revenue, 2)),
        })

    return JsonResponse({
        'success': True,
        'service_name': service_name,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_count': total_count,
        'total_revenue': str(round(total_revenue, 2)),
        'rows': rows,
    })



@csrf_exempt

def api_list_complaint_types(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
    
    from .models import ComplaintType
    types = ComplaintType.objects.filter(company=company, is_deleted=False).order_by('name')
    
    return JsonResponse({
        'success': True,
        'complaint_types': [{'id': str(t.id), 'name': t.name} for t in types]
    })


@csrf_exempt
def api_create_complaint_type(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'success': False, 'message': 'Name is required'}, status=400)
        
        from .models import ComplaintType
        from core.functions import get_auto_id
        
        if ComplaintType.objects.filter(company=company, name__iexact=name, is_deleted=False).exists():
            return JsonResponse({'success': False, 'message': 'This complaint type already exists'}, status=400)
        
        complaint_type = ComplaintType.objects.create(
            company=company,
            name=name,
            auto_id=get_auto_id(ComplaintType)
        )
        return JsonResponse({
            'success': True,
            'complaint_type': {'id': str(complaint_type.id), 'name': complaint_type.name}
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_complaint(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    
    role = user.profile.role.name if user.profile.role else None
    branch = None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        branch = user.managed_branch
    
    if not branch:
        return JsonResponse({'success': False, 'message': 'Only Branch Admin can create complaints'}, status=403)
    
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
    
    try:
        data = json.loads(request.body)
        complaint_type_id = data.get('complaint_type_id')
        priority = data.get('priority', 'low').lower()
        complaint_description = data.get('complaint', '').strip()
        
        if not complaint_type_id or not complaint_description:
            return JsonResponse({'success': False, 'message': 'Complaint type and description are required'}, status=400)
        
        if priority not in ['low', 'medium', 'high']:
            return JsonResponse({'success': False, 'message': 'Invalid priority level'}, status=400)
        
        from .models import ComplaintType, Complaint
        from core.functions import get_auto_id
        
        complaint_type = ComplaintType.objects.filter(id=complaint_type_id, company=company, is_deleted=False).first()
        if not complaint_type:
            return JsonResponse({'success': False, 'message': 'Invalid complaint type'}, status=400)
            
        complaint = Complaint.objects.create(
            company=company,
            branch=branch,
            complaint_type=complaint_type,
            priority=priority,
            complaint_description=complaint_description,
            status='new',
            auto_id=get_auto_id(Complaint)
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Complaint created successfully',
            'complaint': {
                'id': str(complaint.id),
                'auto_id': complaint.auto_id,
                'complaint_type': complaint.complaint_type.name,
                'priority': complaint.priority,
                'complaint': complaint.complaint_description,
                'status': complaint.status,
                'branch': complaint.branch.name,
                'date_added': complaint.date_added.strftime('%d-%m-%Y')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_list_complaints(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    
    role = user.profile.role.name if user.profile.role else None
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
        
    from .models import Complaint
    from django.utils import timezone
    
    qs = Complaint.objects.filter(company=company, is_deleted=False).select_related('branch', 'complaint_type').order_by('-date_added', '-auto_id')
    
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        qs = qs.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN':
        pass
    else:
        return JsonResponse({'success': False, 'message': 'Unauthorized role for viewing complaints'}, status=403)
        
    today = timezone.localtime(timezone.now()).date()
    complaints = []
    for c in qs:
        # Dynamic status evaluation
        if c.status == 'resolved':
            computed_status = 'resolved'
        else:
            added_date = timezone.localtime(c.date_added).date()
            if added_date == today:
                computed_status = 'new'
            else:
                computed_status = 'pending'
                
        complaints.append({
            'id': str(c.id),
            'auto_id': c.auto_id,
            'complaint_type_id': str(c.complaint_type.id),
            'complaint_type': c.complaint_type.name,
            'priority': c.priority,
            'complaint': c.complaint_description,
            'status': computed_status,
            'resolve_remarks': c.resolve_remarks or '',
            'branch': c.branch.name,
            'date_added': timezone.localtime(c.date_added).strftime('%d-%m-%Y')
        })
        
    return JsonResponse({
        'success': True,
        'complaints': complaints
    })


@csrf_exempt
def api_update_complaint_status(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can resolve complaints'}, status=403)
        
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
        
    try:
        data = json.loads(request.body)
        complaint_id = data.get('complaint_id')
        status = data.get('status', '').lower().strip()
        remarks = data.get('remarks', data.get('resolve_remarks', '')).strip()
        
        if not complaint_id or not status:
            return JsonResponse({'success': False, 'message': 'Complaint ID and status are required'}, status=400)
            
        if status not in ['new', 'pending', 'resolved']:
            return JsonResponse({'success': False, 'message': 'Invalid status. Choose from: new, pending, resolved'}, status=400)
            
        from .models import Complaint
        complaint = Complaint.objects.filter(id=complaint_id, company=company, is_deleted=False).first()
        if not complaint:
            return JsonResponse({'success': False, 'message': 'Complaint not found'}, status=404)
            
        complaint.status = status
        if remarks:
            complaint.resolve_remarks = remarks
        complaint.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Complaint status updated to {status}',
            'complaint': {
                'id': str(complaint.id),
                'auto_id': complaint.auto_id,
                'status': complaint.status,
                'resolve_remarks': complaint.resolve_remarks or ''
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_list_suppliers(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
    
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import Supplier
        company = getattr(getattr(user, 'profile', None), 'company', None)
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        suppliers = Supplier.objects.filter(company=company, is_deleted=False).order_by('name')
        supplier_list = [{
            'id': str(s.id),
            'name': s.name,
            'address': s.address,
            'gst_no': s.gst_no or '',
            'phone_no': s.phone_no,
            'is_active': s.is_active
        } for s in suppliers]
        
        return JsonResponse({'success': True, 'suppliers': supplier_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_supplier(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import Supplier
        company = getattr(getattr(user, 'profile', None), 'company', None)
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        data = json.loads(request.body)
        supplier_id = data.get('id')
        name = data.get('name', '').strip()
        address = data.get('address', '').strip()
        gst_no = data.get('gst_no', '').strip() or None
        phone_no = data.get('phone_no', '').strip()
        is_active = data.get('is_active', True)
        
        if not name or not address or not phone_no:
            return JsonResponse({'success': False, 'message': 'Name, address, and phone number are required'}, status=400)
            
        if supplier_id:
            # Edit
            supplier = Supplier.objects.get(id=supplier_id, company=company, is_deleted=False)
            supplier.name = name
            supplier.address = address
            supplier.gst_no = gst_no
            supplier.phone_no = phone_no
            supplier.is_active = is_active
            supplier.updater = user
            supplier.save()
            msg = "Supplier updated successfully"
        else:
            # Create
            if Supplier.objects.filter(company=company, name__iexact=name, is_deleted=False).exists():
                return JsonResponse({'success': False, 'message': 'A supplier with this name already exists'}, status=400)
                
            supplier = Supplier.objects.create(
                auto_id=get_auto_id(Supplier),
                company=company,
                name=name,
                address=address,
                gst_no=gst_no,
                phone_no=phone_no,
                is_active=is_active,
                creator=user
            )
            msg = "Supplier created successfully"
            
        return JsonResponse({
            'success': True,
            'message': msg,
            'supplier': {
                'id': str(supplier.id),
                'name': supplier.name,
                'address': supplier.address,
                'gst_no': supplier.gst_no or '',
                'phone_no': supplier.phone_no,
                'is_active': supplier.is_active
            }
        })
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Supplier not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_delete_supplier(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import Supplier
        company = getattr(getattr(user, 'profile', None), 'company', None)
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        data = json.loads(request.body)
        supplier_id = data.get('id')
        if not supplier_id:
            return JsonResponse({'success': False, 'message': 'id is required'}, status=400)
            
        supplier = Supplier.objects.get(id=supplier_id, company=company, is_deleted=False)
        supplier.is_deleted = True
        supplier.updater = user
        supplier.save()
        
        return JsonResponse({'success': True, 'message': 'Supplier deleted successfully'})
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Supplier not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def api_get_expense_heads(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
    
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import ExpenseHead
        from django.db.models import Q
        company = getattr(getattr(user, 'profile', None), 'company', None)
        if not company:
            heads = ExpenseHead.objects.filter(is_deleted=False).order_by('name')
        else:
            heads = ExpenseHead.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).order_by('name')
        head_list = [{'id': str(h.id), 'name': h.name, 'is_deletable': h.is_deletable} for h in heads]
        return JsonResponse({'success': True, 'expense_heads': head_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_list_purchase_expenses(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import ExpenseEntry
        company = getattr(getattr(user, 'profile', None), 'company', None)
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        
        # Filter expenses where head is 'purchase'
        qs = ExpenseEntry.objects.filter(
            company=company,
            expense__expense_head__name__iexact='purchase',
            is_deleted=False
        ).select_related('expense', 'expense__expense_head', 'supplier', 'branch').order_by('-expense_date', '-auto_id')
        
        # If user is a branch admin, filter by branch
        if hasattr(user, 'managed_branch') and user.managed_branch:
            qs = qs.filter(branch=user.managed_branch)
            
        expense_list = []
        for e in qs:
            expense_list.append({
                'id': str(e.id),
                'expense_name': e.expense.name,
                'amount': str(e.amount or 0),
                'paid_amount': str(e.paid_amount or 0),
                'balance_amount': str((e.amount or 0) - (e.paid_amount or 0)),
                'expense_date': e.expense_date.strftime('%Y-%m-%d'),
                'remarks': e.remarks or '',
                'supplier_name': e.supplier.name if e.supplier else 'N/A',
                'branch_name': e.branch.name if e.branch else 'N/A',
            })
            
        return JsonResponse({'success': True, 'purchase_expenses': expense_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_update_purchase_expense_payment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import ExpenseEntry
        from decimal import Decimal
        
        data = json.loads(request.body)
        expense_id = data.get('id')
        additional_paid = data.get('additional_paid')
        
        if not expense_id or additional_paid is None:
            return JsonResponse({'success': False, 'message': 'id and additional_paid are required'}, status=400)
            
        additional_paid = Decimal(str(additional_paid))
        if additional_paid <= 0:
            return JsonResponse({'success': False, 'message': 'additional_paid must be greater than zero'}, status=400)
            
        company = getattr(getattr(user, 'profile', None), 'company', None)
        expense = ExpenseEntry.objects.get(id=expense_id, company=company, is_deleted=False)
        
        new_paid_amount = (expense.paid_amount or 0) + additional_paid
        if new_paid_amount > (expense.amount or 0):
            return JsonResponse({
                'success': False, 
                'message': f'Paid amount ({new_paid_amount}) cannot exceed total expense amount ({expense.amount or 0})'
            }, status=400)
            
        expense.paid_amount = new_paid_amount
        expense.updater = user
        expense.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Payment updated successfully',
            'paid_amount': str(expense.paid_amount),
            'balance_amount': str((expense.amount or 0) - expense.paid_amount)
        })
    except ExpenseEntry.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Expense entry not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_expense_entry(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from master.models import ExpenseHead, Expense, ExpenseEntry
        from .models import Branch
        from django.shortcuts import get_object_or_404
        
        data = json.loads(request.body)
        expense_head_id = data.get('expense_head_id')
        expense_name = data.get('expense_name')
        amount = data.get('amount')
        expense_date = data.get('date')  # 'yyyy-mm-dd'
        remarks = data.get('remarks', '')
        
        if not expense_head_id or not expense_name or not amount or not expense_date:
            return JsonResponse({'success': False, 'message': 'expense_head_id, expense_name, amount, and date are required'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        branch = None
        if hasattr(user, 'managed_branch') and user.managed_branch:
            branch = user.managed_branch
        elif role == 'COMPANY_ADMIN':
            branch_id = data.get('branch_id')
            if branch_id:
                branch = get_object_or_404(Branch, id=branch_id, company=company)
            else:
                branch = company.branches.filter(is_deleted=False).first()
                
        if not branch:
            return JsonResponse({'success': False, 'message': 'No branch associated with user'}, status=400)
            
        # Get or create the Expense
        expense_head = get_object_or_404(ExpenseHead, id=expense_head_id, is_deleted=False)
        expense, created = Expense.objects.get_or_create(
            expense_head=expense_head,
            name=expense_name,
            defaults={
                'auto_id': get_auto_id(Expense),
                'creator': user
            }
        )
        
        # If it's a purchase expense, handle supplier and paid_amount
        supplier = None
        paid_amount = amount
        if expense_head.name.strip().lower() == 'purchase':
            supplier_id = data.get('supplier_id')
            if supplier_id:
                from master.models import Supplier
                supplier = get_object_or_404(Supplier, id=supplier_id, company=company, is_deleted=False)
            paid_amount = data.get('paid_amount', 0.00)
            
        # Create ExpenseEntry
        entry = ExpenseEntry.objects.create(
            auto_id=get_auto_id(ExpenseEntry),
            creator=user,
            company=company,
            branch=branch,
            expense=expense,
            amount=amount,
            expense_date=expense_date,
            remarks=remarks,
            supplier=supplier,
            paid_amount=paid_amount
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Expense created successfully',
            'expense_entry_id': str(entry.id)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_get_staff_list(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import Staff
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        staffs = Staff.objects.filter(company=company, is_deleted=False)
        
        # If Branch Admin/Staff, restrict to their managed branch
        if role in ['BRANCH_ADMIN', 'BRANCH_MANAGER', 'MARKETING', 'CLERICAL', 'SERVICE']:
            if hasattr(user, 'managed_branch') and user.managed_branch:
                staffs = staffs.filter(branch=user.managed_branch)
            elif hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.branch:
                staffs = staffs.filter(branch=user.staff_profile.branch)
                
        staff_list = [{
            'id': str(s.id),
            'name': s.name,
            'employee_id': s.employee_id,
            'branch_name': s.branch.name if s.branch else ''
        } for s in staffs.order_by('name')]
        
        return JsonResponse({'success': True, 'staffs': staff_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_get_staff_leaves(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import StaffLeave
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        leaves = StaffLeave.objects.filter(staff__company=company, is_deleted=False)
        
        if hasattr(user, 'staff_profile') and user.staff_profile:
            leaves = leaves.filter(staff=user.staff_profile)
        elif role == 'BRANCH_ADMIN':
            if hasattr(user, 'managed_branch') and user.managed_branch:
                leaves = leaves.filter(staff__branch=user.managed_branch)
                
        leave_list = [{
            'id': str(l.id),
            'staff_name': l.staff.name,
            'employee_id': l.staff.employee_id,
            'branch_name': l.staff.branch.name if l.staff.branch else '',
            'start_date': str(l.start_date),
            'end_date': str(l.end_date),
            'reason': l.reason or '',
            'remarks': l.remarks or '',
            'status': l.status
        } for l in leaves.order_by('-start_date')]
        
        return JsonResponse({'success': True, 'leaves': leave_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_staff_leave(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import Staff, StaffLeave
        from django.shortcuts import get_object_or_404
        
        data = json.loads(request.body)
        staff_id = data.get('staff_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        reason = data.get('reason', '')
        remarks = data.get('remarks', '')
        status = data.get('status', 'APPROVED')
        
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        
        if not staff_id:
            if hasattr(user, 'staff_profile') and user.staff_profile:
                staff = user.staff_profile
            else:
                return JsonResponse({'success': False, 'message': 'staff_id is required'}, status=400)
        else:
            staff = get_object_or_404(Staff, id=staff_id, company=company, is_deleted=False)
            
        if not start_date or not end_date:
            return JsonResponse({'success': False, 'message': 'start_date and end_date are required'}, status=400)
        
        # Verify branch scope if they are branch admin
        role = user.profile.role.name if user.profile.role else None
        if role in ['BRANCH_ADMIN', 'BRANCH_MANAGER', 'MARKETING', 'CLERICAL', 'SERVICE']:
            user_branch = None
            if hasattr(user, 'managed_branch') and user.managed_branch:
                user_branch = user.managed_branch
            elif hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.branch:
                user_branch = user.staff_profile.branch
            
            if user_branch and staff.branch != user_branch:
                return JsonResponse({'success': False, 'message': 'Permission denied for this branch staff member'}, status=403)
                
        # Create StaffLeave
        leave = StaffLeave.objects.create(
            auto_id=get_auto_id(StaffLeave),
            creator=user,
            staff=staff,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            remarks=remarks,
            status=status
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Staff leave recorded successfully',
            'leave_id': str(leave.id)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_get_stock_list(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import Stock
        from django.db.models import Q
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        stocks = Stock.objects.filter(
            Q(company=company) | Q(company__isnull=True),
            is_deleted=False
        ).select_related('expense_head').order_by('item_name')
        
        stock_list = [{
            'id': str(s.id),
            'item_name': s.item_name,
            'unit': s.unit,
            'unit_display': s.get_unit_display(),
            'expense_head_id': str(s.expense_head.id) if s.expense_head else None,
            'expense_head_name': s.expense_head.name if s.expense_head else None,
        } for s in stocks]
        
        return JsonResponse({'success': True, 'stocks': stock_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_get_purchase_requests(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import PurchaseRequest
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        role = user.profile.role.name if user.profile.role else None
        purchases = PurchaseRequest.objects.filter(company=company, is_deleted=False)
        
        if role == 'BRANCH_ADMIN' or hasattr(user, 'managed_branch') or (hasattr(user, 'staff_profile') and user.staff_profile):
            user_branch = None
            if hasattr(user, 'managed_branch') and user.managed_branch:
                user_branch = user.managed_branch
            elif hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.branch:
                user_branch = user.staff_profile.branch
            
            if user_branch:
                purchases = purchases.filter(branch=user_branch)
                
        purchase_list = [{
            'id': str(p.id),
            'date': str(p.date),
            'material_id': str(p.material.id),
            'material_name': p.material.item_name,
            'unit': p.material.unit,
            'unit_display': p.material.get_unit_display(),
            'qty': float(p.qty),
            'requested_by_name': p.requested_by.username if p.requested_by else 'Unknown',
            'status': p.status,
            'remarks': p.remarks or ''
        } for p in purchases.order_by('-date', '-date_added')]
        
        return JsonResponse({'success': True, 'purchase_requests': purchase_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_purchase_request(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import Stock, PurchaseRequest
        from django.shortcuts import get_object_or_404
        
        data = json.loads(request.body)
        date = data.get('date')
        material_id = data.get('material_id')
        qty = data.get('qty')
        remarks = data.get('remarks', '')
        
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        if not date or not material_id or qty is None:
            return JsonResponse({'success': False, 'message': 'date, material_id, and qty are required'}, status=400)
            
        material = get_object_or_404(Stock, id=material_id, is_deleted=False)
        if material.company and material.company != company:
            return JsonResponse({'success': False, 'message': 'Permission denied for this stock material'}, status=403)
            
        user_branch = None
        if hasattr(user, 'managed_branch') and user.managed_branch:
            user_branch = user.managed_branch
        elif hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.branch:
            user_branch = user.staff_profile.branch
            
        purchase = PurchaseRequest.objects.create(
            auto_id=get_auto_id(PurchaseRequest),
            creator=user,
            company=company,
            branch=user_branch,
            date=date,
            material=material,
            qty=qty,
            requested_by=user,
            remarks=remarks,
            status='PENDING'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Purchase request submitted successfully',
            'purchase_id': str(purchase.id)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_expense_head(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can create expense heads'}, status=403)
        
    try:
        from master.models import ExpenseHead
        from core.functions import get_auto_id
        
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'success': False, 'message': 'Name is required'}, status=400)
            
        if ExpenseHead.objects.filter(name__iexact=name, is_deleted=False).exists():
            return JsonResponse({'success': False, 'message': 'This expense head already exists'}, status=400)
            
        expense_head = ExpenseHead.objects.create(
            name=name,
            auto_id=get_auto_id(ExpenseHead),
            creator=user
        )
        return JsonResponse({
            'success': True,
            'message': 'Expense head created successfully',
            'expense_head': {'id': str(expense_head.id), 'name': expense_head.name}
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_stock(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can create stock items'}, status=403)
        
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
        
    try:
        from .models import Stock
        from core.functions import get_auto_id
        
        data = json.loads(request.body)
        item_name = data.get('item_name', '').strip()
        unit = data.get('unit', '').strip()
        expense_head_id = data.get('expense_head_id')
        
        if not item_name or not unit:
            return JsonResponse({'success': False, 'message': 'item_name and unit are required'}, status=400)
            
        valid_units = [u[0] for u in Stock.UNIT_CHOICES]
        if unit not in valid_units:
            return JsonResponse({'success': False, 'message': f'Invalid unit. Valid choices are: {", ".join(valid_units)}'}, status=400)
            
        if Stock.objects.filter(company=company, item_name__iexact=item_name, is_deleted=False).exists():
            return JsonResponse({'success': False, 'message': 'Stock item already exists'}, status=400)
            
        expense_head = None
        if expense_head_id:
            from master.models import ExpenseHead
            from django.db.models import Q
            expense_head = get_object_or_404(ExpenseHead, Q(company=company) | Q(company__isnull=True), id=expense_head_id, is_deleted=False)
            
        stock = Stock.objects.create(
            company=company,
            item_name=item_name,
            unit=unit,
            expense_head=expense_head,
            auto_id=get_auto_id(Stock),
            creator=user
        )
        return JsonResponse({
            'success': True,
            'message': 'Stock item created successfully',
            'stock': {
                'id': str(stock.id),
                'item_name': stock.item_name,
                'unit': stock.unit,
                'unit_display': stock.get_unit_display(),
                'expense_head_id': str(stock.expense_head.id) if stock.expense_head else None,
                'expense_head_name': stock.expense_head.name if stock.expense_head else None,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_edit_expense_head(request, id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can edit expense heads'}, status=403)
    try:
        from master.models import ExpenseHead
        expense_head = get_object_or_404(ExpenseHead, id=id, is_deleted=False)
        
        company = user.profile.company
        if expense_head.company != company and not user.is_superuser:
            return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)

        if not expense_head.is_deletable:
            return JsonResponse({'success': False, 'message': f"Editing is disabled for '{expense_head.name}' expense head."}, status=400)

        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'success': False, 'message': 'Name is required'}, status=400)

        if ExpenseHead.objects.filter(company=company, name__iexact=name, is_deleted=False).exclude(id=id).exists():
            return JsonResponse({'success': False, 'message': 'This expense head already exists'}, status=400)

        expense_head.name = name
        expense_head.save()

        return JsonResponse({
            'success': True,
            'message': 'Expense head updated successfully',
            'expense_head': {'id': str(expense_head.id), 'name': expense_head.name}
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_delete_expense_head(request, id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can delete expense heads'}, status=403)
    try:
        from master.models import ExpenseHead
        expense_head = get_object_or_404(ExpenseHead, id=id, is_deleted=False)

        company = user.profile.company
        if expense_head.company != company and not user.is_superuser:
            return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)

        if not expense_head.is_deletable:
            return JsonResponse({'success': False, 'message': f"Deletion is disabled for '{expense_head.name}' expense head."}, status=400)

        expense_head.is_deleted = True
        expense_head.save()

        return JsonResponse({
            'success': True,
            'message': 'Expense head deleted successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_edit_stock(request, id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can edit stock items'}, status=403)
    try:
        from .models import Stock
        stock = get_object_or_404(Stock, id=id, is_deleted=False)

        company = user.profile.company
        if stock.company != company and not user.is_superuser:
            return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)

        data = json.loads(request.body)
        item_name = data.get('item_name', '').strip()
        unit = data.get('unit', '').strip()
        expense_head_id = data.get('expense_head_id')

        if not item_name or not unit:
            return JsonResponse({'success': False, 'message': 'item_name and unit are required'}, status=400)

        valid_units = [u[0] for u in Stock.UNIT_CHOICES]
        if unit not in valid_units:
            return JsonResponse({'success': False, 'message': f'Invalid unit. Valid choices are: {", ".join(valid_units)}'}, status=400)

        if Stock.objects.filter(company=company, item_name__iexact=item_name, is_deleted=False).exclude(id=id).exists():
            return JsonResponse({'success': False, 'message': 'Stock item already exists'}, status=400)

        expense_head = None
        if expense_head_id:
            from master.models import ExpenseHead
            from django.db.models import Q
            expense_head = get_object_or_404(ExpenseHead, Q(company=company) | Q(company__isnull=True), id=expense_head_id, is_deleted=False)

        stock.item_name = item_name
        stock.unit = unit
        stock.expense_head = expense_head
        stock.save()

        return JsonResponse({
            'success': True,
            'message': 'Stock item updated successfully',
            'stock': {
                'id': str(stock.id),
                'item_name': stock.item_name,
                'unit': stock.unit,
                'unit_display': stock.get_unit_display(),
                'expense_head_id': str(stock.expense_head.id) if stock.expense_head else None,
                'expense_head_name': stock.expense_head.name if stock.expense_head else None,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_delete_stock(request, id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can delete stock items'}, status=403)
    try:
        from .models import Stock
        stock = get_object_or_404(Stock, id=id, is_deleted=False)

        company = user.profile.company
        if stock.company != company and not user.is_superuser:
            return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)

        stock.is_deleted = True
        stock.save()

        return JsonResponse({
            'success': True,
            'message': 'Stock item deleted successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_report_expense_head_wise(request):
    """Expense head wise report: Summary of expenses grouped by head in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Permission denied: Only Company Admin/Owner can access this report'}, status=403)

    from master.models import ExpenseEntry, ExpenseHead
    from django.db.models import Sum

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    qs = ExpenseEntry.objects.filter(
        is_deleted=False,
        expense_date__gte=from_date,
        expense_date__lte=to_date,
        **scope
    ).select_related('expense__expense_head')

    from django.db.models import Q
    heads = ExpenseHead.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).order_by('name')
    
    rows = []
    total_all = 0.0

    for h in heads:
        head_qs = qs.filter(expense__expense_head=h)
        total_amount = head_qs.aggregate(s=Sum('amount'))['s'] or 0.0
        total_amount = float(total_amount)
        if total_amount > 0:
            total_all += total_amount
            rows.append({
                'expense_head_id': str(h.id),
                'expense_head_name': h.name,
                'total_amount': str(round(total_amount, 2))
            })

    rows.sort(key=lambda x: float(x['total_amount']), reverse=True)

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_expense': str(round(total_all, 2)),
        'rows': rows
    })


@csrf_exempt
def api_report_profit_loss(request):
    """Profit and Loss report: Income by service type and Expense by expense head, with net profit/loss."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import InvoiceItem, Invoice
    from master.models import ExpenseEntry, ExpenseHead
    from django.db.models import Sum, F

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    invoice_scope = {f'invoice__{k}': v for k, v in scope.items()}

    # --- 1. INCOME (grouped by service name) ---
    income_qs = InvoiceItem.objects.filter(
        invoice__is_deleted=False,
        invoice__date__gte=from_date,
        invoice__date__lte=to_date,
        **invoice_scope
    )
    
    income_grouped = income_qs.values('service_name').annotate(
        revenue=Sum(F('rate') - F('discount'))
    ).order_by('-revenue')

    income_rows = []
    total_income = 0.0
    for item in income_grouped:
        service_name = item['service_name']
        revenue = float(item['revenue'] or 0.0)
        total_income += revenue
        income_rows.append({
            'service_name': service_name,
            'amount': str(round(revenue, 2)),
        })

    # --- 2. EXPENSE (grouped by expense head) ---
    expense_qs = ExpenseEntry.objects.filter(
        is_deleted=False,
        expense_date__gte=from_date,
        expense_date__lte=to_date,
        **scope
    ).select_related('expense__expense_head')

    from django.db.models import Q
    heads = ExpenseHead.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).order_by('name')
    expense_rows = []
    total_expense = 0.0

    for h in heads:
        head_qs = expense_qs.filter(expense__expense_head=h)
        total_amount = head_qs.aggregate(s=Sum('amount'))['s'] or 0.0
        total_amount = float(total_amount)
        if total_amount > 0:
            total_expense += total_amount
            expense_rows.append({
                'expense_head_name': h.name,
                'amount': str(round(total_amount, 2))
            })
    
    expense_rows.sort(key=lambda x: float(x['amount']), reverse=True)

    # Calculate net profit or loss
    net_profit = total_income - total_expense

    # Calculate outstanding balance (Receivables)
    invoices = Invoice.objects.filter(
        is_deleted=False,
        date__gte=from_date,
        date__lte=to_date,
        **scope
    )
    total_outstanding = sum(float(inv.total or 0) - float(inv.amount_collected or 0) for inv in invoices)

    # Calculate payables (unpaid purchase expense balance)
    payables_qs = ExpenseEntry.objects.filter(
        is_deleted=False,
        expense_date__gte=from_date,
        expense_date__lte=to_date,
        expense__expense_head__name__iexact='purchase',
        **scope
    )
    total_payables = sum(float(e.amount or 0) - float(e.paid_amount or 0) for e in payables_qs)

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_income': str(round(total_income, 2)),
        'total_expense': str(round(total_expense, 2)),
        'net_profit': str(round(net_profit, 2)),
        'total_outstanding': str(round(total_outstanding, 2)),
        'total_payables': str(round(total_payables, 2)),
        'income_rows': income_rows,
        'expense_rows': expense_rows,
    })


@csrf_exempt
def api_report_expense_head_detail(request):
    """Detailed view of all expense entries under a specific head in date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Permission denied: Only Company Admin/Owner can access this report'}, status=403)

    from master.models import ExpenseEntry, ExpenseHead
    from django.shortcuts import get_object_or_404

    expense_head_id = request.GET.get('expense_head_id')
    if not expense_head_id:
        return JsonResponse({'success': False, 'message': 'expense_head_id is required'}, status=400)

    expense_head = get_object_or_404(ExpenseHead, id=expense_head_id, is_deleted=False)

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    entries = ExpenseEntry.objects.filter(
        expense__expense_head=expense_head,
        is_deleted=False,
        expense_date__gte=from_date,
        expense_date__lte=to_date,
        **scope
    ).select_related('expense').order_by('-expense_date', '-auto_id')

    details = []
    for idx, e in enumerate(entries, 1):
        details.append({
            'sl_no': idx,
            'expense_name': e.expense.name,
            'amount': str(e.amount),
            'date': e.expense_date.strftime('%Y-%m-%d'),
            'remarks': e.remarks or ''
        })

    return JsonResponse({
        'success': True,
        'expense_head_name': expense_head.name,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'details': details
    })


@csrf_exempt
def api_report_leave(request):
    """Leave report: List of all staff leaves in the date range."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from client_management.models import StaffLeave
    from django.db.models import Count

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    staff_scope = {}
    for key, val in scope.items():
        new_key = key.replace('branch', 'staff__branch')
        staff_scope[new_key] = val

    leaves = StaffLeave.objects.filter(
        is_deleted=False,
        start_date__gte=from_date,
        start_date__lte=to_date,
        **staff_scope
    ).select_related('staff__branch').order_by('-start_date')

    rows = []
    for idx, l in enumerate(leaves, 1):
        rows.append({
            'sl_no': idx,
            'staff_name': l.staff.name,
            'employee_id': l.staff.employee_id or '',
            'branch_name': l.staff.branch.name if l.staff.branch else '',
            'start_date': l.start_date.strftime('%Y-%m-%d'),
            'end_date': l.end_date.strftime('%Y-%m-%d'),
            'reason': l.reason or '',
            'remarks': l.remarks or '',
            'status': l.status
        })

    total_leaves = len(rows)
    pending_leaves = sum(1 for r in rows if r['status'] == 'PENDING')
    approved_leaves = sum(1 for r in rows if r['status'] == 'APPROVED')

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rows': rows
    })


@csrf_exempt
def api_get_extras_list(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        from .models import Extra
        from django.db.models import Q
        company = user.profile.company
        if not company:
            return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
            
        extras = Extra.objects.filter(
            Q(company=company) | Q(company__isnull=True),
            is_deleted=False
        ).order_by('name')
        
        extras_list = [{
            'id': str(e.id),
            'name': e.name,
        } for e in extras]
        
        return JsonResponse({'success': True, 'extras': extras_list})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_create_extra(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    role = user.profile.role.name if user.profile.role else None
    if role != 'COMPANY_ADMIN':
        return JsonResponse({'success': False, 'message': 'Only Owner/Company Admin can create extras'}, status=403)
        
    company = user.profile.company
    if not company:
        return JsonResponse({'success': False, 'message': 'No company associated with user'}, status=400)
        
    try:
        from .models import Extra
        from core.functions import get_auto_id
        
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'message': 'name is required'}, status=400)
            
        if Extra.objects.filter(company=company, name__iexact=name, is_deleted=False).exists():
            return JsonResponse({'success': False, 'message': 'Extra item already exists'}, status=400)
            
        extra = Extra.objects.create(
            company=company,
            name=name,
            auto_id=get_auto_id(Extra),
            creator=user
        )
        return JsonResponse({
            'success': True,
            'message': 'Extra item created successfully',
            'extra': {
                'id': str(extra.id),
                'name': extra.name,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_report_daywise_consolidated(request):
    """
    Daywise consolidated reports:
    - income: Daywise invoice count, total total, total collected.
    - profit: Daywise total income, total expense, net profit.
    - collection: Daywise payment collection by mode.
    - outstanding: Daywise outstanding invoice count and balance.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from django.db.models import Sum, Count, F, Q, ExpressionWrapper, DecimalField
    from django.db import models
    from finance_management.models import Invoice, Receipt
    from master.models import ExpenseEntry
    from datetime import timedelta

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    report_type = request.GET.get('type', 'income')

    # Construct the base date list to ensure we cover all days in the range (even empty ones)
    date_list = []
    curr = from_date
    while curr <= to_date:
        date_list.append(curr)
        curr += timedelta(days=1)

    # Let's map branch scopes for Receipt
    receipt_scope = {}
    if 'branch' in scope:
        receipt_scope['invoice__branch'] = scope['branch']
    elif 'branch__company' in scope:
        receipt_scope['invoice__branch__company'] = scope['branch__company']

    rows = []

    if report_type == 'income':
        inv_qs = Invoice.objects.filter(
            is_deleted=False,
            date__gte=from_date,
            date__lte=to_date,
            **scope
        ).values('date').annotate(
            count=Count('id'),
            total_income=models.Sum('total'),
            total_collected=models.Sum('amount_collected')
        )
        inv_map = {item['date']: item for item in inv_qs}

        total_income_sum = 0.0
        total_collected_sum = 0.0
        total_jobs_sum = 0

        for d in date_list:
            item = inv_map.get(d)
            count = item['count'] if item else 0
            income = float(item['total_income'] or 0.0) if item else 0.0
            collected = float(item['total_collected'] or 0.0) if item else 0.0

            total_income_sum += income
            total_collected_sum += collected
            total_jobs_sum += count

            rows.append({
                'date': d.strftime('%d-%m-%Y'),
                'count': count,
                'income': str(round(income, 2)),
                'collected': str(round(collected, 2)),
            })

        rows.reverse()

        return JsonResponse({
            'success': True,
            'from_date': str(from_date),
            'to_date': str(to_date),
            'total_income': str(round(total_income_sum, 2)),
            'total_collected': str(round(total_collected_sum, 2)),
            'total_jobs': total_jobs_sum,
            'rows': rows,
        })

    elif report_type == 'profit':
        # Income from Invoices
        inv_qs = Invoice.objects.filter(
            is_deleted=False,
            date__gte=from_date,
            date__lte=to_date,
            **scope
        ).values('date').annotate(
            income=models.Sum('total')
        )
        inv_map = {item['date']: float(item['income'] or 0.0) for item in inv_qs}

        # Expense from ExpenseEntry
        exp_qs = ExpenseEntry.objects.filter(
            is_deleted=False,
            expense_date__gte=from_date,
            expense_date__lte=to_date,
            **scope
        ).values('expense_date').annotate(
            expense=models.Sum('amount')
        )
        exp_map = {item['expense_date']: float(item['expense'] or 0.0) for item in exp_qs}

        total_income_sum = 0.0
        total_expense_sum = 0.0
        total_profit_sum = 0.0

        for d in date_list:
            income = inv_map.get(d, 0.0)
            expense = exp_map.get(d, 0.0)
            profit = income - expense

            total_income_sum += income
            total_expense_sum += expense
            total_profit_sum += profit

            rows.append({
                'date': d.strftime('%d-%m-%Y'),
                'income': str(round(income, 2)),
                'expense': str(round(expense, 2)),
                'profit': str(round(profit, 2)),
            })

        rows.reverse()

        return JsonResponse({
            'success': True,
            'from_date': str(from_date),
            'to_date': str(to_date),
            'total_income': str(round(total_income_sum, 2)),
            'total_expense': str(round(total_expense_sum, 2)),
            'total_profit': str(round(total_profit_sum, 2)),
            'rows': rows,
        })

    elif report_type == 'collection':
        rec_qs = Receipt.objects.filter(
            created_at__date__gte=from_date,
            created_at__date__lte=to_date,
            **receipt_scope
        ).values('created_at__date').annotate(
            cash=models.Sum('amount', filter=Q(payment_mode='cash')),
            cheque=models.Sum('amount', filter=Q(payment_mode='cheque')),
            online=models.Sum('amount', filter=Q(payment_mode='online')),
            total=models.Sum('amount')
        )
        rec_map = {item['created_at__date']: item for item in rec_qs}

        total_cash = 0.0
        total_cheque = 0.0
        total_online = 0.0
        total_all = 0.0

        for d in date_list:
            item = rec_map.get(d)
            cash = float(item['cash'] or 0.0) if item else 0.0
            cheque = float(item['cheque'] or 0.0) if item else 0.0
            online = float(item['online'] or 0.0) if item else 0.0
            total = float(item['total'] or 0.0) if item else 0.0

            total_cash += cash
            total_cheque += cheque
            total_online += online
            total_all += total

            rows.append({
                'date': d.strftime('%d-%m-%Y'),
                'cash': str(round(cash, 2)),
                'cheque': str(round(cheque, 2)),
                'online': str(round(online, 2)),
                'total': str(round(total, 2)),
            })

        rows.reverse()

        return JsonResponse({
            'success': True,
            'from_date': str(from_date),
            'to_date': str(to_date),
            'total_cash': str(round(total_cash, 2)),
            'total_cheque': str(round(total_cheque, 2)),
            'total_online': str(round(total_online, 2)),
            'total_collected': str(round(total_all, 2)),
            'rows': rows,
        })

    elif report_type == 'outstanding':
        inv_qs = Invoice.objects.filter(
            is_deleted=False,
            date__gte=from_date,
            date__lte=to_date,
            **scope
        ).annotate(
            balance=ExpressionWrapper(F('total') - F('amount_collected'), output_field=DecimalField())
        ).filter(balance__gt=0).values('date').annotate(
            count=Count('id'),
            outstanding=models.Sum('balance')
        )
        inv_map = {item['date']: item for item in inv_qs}

        total_outstanding_sum = 0.0
        total_count_sum = 0

        for d in date_list:
            item = inv_map.get(d)
            count = item['count'] if item else 0
            outstanding = float(item['outstanding'] or 0.0) if item else 0.0

            total_outstanding_sum += outstanding
            total_count_sum += count

            rows.append({
                'date': d.strftime('%d-%m-%Y'),
                'count': count,
                'outstanding': str(round(outstanding, 2)),
            })

        rows.reverse()

        return JsonResponse({
            'success': True,
            'from_date': str(from_date),
            'to_date': str(to_date),
            'total_outstanding': str(round(total_outstanding_sum, 2)),
            'total_invoices': total_count_sum,
            'rows': rows,
        })

    else:
        return JsonResponse({'success': False, 'message': 'Invalid report type'}, status=400)


@csrf_exempt
def api_report_payment_type(request):
    """Payment Type report: returns total amounts collected grouped by payment mode, and all receipts."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from finance_management.models import Receipt
    from django.db.models import Sum

    from_date, to_date = _parse_dates(request)
    company, scope = _report_scope(user, request.GET.get('branch_id'))

    receipt_scope = {}
    if 'branch' in scope:
        receipt_scope['invoice__branch'] = scope['branch']
    elif 'branch__company' in scope:
        receipt_scope['invoice__branch__company'] = scope['branch__company']

    rec_qs = Receipt.objects.filter(
        created_at__date__gte=from_date,
        created_at__date__lte=to_date,
        **receipt_scope
    )

    # Group by payment mode
    grouped = rec_qs.values('payment_mode').annotate(total_amount=Sum('amount')).order_by('-total_amount')
    
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
            'total_amount': str(amt),
        })

    existing_modes = {item['payment_mode'] for item in grouped}
    for mode, label in Receipt.PAYMENT_CHOICES:
        if mode not in existing_modes:
            summary.append({
                'payment_mode': mode,
                'payment_mode_display': label,
                'total_amount': '0.00',
            })

    # Individual rows for detail table
    rec_qs = rec_qs.select_related('invoice', 'invoice__customer', 'invoice__vehicle', 'invoice__branch').order_by('-created_at')
    rows = []
    for rec in rec_qs:
        rows.append({
            'receipt_number': rec.receipt_number,
            'date': rec.created_at.date().strftime('%d-%m-%Y'),
            'invoice_number': rec.invoice.invoice_number,
            'customer': rec.invoice.customer.name,
            'phone': rec.invoice.customer.phone,
            'vehicle': rec.invoice.vehicle.vehicle_number if rec.invoice.vehicle else '',
            'branch': rec.invoice.branch.name if rec.invoice.branch else '',
            'amount': str(rec.amount),
            'payment_mode': PAYMENT_LABELS.get(rec.payment_mode, rec.payment_mode.title()),
            'remarks': rec.remarks or '',
        })

    return JsonResponse({
        'success': True,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'total_collected': str(total_collected),
        'summary': summary,
        'rows': rows,
    })







