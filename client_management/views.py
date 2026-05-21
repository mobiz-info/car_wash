from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import Coalesce

from .models import *
from finance_management.models import Invoice,InvoiceItem
from .forms import *
from master.models import State, Area, District
from core.functions import get_auto_id


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


def _next_branch_invoice_prefix(company):
    branches = Branch.objects.filter(
        company=company,
    ).order_by('date_added', 'auto_id')

    used_prefixes = {
        (prefix or '').strip().upper()
        for prefix in branches.values_list('invoice_prefix', flat=True)
        if (prefix or '').strip()
    }

    next_index = branches.count()
    prefix = _index_to_invoice_prefix(next_index)
    while prefix in used_prefixes:
        next_index += 1
        prefix = _index_to_invoice_prefix(next_index)

    return prefix


@login_required
def client_list(request):
    search = request.GET.get('search', '')
    queryset = Client.objects.filter(is_deleted=False)
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'client/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def client_create(request):
    form = ClientForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   
            instance.auto_id = get_auto_id(Client)
            instance.save()
            form.save_m2m()
            messages.success(request, "Client created successfully")
            return redirect('client_list')
    return render(request, 'client/create.html', {
        'form': form,
        'title': 'Create Client'
    })


@login_required
def client_edit(request, id):
    instance = get_object_or_404(Client, id=id, is_deleted=False)
    form = ClientForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            form.save_m2m()
            messages.success(request, "Client updated successfully")
            return redirect('client_list')
    return render(request, 'client/create.html', {
        'form': form,
        'title': 'Edit Client',
        'selected_country_id': str(instance.country_id) if instance.country_id else '',
        'selected_state_id': str(instance.state_id) if instance.state_id else '',
        'selected_area_id': str(instance.area_id) if instance.area_id else '',
    })


