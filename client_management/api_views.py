import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.utils import timezone
from core.models import APIToken
from core.functions import get_auto_id
from .models import Customer, CustomerVehicle, Scheme
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
            if role not in ['COMPANY_ADMIN', 'BRANCH_ADMIN']:
                return JsonResponse({'success': False, 'message': 'Unauthorized role'}, status=403)
                
            token_obj, created = APIToken.objects.get_or_create(user=user)
            
            company_name = user.profile.company.company_name if user.profile.company else ''
            branch_name = ''
            if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
                branch_name = user.managed_branch.name

            # Display name: branch name for BRANCH_ADMIN, company name for COMPANY_ADMIN
            display_name = branch_name if role == 'BRANCH_ADMIN' else company_name

            return JsonResponse({
                'success': True,
                'token': token_obj.token,
                'role': role,
                'company_name': company_name,
                'branch_name': branch_name,
                'display_name': display_name,
                'username': user.username
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
            return token_obj.user
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

    return JsonResponse({
        'success': True,
        'today_jobs': today_jobs,
        'total_jobs': today_jobs,        # backward compat
        'today_revenue': str(today_revenue),
        'today_collected': str(today_collected),
        'total_outstanding': str(total_outstanding),
        'outstanding_count': outstanding_count,
        'total_customers': customers_qs.count(),
        'recent_invoices': recent,
    })

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
                
                from finance_management.models import Invoice
                
                # Count actual invoices for this vehicle as visits
                visits_count = Invoice.objects.filter(vehicle=v, is_deleted=False).count()
                
                if paid_visits > 0 and visits_count >= paid_visits:
                    is_eligible = True
                
        vehicles_data.append({
            'id': str(v.id),
            'no': v.vehicle_number,
            'type': v.vehicle_type_model.name if v.vehicle_type_model else 'Unknown',
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

            services_data.append({
                'id': str(svc.id),
                'name': svc.name,
                'service_type': svc.service_type.name,
                'rate': rate,
                'has_price': price_obj is not None and rate > 0,
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

        prefix_base = f"INV-{prefix}-"
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
            creator=user,
            auto_id=get_auto_id(Invoice)
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
                creator=user,
                auto_id=get_auto_id(InvoiceItem)
            )
            
        return JsonResponse({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice_id': str(invoice.id),
            'invoice_number': invoice.invoice_number
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


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

    # Scope vehicles to the company's customers
    vehicles = CustomerVehicle.objects.filter(
        vehicle_number__iexact=vehicle_number,
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
    """Returns customer types and vehicle type models for the add-customer form."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from master.models import VehicleTypeModel
    from .models import CustomerType

    customer_types = CustomerType.objects.filter(is_deleted=False)
    vehicle_models = VehicleTypeModel.objects.filter(is_deleted=False, is_active=True).select_related('vehicle_type').order_by('vehicle_type__name', 'name')

    return JsonResponse({
        'success': True,
        'customer_types': [{'id': str(ct.id), 'name': ct.name} for ct in customer_types],
        'vehicle_models': [{'id': str(vm.id), 'name': vm.name, 'vehicle_type': vm.vehicle_type.name} for vm in vehicle_models],
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
                if not vehicle_number or not vehicle_model_id:
                    continue
                vm = VehicleTypeModel.objects.filter(id=vehicle_model_id, is_deleted=False).first()
                if not vm:
                    continue
                cv = CustomerVehicle.objects.create(
                    customer=customer,
                    vehicle_type_model=vm,
                    vehicle_number=vehicle_number,
                    creator=user,
                    auto_id=get_auto_id(CustomerVehicle),
                )
                vehicles_data.append({
                    'id': str(cv.id),
                    'no': cv.vehicle_number,
                    'type': vm.name,
                })

        return JsonResponse({
            'success': True,
            'message': 'Customer added successfully',
            'customer': {
                'id': str(customer.id),
                'name': customer.name,
                'phone': customer.phone,
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

        search = request.GET.get('search', '').strip()
        if search:
            from django.db.models import Q
            customers_qs = customers_qs.filter(
                Q(name__icontains=search) | Q(phone__icontains=search)
            )

        customers_data = []
        for c in customers_qs.select_related('customer_type')[:100]:
            customers_data.append({
                'id': str(c.id),
                'name': c.name,
                'phone': c.phone,
                'customer_type': c.customer_type.name if c.customer_type else '',
                'vehicle_count': c.vehicles.filter(is_deleted=False).count(),
            })

        return JsonResponse({'success': True, 'customers': customers_data})
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
                cv.save()

            # Add new vehicles
            for v in new_vehicles:
                vehicle_number = v.get('vehicle_number', '').strip().upper()
                vehicle_model_id = v.get('vehicle_model_id')
                if not vehicle_number or not vehicle_model_id:
                    continue
                vm = VehicleTypeModel.objects.filter(id=vehicle_model_id, is_deleted=False).first()
                if not vm:
                    continue
                CustomerVehicle.objects.create(
                    customer=customer,
                    vehicle_type_model=vm,
                    vehicle_number=vehicle_number,
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

        # Total paid visits (invoices without any scheme)
        total_paid_visits = Invoice.objects.filter(vehicle=vehicle, scheme__isnull=True, is_deleted=False).count()

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
                
                # Count how many times this specific scheme was already used by this vehicle
                free_washes_taken = Invoice.objects.filter(vehicle=vehicle, scheme=scheme, is_deleted=False).count()
                
                # Calculate current progress towards the next free wash
                current_progress = total_paid_visits - (free_washes_taken * paid)
                if current_progress < 0:
                    current_progress = 0
                    
                is_eligible = paid > 0 and current_progress >= paid
                entry.update({
                    'description': f'Get {free} free wash after every {paid} paid washes',
                    'paid_visits': paid,
                    'free_visits': free,
                    'visits_count': current_progress,
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

        if voucher:
            return JsonResponse({
                'success': True,
                'voucher_id': str(voucher.id),
                'discount': float(voucher.discount),
                'message': f'Voucher applied! ₹{voucher.discount} off',
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid or already used voucher'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
