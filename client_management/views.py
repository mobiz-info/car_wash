from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import JsonResponse

from .models import *
from .forms import *
from master.models import State, Area
from core.functions import get_auto_id


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


def ajax_get_areas(request):
    state_id = request.GET.get('state_id')
    areas = Area.objects.filter(district__state_id=state_id, is_deleted=False).values('id', 'name')
    return JsonResponse({'areas': list(areas)})


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
from service_management.models import Service
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

    return render(request, 'scheme/list.html', {'schemes': schemes, 'title': 'Schemes'})


@login_required
def scheme_create(request):
    try:
        company = request.user.profile.company
    except AttributeError:
        messages.error(request, "Not associated with any company.")
        return redirect('dashboard')

    all_services = Service.objects.filter(is_deleted=False, is_active=True)
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

    all_services = Service.objects.filter(is_deleted=False, is_active=True)
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
def customer_vehicle_list(request):
    data = CustomerVehicle.objects.filter(is_deleted=False)
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