@login_required
def client_delete(request, id):
    instance = get_object_or_404(Client, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Client deleted successfully")
    return redirect('client_list')


def ajax_get_states(request):
    country_id = request.GET.get('country_id')
    states = State.objects.filter(country_id=country_id, is_deleted=False).values('id', 'name')
    return JsonResponse({'states': list(states)})


@login_required
def ajax_get_areas(request):

    district_id = request.GET.get('district_id')

    areas = Area.objects.filter(
        district_id=district_id,
        is_deleted=False
    ).values('id', 'name')

    return JsonResponse({
        'areas': list(areas)
    })

@login_required
def ajax_get_districts(request):

    state_id = request.GET.get('state_id')

    districts = District.objects.filter(
        state_id=state_id,
        is_deleted=False
    ).values('id', 'name')

    return JsonResponse({
        'districts': list(districts)
    })
# ─── Subscription Views ───────────────────────────────────────────────────────

@login_required
def subscription_list(request):
    search = request.GET.get('search', '')
    queryset = Subscription.objects.filter(is_deleted=False).select_related('company')
    if search:
        queryset = queryset.filter(company__company_name__icontains=search)
    paginator = Paginator(queryset.order_by('-date_added'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'subscription/list.html', {
        'page_obj': page_obj,
        'search': search,
    })


@login_required
def subscription_create(request):
    form = SubscriptionForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(Subscription)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Subscription created successfully")
            return redirect('subscription_list')
    return render(request, 'subscription/create.html', {
        'form': form,
        'title': 'Create Subscription',
    })


@login_required
def subscription_edit(request, id):
    instance = get_object_or_404(Subscription, id=id, is_deleted=False)
    form = SubscriptionForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Subscription updated successfully")
            return redirect('subscription_list')
    return render(request, 'subscription/create.html', {
        'form': form,
        'title': 'Edit Subscription',
    })


@login_required
def subscription_delete(request, id):
    instance = get_object_or_404(Subscription, id=id, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Subscription deleted successfully")
    return redirect('subscription_list')


# ==========================================
# BRANCH MANAGEMENT
# ==========================================

@login_required
def branch_list(request):
    search = request.GET.get('search', '')
    
    # Restrict to Company Admin's company
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')
        
    branches = Branch.objects.filter(is_deleted=False, company=company).order_by('-date_added')
    
    if search:
        branches = branches.filter(name__icontains=search)
        
    paginator = Paginator(branches, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'branch/list.html', {
        'page_obj': page_obj,
        'search': search,
        'title': 'Branches',
    })

@login_required
def branch_create(request):
    form = BranchForm(request.POST or None, request.FILES or None, request=request)
    if request.method == 'POST':
        if form.is_valid():
            branch = form.save(commit=False)
            branch.auto_id = get_auto_id(Branch)
            branch.creator = request.user

            # Auto-assign the next available branch invoice prefix.
            try:
                company = request.user.profile.company
                branch.invoice_prefix = _next_branch_invoice_prefix(company)
            except Exception:
                pass

            branch.save()
            form.save_m2m()
            messages.success(request, "Branch created successfully")
            return redirect('branch_list')
        else:
            messages.error(request, "Please correct the errors below.")
            
    return render(request, 'branch/create.html', {
        'form': form,
        'title': 'Create Branch',
    })

@login_required
def branch_edit(request, id):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    instance = get_object_or_404(Branch, id=id, company=company, is_deleted=False)
    form = BranchForm(request.POST or None, request.FILES or None, instance=instance, request=request)
    
    if request.method == 'POST':
        if form.is_valid():
            branch = form.save(commit=False)
            branch.updater = request.user
            branch.save()
            form.save_m2m()
            messages.success(request, "Branch updated successfully")
            return redirect('branch_list')
        else:
            messages.error(request, "Please correct the errors below.")
            
    return render(request, 'branch/create.html', {
        'form': form,
        'title': 'Edit Branch',
        'is_edit': True,
    })

@login_required
def branch_delete(request, id):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    instance = get_object_or_404(Branch, id=id, company=company, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Branch deleted successfully")
    return redirect('branch_list')


# ==========================================
# STAFF MANAGEMENT
# ==========================================

@login_required
def staff_list(request):
    search = request.GET.get('search', '')
    
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')
        
    staffs = Staff.objects.filter(is_deleted=False, company=company).order_by('-date_added')
    
    if request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):
        staffs = staffs.filter(branch=request.user.managed_branch)
    
    if search:
        staffs = staffs.filter(name__icontains=search)
        
    paginator = Paginator(staffs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'staff/list.html', {
        'page_obj': page_obj,
        'search': search,
        'title': 'Staff',
    })

@login_required
def staff_create(request):
    form = StaffForm(request.POST or None, request.FILES or None, request=request)
    if request.method == 'POST':
        if form.is_valid():
            staff = form.save(commit=False)
            staff.auto_id = get_auto_id(Staff)
            staff.creator = request.user
            staff.save()
            messages.success(request, "Staff member created successfully")
            return redirect('staff_list')
        else:
            messages.error(request, "Please correct the errors below.")
            
    return render(request, 'staff/create.html', {
        'form': form,
        'title': 'Create Staff',
    })

@login_required
def staff_edit(request, id):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    instance = get_object_or_404(Staff, id=id, company=company, is_deleted=False)
    form = StaffForm(request.POST or None, request.FILES or None, instance=instance, request=request)
    
    if request.method == 'POST':
        if form.is_valid():
            staff = form.save(commit=False)
            staff.updater = request.user
            staff.save()
            messages.success(request, "Staff member updated successfully")
            return redirect('staff_list')
        else:
            messages.error(request, "Please correct the errors below.")
            
    return render(request, 'staff/create.html', {
        'form': form,
        'title': 'Edit Staff',
        'is_edit': True,
    })

@login_required
def staff_delete(request, id):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    instance = get_object_or_404(Staff, id=id, company=company, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Staff member deleted successfully")
    return redirect('staff_list')


@login_required
def customer_type_list(request):
    data = CustomerType.objects.filter(is_deleted=False)
    return render(request, 'customer_type/list.html', {'data': data})


@login_required
def customer_type_create(request):
    form = CustomerTypeForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(CustomerType)
            instance.save()
            messages.success(request, "Customer Type created successfully")
            return redirect('customer_type_list')

    return render(request, 'customer_type/create.html', {
        'form': form,
        'title': 'Create Customer Type'
    })


@login_required
def customer_type_edit(request, id):
    instance = get_object_or_404(CustomerType, id=id, is_deleted=False)

    form = CustomerTypeForm(request.POST or None, instance=instance)

    if form.is_valid():
        instance = form.save(commit=False)
        instance.updater = request.user
        instance.save()
        messages.success(request, "Customer Type updated successfully")
        return redirect('customer_type_list')

    return render(request, 'customer_type/create.html', {
        'form': form,
        'title': 'Edit Customer Type'
    })


@login_required
def customer_type_delete(request, id):
    instance = get_object_or_404(CustomerType, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Customer Type deleted successfully")
    return redirect('customer_type_list')

# ==========================================
# CUSTOMER MANAGEMENT
# ==========================================

from .models import Customer, CustomerVehicle
from .forms import CustomerForm, CustomerVehicleForm
from master.models import VehicleTypeModel

@login_required
def customer_list(request):
    search = request.GET.get('search', '')
    
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')
        
    customers = Customer.objects.filter(is_deleted=False, company=company).order_by('-date_added')
    
    # Restrict to branch if BRANCH_ADMIN
    if request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):
        customers = customers.filter(branch=request.user.managed_branch)
    
    if search:
        customers = customers.filter(name__icontains=search)
        
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'customer/list.html', {
        'page_obj': page_obj,
        'search': search,
        'title': 'Customers',
    })

@login_required
def customer_create(request):
    # Allow both COMPANY_ADMIN and BRANCH_ADMIN to create customers
    if request.user.profile.role.name not in ['BRANCH_ADMIN', 'COMPANY_ADMIN']:
        messages.error(request, "Only Branch or Company Admins can create customers.")
        return redirect('customer_list')

    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "Company configuration missing.")
        return redirect('dashboard')

    customer_form = CustomerForm(request.POST or None, request=request)
    vehicle_form = CustomerVehicleForm(request.POST or None)

    if request.method == 'POST':
        customer_valid = customer_form.is_valid()
        
        is_rc_owner = False
        if customer_valid:
            customer_type = customer_form.cleaned_data.get('customer_type')
            if customer_type and customer_type.name.lower() == 'rc owner':
                is_rc_owner = True
                
        # Only require vehicle form to be valid if it's an RC owner
        all_valid = customer_valid and (not is_rc_owner or vehicle_form.is_valid())

        if all_valid:
            # Save Customer
            customer = customer_form.save(commit=False)
            customer.company = company
            # branch is handled by the form because it is in the ModelForm fields
            customer.auto_id = get_auto_id(Customer)
            customer.creator = request.user
            customer.save()

            # Save Vehicle only if RC owner
            if is_rc_owner:
                vehicle = vehicle_form.save(commit=False)
                vehicle.customer = customer
                vehicle.auto_id = get_auto_id(CustomerVehicle)
                vehicle.creator = request.user
                vehicle.save()

            messages.success(request, "Customer created successfully")
            return redirect('customer_list')
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'customer/create.html', {
        'customer_form': customer_form,
        'vehicle_form': vehicle_form,
        'title': 'Add Customer',
    })

@login_required
def customer_edit(request, id):
    if request.user.profile.role.name not in ['BRANCH_ADMIN', 'COMPANY_ADMIN']:
        messages.error(request, "Only Branch or Company Admins can edit customers.")
        return redirect('customer_list')

    customer = get_object_or_404(Customer, id=id, is_deleted=False)
    
    # Ensure they belong to the same company
    if customer.company != request.user.profile.company:
        messages.error(request, "Unauthorized to edit this customer.")
        return redirect('customer_list')

    customer_form = CustomerForm(request.POST or None, instance=customer, request=request)
    
    if request.method == 'POST':
        if customer_form.is_valid():
            customer_form.save()
            messages.success(request, "Customer updated successfully.")
            return redirect('customer_list')
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'customer/create.html', {
        'customer_form': customer_form,
        'title': 'Edit Customer',
        'is_edit': True,
    })

@login_required
def customer_delete(request, id):
    if request.user.profile.role.name not in ['BRANCH_ADMIN', 'COMPANY_ADMIN']:
        messages.error(request, "Only Branch or Company Admins can delete customers.")
        return redirect('customer_list')

    customer = get_object_or_404(Customer, id=id, is_deleted=False)
    
    if customer.company != request.user.profile.company:
        messages.error(request, "Unauthorized to delete this customer.")
        return redirect('customer_list')

    customer.is_deleted = True
    customer.save()
    messages.success(request, "Customer deleted successfully.")
    return redirect('customer_list')

def ajax_load_vehicle_models(request):
    vehicle_type_id = request.GET.get('vehicle_type')
    if vehicle_type_id:
        models = VehicleTypeModel.objects.filter(vehicle_type_id=vehicle_type_id, is_active=True).order_by('name')
        return JsonResponse({'models': list(models.values('id', 'name'))})
    return JsonResponse({'models': []})


# ==========================================
# SCHEME MANAGEMENT
# ==========================================

import json
from .models import Scheme, SchemeVoucher
from .forms import SchemeForm
from service_management.models import Service, CompanyService
from master.models import VehicleType as MasterVehicleType


@login_required
def scheme_list(request):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    schemes = Scheme.objects.filter(is_deleted=False, company=company).prefetch_related(
        'services', 'customer_types', 'vehicle_types', 'scheme_type'
    ).order_by('-date_added')

    # If user is a branch admin, show only active schemes matching the branch's allowed scheme types
    if request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):
        from django.utils import timezone
        today = timezone.now().date()
        branch = request.user.managed_branch
        schemes = schemes.filter(
            scheme_type__in=branch.scheme_types.all(),
            start_date__lte=today,
            end_date__gte=today
        )

    # Compute benefited users count per scheme
    from finance_management.models import Invoice
    from django.db.models import Count, Q
    benefited_counts = []  # list of (scheme, count) tuples
    for scheme in schemes:
        scheme_type_name = scheme.scheme_type.name if scheme.scheme_type else ''

        # Base vehicle queryset: vehicles matching scheme's vehicle_types (if filtered)
        vehicles_qs = CustomerVehicle.objects.filter(
            is_deleted=False,
            customer__company=company,
        )
        if scheme.vehicle_types.exists():
            vehicles_qs = vehicles_qs.filter(
                vehicle_type_model__vehicle_type__in=scheme.vehicle_types.all()
            )
        if scheme.customer_types.exists():
            vehicles_qs = vehicles_qs.filter(
                customer__customer_type__in=scheme.customer_types.all()
            )

        if scheme_type_name == 'Quantity' and scheme.paid_visits:
            benefited = (
                vehicles_qs
                .annotate(visit_count=Count('invoices', filter=Q(invoices__is_deleted=False)))
                .filter(visit_count__gte=scheme.paid_visits)
                .values('customer').distinct().count()
            )
        elif scheme_type_name == 'Voucher':
            benefited = (
                Invoice.objects.filter(
                    is_deleted=False,
                    customer__company=company,
                    vehicle__in=vehicles_qs,
                    discount__gt=0,
                ).values('customer').distinct().count()
            )
        else:
            benefited = vehicles_qs.values('customer').distinct().count()

        benefited_counts.append((scheme, benefited))

    return render(request, 'scheme/list.html', {
        'schemes': benefited_counts,
        'title': 'Schemes',
    })

@login_required
def scheme_usage_list(request):
    """View to list all scheme redemptions (usages) across the company/branch."""
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    from finance_management.models import Invoice
    usages = Invoice.objects.filter(
        scheme__isnull=False, 
        is_deleted=False, 
        scheme__company=company
    ).select_related(
        'scheme', 'customer', 'vehicle', 'branch'
    ).order_by('-date_added')

    # If branch admin, only show usages from their branch
    if request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):
        usages = usages.filter(branch=request.user.managed_branch)

    return render(request, 'scheme/usages.html', {
        'usages': usages,
        'title': 'Scheme Usages',
    })


@login_required
def scheme_create(request):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "Not associated with any company.")
        return redirect('dashboard')

    company_enabled_service_ids = CompanyService.objects.filter(
        company=company, is_enabled=True
    ).values_list('service_id', flat=True)
    
    all_services = Service.objects.filter(
        id__in=company_enabled_service_ids, 
        is_deleted=False, 
        is_active=True
    )
    all_customer_types = CustomerType.objects.filter(is_deleted=False)
    all_vehicle_types = MasterVehicleType.objects.filter(is_deleted=False, is_active=True)

    # Only show scheme types the company has enabled
    company_scheme_types = company.scheme_types.all()

    form = SchemeForm(request.POST or None)
    form.fields['scheme_type'].queryset = company_scheme_types

    if request.method == 'POST':
        if form.is_valid():
            scheme_type_name = form.cleaned_data['scheme_type'].name.lower()

            # Validate benefit fields based on scheme type
            error = None
            if 'quantity' in scheme_type_name:
                if not form.cleaned_data.get('paid_visits') or not form.cleaned_data.get('free_visits'):
                    error = "Please enter Paid Visits and Free Visits for Quantity scheme."
            elif 'discount' in scheme_type_name:
                if not form.cleaned_data.get('discount_percentage'):
                    error = "Please enter a Discount Percentage for Discount scheme."
            elif 'voucher' in scheme_type_name:
                vouchers_json = request.POST.get('vouchers_data', '[]')
                try:
                    vouchers = json.loads(vouchers_json)
                except (json.JSONDecodeError, ValueError):
                    vouchers = []
                if not vouchers:
                    error = "Please add at least one voucher for Voucher scheme."

            if error:
                messages.error(request, error)
            else:
                scheme = form.save(commit=False)
                scheme.company = company
                scheme.auto_id = get_auto_id(Scheme)
                scheme.creator = request.user
                scheme.save()
                form.save_m2m()

                # Save vouchers if voucher type
                if 'voucher' in scheme_type_name:
                    for v in vouchers:
                        vnum = v.get('voucher_number', '').strip()
                        vdis = v.get('discount', None)
                        if vnum and vdis is not None:
                            SchemeVoucher.objects.create(
                                scheme=scheme,
                                voucher_number=vnum,
                                discount=vdis,
                                auto_id=get_auto_id(SchemeVoucher),
                                creator=request.user,
                            )

                messages.success(request, "Scheme created successfully")
                return redirect('scheme_list')
        else:
            messages.error(request, "Please correct the errors below.")

    import uuid
    selected_services = []
    selected_customers = []
    selected_vehicles = []
    if request.method == 'POST':
        for x in request.POST.getlist('services'):
            try: selected_services.append(uuid.UUID(x))
            except: pass
        for x in request.POST.getlist('customer_types'):
            try: selected_customers.append(uuid.UUID(x))
            except: pass
        for x in request.POST.getlist('vehicle_types'):
            try: selected_vehicles.append(uuid.UUID(x))
            except: pass

    return render(request, 'scheme/create.html', {
        'form': form,
        'all_services': all_services,
        'all_customer_types': all_customer_types,
        'all_vehicle_types': all_vehicle_types,
        'selected_services': selected_services,
        'selected_customers': selected_customers,
        'selected_vehicles': selected_vehicles,
        'title': 'Create Scheme',
    })

@login_required
def scheme_edit(request, id):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "Not associated with any company.")
        return redirect('dashboard')

    instance = get_object_or_404(Scheme, id=id, company=company, is_deleted=False)

    company_enabled_service_ids = CompanyService.objects.filter(
        company=company, is_enabled=True
    ).values_list('service_id', flat=True)
    
    all_services = Service.objects.filter(
        id__in=company_enabled_service_ids, 
        is_deleted=False, 
        is_active=True
    )
    all_customer_types = CustomerType.objects.filter(is_deleted=False)
    all_vehicle_types = MasterVehicleType.objects.filter(is_deleted=False, is_active=True)

    company_scheme_types = company.scheme_types.all()

    form = SchemeForm(request.POST or None, instance=instance)
    form.fields['scheme_type'].queryset = company_scheme_types
    
    existing_vouchers = list(instance.vouchers.values('voucher_number', 'discount'))

    if request.method == 'POST':
        if form.is_valid():
            scheme_type_name = form.cleaned_data['scheme_type'].name.lower()

            error = None
            if 'quantity' in scheme_type_name:
                if not form.cleaned_data.get('paid_visits') or not form.cleaned_data.get('free_visits'):
                    error = "Please enter Paid Visits and Free Visits for Quantity scheme."
            elif 'discount' in scheme_type_name:
                if not form.cleaned_data.get('discount_percentage'):
                    error = "Please enter a Discount Percentage for Discount scheme."
            elif 'voucher' in scheme_type_name:
                vouchers_json = request.POST.get('vouchers_data', '[]')
                try:
                    vouchers = json.loads(vouchers_json)
                except (json.JSONDecodeError, ValueError):
                    vouchers = []
                if not vouchers:
                    error = "Please add at least one voucher for Voucher scheme."

            if error:
                messages.error(request, error)
            else:
                scheme = form.save(commit=False)
                scheme.updater = request.user
                scheme.save()
                form.save_m2m()

                if 'voucher' in scheme_type_name:
                    instance.vouchers.all().delete()
                    for v in vouchers:
                        vnum = v.get('voucher_number', '').strip()
                        vdis = v.get('discount', None)
                        if vnum and vdis is not None:
                            SchemeVoucher.objects.create(
                                scheme=scheme,
                                voucher_number=vnum,
                                discount=vdis,
                                auto_id=get_auto_id(SchemeVoucher),
                                creator=request.user,
                            )

                messages.success(request, "Scheme updated successfully")
                return redirect('scheme_list')
        else:
            messages.error(request, "Please correct the errors below.")

    # Convert values to list for easy checking in template
    selected_services = list(instance.services.values_list('id', flat=True))
    selected_customers = list(instance.customer_types.values_list('id', flat=True))
    selected_vehicles = list(instance.vehicle_types.values_list('id', flat=True))

    return render(request, 'scheme/create.html', {
        'form': form,
        'all_services': all_services,
        'all_customer_types': all_customer_types,
        'all_vehicle_types': all_vehicle_types,
        'existing_vouchers_json': json.dumps([{'voucher_number': v['voucher_number'], 'discount': str(v['discount'])} for v in existing_vouchers]),
        'selected_services': selected_services,
        'selected_customers': selected_customers,
        'selected_vehicles': selected_vehicles,
        'title': 'Edit Scheme',
        'is_edit': True,
    })


@login_required
def scheme_delete(request, id):
    try:
        company = request.user.profile.company
    except AttributeError:
        return redirect('dashboard')
    instance = get_object_or_404(Scheme, id=id, company=company, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Scheme deleted successfully")
    return redirect('scheme_list')


@login_required
def scheme_detail(request, id):
    """Full detail view for a scheme including voucher management."""
    try:
        company = request.user.profile.company
    except AttributeError:
        return redirect('dashboard')

    scheme = get_object_or_404(Scheme, id=id, company=company, is_deleted=False)
    vouchers = scheme.vouchers.filter(is_deleted=False).order_by('-date_added')
    
    from finance_management.models import Invoice
    usages = Invoice.objects.filter(scheme=scheme, is_deleted=False).select_related(
        'customer', 'vehicle', 'branch'
    ).order_by('-date_added')

    return render(request, 'scheme/detail.html', {
        'scheme': scheme,
        'vouchers': vouchers,
        'usages': usages,
        'title': scheme.name,
        'is_company_admin': request.user.profile.role.name == 'COMPANY_ADMIN',
    })


@login_required
def voucher_add(request, scheme_id):
    """Add a voucher number to a scheme."""
    try:
        company = request.user.profile.company
    except AttributeError:
        return redirect('dashboard')

    if request.user.profile.role.name != 'COMPANY_ADMIN':
        messages.error(request, "Only company admins can add vouchers.")
        return redirect('scheme_detail', id=scheme_id)

    scheme = get_object_or_404(Scheme, id=scheme_id, company=company, is_deleted=False)

    if request.method == 'POST':
        from .models import SchemeVoucher
        voucher_number = request.POST.get('voucher_number', '').strip()
        discount = request.POST.get('discount', '0').strip()

        if not voucher_number:
            messages.error(request, "Voucher number is required.")
        elif SchemeVoucher.objects.filter(scheme=scheme, voucher_number=voucher_number, is_deleted=False).exists():
            messages.error(request, f"Voucher '{voucher_number}' already exists for this scheme.")
        else:
            try:
                from decimal import Decimal
                v = SchemeVoucher(
                    scheme=scheme,
                    voucher_number=voucher_number,
                    discount=Decimal(discount),
                    auto_id=SchemeVoucher.objects.count() + 1,
                )
                v.save()
                messages.success(request, f"Voucher '{voucher_number}' added successfully.")
            except Exception as e:
                messages.error(request, f"Error: {e}")

    return redirect('scheme_detail', id=scheme_id)


@login_required
def voucher_delete(request, voucher_id):
    """Delete a voucher from a scheme."""
    try:
        company = request.user.profile.company
    except AttributeError:
        return redirect('dashboard')

    if request.user.profile.role.name != 'COMPANY_ADMIN':
        messages.error(request, "Only company admins can delete vouchers.")
        return redirect('scheme_list')

    from .models import SchemeVoucher
    voucher = get_object_or_404(SchemeVoucher, id=voucher_id, scheme__company=company, is_deleted=False)
    scheme_id = voucher.scheme.id
    voucher.is_deleted = True
    voucher.save()
    messages.success(request, "Voucher deleted successfully.")
    return redirect('scheme_detail', id=scheme_id)



@login_required
def customer_vehicle_list(request):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "You are not associated with any company.")
        return redirect('dashboard')

    data = CustomerVehicle.objects.filter(is_deleted=False, customer__company=company).order_by('-date_added')

    # Restrict to branch if BRANCH_ADMIN
    if request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch'):
        data = data.filter(customer__branch=request.user.managed_branch)

    return render(request, 'customer_vehicle/list.html', {'data': data})


@login_required
def customer_vehicle_create(request):
    form = CustomersVehicleForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(CustomerVehicle)
            instance.save()
            return redirect('customer_vehicle_list')

    return render(request, 'customer_vehicle/create.html', {'form': form, 'title': 'Create Vehicle'})


@login_required
def customer_vehicle_edit(request, pk):
    instance = get_object_or_404(CustomerVehicle, pk=pk, is_deleted=False)
    form = CustomersVehicleForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('customer_vehicle_list')

    return render(request, 'customer_vehicle/create.html', {'form': form, 'title': 'Edit Vehicle'})


@login_required
def customer_vehicle_delete(request, pk):
    instance = get_object_or_404(CustomerVehicle, pk=pk)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Vehicle deleted successfully")
    return redirect('customer_vehicle_list')


@login_required
def load_vehicle_models(request):
    vehicle_type_id = request.GET.get('vehicle_type_id')
    models = VehicleTypeModel.objects.filter(vehicle_type_id=vehicle_type_id).values('id', 'name')
    return JsonResponse(list(models), safe=False)


@login_required
def customer_ledger(request):
    customers = Customer.objects.filter(is_deleted=False)

    customer_id = request.GET.get('customer')

    customer = None
    ledger_items = []
    total_services = 0
    total_amount = 0
    total_collected = 0
    total_balance = 0

    if customer_id:
        customer = get_object_or_404(
            Customer,
            id=customer_id,
            is_deleted=False
        )

        invoices = Invoice.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related(
            'vehicle',
            'branch'
        ).prefetch_related(
            'items'
        ).order_by('-date', '-id')

        ledger_items = []

        sl_no = 1

        for invoice in invoices:

            invoice_balance = invoice.total - invoice.amount_collected

            for item in invoice.items.all():

                ledger_items.append({
                    'sl_no': sl_no,
                    'date': invoice.date,
                    'invoice_number': invoice.invoice_number,
                    'vehicle_no': invoice.vehicle.vehicle_number if invoice.vehicle else '',
                    'service_name': item.service_name,
                    'price': item.rate,
                    'balance': invoice_balance,
                })

                sl_no += 1

        total_services = InvoiceItem.objects.filter(
            invoice__customer=customer,
            invoice__is_deleted=False,
            is_deleted=False
        ).count()

        totals = Invoice.objects.filter(
            customer=customer,
            is_deleted=False
        ).aggregate(
            total_amount=Coalesce(
                Sum('total'),
                0,
                output_field=DecimalField()
            ),
            total_collected=Coalesce(
                Sum('amount_collected'),
                0,
                output_field=DecimalField()
            )
        )

        total_amount = totals['total_amount']
        total_collected = totals['total_collected']
        total_balance = total_amount - total_collected

    context = {
        'customers': customers,
        'customer': customer,
        'ledger_items': ledger_items,
        'total_services': total_services,
        'total_amount': total_amount,
        'total_collected': total_collected,
        'total_balance': total_balance,
    }

    return render(request, 'customer/customer_ledger.html', context)


def complaint_list(request):
    search = request.GET.get('search', '')
    branch_id = request.GET.get('branch', '')
    
    role = request.user.profile.role.name if request.user.profile.role else None
    company = request.user.profile.company
    
    if not company:
        messages.error(request, "No company associated with user.")
        return redirect('dashboard')
        
    from .models import Complaint, Branch
    queryset = Complaint.objects.filter(company=company, is_deleted=False).select_related('branch', 'complaint_type').order_by('-date_added', '-auto_id')
    
    branches = Branch.objects.filter(company=company, is_deleted=False)
    
    if role == 'BRANCH_ADMIN' and hasattr(request.user, 'managed_branch') and request.user.managed_branch:
        queryset = queryset.filter(branch=request.user.managed_branch)
    elif role == 'COMPANY_ADMIN':
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
    else:
        # Super admin / other roles
        pass
        
    if search:
        queryset = queryset.filter(complaint_description__icontains=search)
        
    from django.utils import timezone
    today = timezone.localtime(timezone.now()).date()
    
    for c in queryset:
        if c.status == 'resolved':
            c.computed_status = 'resolved'
            c.status_bg = '#d1fae5'
            c.status_fg = '#065f46'
        else:
            added_date = timezone.localtime(c.date_added).date()
            if added_date == today:
                c.computed_status = 'new'
                c.status_bg = '#dbeafe'
                c.status_fg = '#1e40af'
            else:
                c.computed_status = 'pending'
                c.status_bg = '#ffedd5'
                c.status_fg = '#9a3412'
                
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'complaint/list.html', {
        'page_obj': page_obj,
        'search': search,
        'selected_branch': branch_id,
        'branches': branches,
        'role': role,
        'title': 'Complaints',
    })


@login_required
def complaint_create(request):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'BRANCH_ADMIN':
        messages.error(request, "Only Branch Admin can create complaints.")
        return redirect('complaint_list')
        
    company = request.user.profile.company
    branch = getattr(request.user, 'managed_branch', None)
    
    if not branch or not company:
        messages.error(request, "Branch configuration missing.")
        return redirect('complaint_list')
        
    from .models import ComplaintType, Complaint
    from core.functions import get_auto_id
    
    complaint_types = ComplaintType.objects.filter(company=company, is_deleted=False)
    
    if request.method == 'POST':
        complaint_type_id = request.POST.get('complaint_type')
        priority = request.POST.get('priority', 'low').lower()
        description = request.POST.get('description', '').strip()
        
        if not complaint_type_id or not description:
            messages.error(request, "Complaint type and description are required.")
        else:
            complaint_type = get_object_or_404(ComplaintType, id=complaint_type_id, company=company)
            Complaint.objects.create(
                company=company,
                branch=branch,
                complaint_type=complaint_type,
                priority=priority,
                complaint_description=description,
                status='new',
                auto_id=get_auto_id(Complaint),
                creator=request.user
            )
            messages.success(request, "Complaint created successfully.")
            return redirect('complaint_list')
            
    return render(request, 'complaint/create.html', {
        'complaint_types': complaint_types,
        'title': 'Create Complaint',
    })


@login_required
def complaint_resolve(request, id):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'COMPANY_ADMIN':
        messages.error(request, "Only Owner can resolve complaints.")
        return redirect('complaint_list')
        
    from .models import Complaint
    complaint = get_object_or_404(Complaint, id=id, company=request.user.profile.company)
    
    if request.method == 'POST':
        remarks = request.POST.get('remarks', '').strip()
        if not remarks:
            messages.error(request, "Resolution remarks are required.")
        else:
            complaint.status = 'resolved'
            complaint.resolve_remarks = remarks
            complaint.save()
            messages.success(request, "Complaint resolved successfully.")
            
    return redirect('complaint_list')


@login_required
def complaint_type_create(request):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'BRANCH_ADMIN':
        messages.error(request, "Only Branch Admin can create complaint types.")
        return redirect('complaint_list')
        
    company = request.user.profile.company
    if not company:
        messages.error(request, "Company missing.")
        return redirect('complaint_list')
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Name is required.")
        else:
            from .models import ComplaintType
            from core.functions import get_auto_id
            
            if ComplaintType.objects.filter(company=company, name__iexact=name, is_deleted=False).exists():
                messages.error(request, "This complaint type already exists.")
            else:
                ComplaintType.objects.create(
                    company=company,
                    name=name,
                    auto_id=get_auto_id(ComplaintType),
                    creator=request.user
                )
                messages.success(request, "Complaint type added successfully.")
                return redirect('complaint_create')
                
    return render(request, 'complaint/create_type.html', {
        'title': 'Add Complaint Type',
    })


@login_required
def whatsapp_settings(request):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'COMPANY_ADMIN':
        messages.error(request, "Access denied. Only Company Admins can manage settings.")
        return redirect('dashboard')

    company = request.user.profile.company
    if not company:
        messages.error(request, "No company associated with user.")
        return redirect('dashboard')

    try:
        setting = WhatsAppSetting.objects.get(company=company)
    except WhatsAppSetting.DoesNotExist:
        setting = WhatsAppSetting(company=company)

    if request.method == 'POST':
        form = WhatsAppSettingForm(request.POST, instance=setting)
        if form.is_valid():
            inst = form.save(commit=False)
            if not inst.auto_id:
                inst.auto_id = get_auto_id(WhatsAppSetting)
            if not inst.creator:
                inst.creator = request.user
            inst.updater = request.user
            inst.save()
            messages.success(request, "WhatsApp settings updated successfully.")
            return redirect('whatsapp_settings')
    else:
        form = WhatsAppSettingForm(instance=setting)

    return render(request, 'settings/whatsapp_settings.html', {
        'form': form,
        'title': 'WhatsApp Settings',
    })


@login_required
def whatsapp_template_list(request):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'COMPANY_ADMIN':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    company = request.user.profile.company
    if not company:
        messages.error(request, "No company associated with user.")
        return redirect('dashboard')

    search = request.GET.get('search', '')
    queryset = WhatsAppTemplate.objects.filter(company=company, is_deleted=False).order_by('-date_added')

    if search:
        queryset = queryset.filter(template_name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'settings/template_list.html', {
        'page_obj': page_obj,
        'search': search,
        'title': 'WhatsApp Templates',
    })


@login_required
def whatsapp_template_create(request):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'COMPANY_ADMIN':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    company = request.user.profile.company
    if not company:
        messages.error(request, "No company associated with user.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = WhatsAppTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.company = company
            template.auto_id = get_auto_id(WhatsAppTemplate)
            template.creator = request.user
            template.save()
            messages.success(request, "WhatsApp template created successfully.")
            return redirect('whatsapp_template_list')
    else:
        form = WhatsAppTemplateForm()

    return render(request, 'settings/template_create.html', {
        'form': form,
        'title': 'Create Template',
        'is_edit': False,
    })


@login_required
def whatsapp_template_edit(request, id):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'COMPANY_ADMIN':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    company = request.user.profile.company
    template = get_object_or_404(WhatsAppTemplate, id=id, company=company, is_deleted=False)

    if request.method == 'POST':
        form = WhatsAppTemplateForm(request.POST, instance=template)
        if form.is_valid():
            inst = form.save(commit=False)
            inst.updater = request.user
            inst.save()
            messages.success(request, "WhatsApp template updated successfully.")
            return redirect('whatsapp_template_list')
    else:
        form = WhatsAppTemplateForm(instance=template)

    return render(request, 'settings/template_create.html', {
        'form': form,
        'title': 'Edit Template',
        'is_edit': True,
    })


@login_required
def whatsapp_template_delete(request, id):
    role = request.user.profile.role.name if request.user.profile.role else None
    if role != 'COMPANY_ADMIN':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    company = request.user.profile.company
    template = get_object_or_404(WhatsAppTemplate, id=id, company=company)
    template.is_deleted = True
    template.save()
    messages.success(request, "WhatsApp template deleted successfully.")
    return redirect('whatsapp_template_list')
