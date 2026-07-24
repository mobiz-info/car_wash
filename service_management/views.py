from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from decimal import Decimal

from .models import ServiceType, Service, BranchService, BranchVehiclePrice, ServiceVehicleTypePrice, CompanyService
from master.models import VehicleType, VehicleTypeModel
from client_management.models import Branch
from .forms import ServiceTypeForm, ServiceForm
from core.functions import get_auto_id
# ==========================================
# SERVICE MANAGEMENT
# ==========================================

@login_required
def service_type_list(request):
    search = request.GET.get('search', '')
    queryset = ServiceType.objects.filter(is_deleted=False).order_by('-date_added')

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'service_type/list.html', {
        'page_obj': page_obj,
        'search': search,
        'title': 'Service Categories'
    })

@login_required
def service_type_create(request):
    if request.method == 'POST':
        form = ServiceTypeForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(ServiceType)
            instance.creator = request.user
            instance.save()
            messages.success(request, 'Service Category created successfully.')
            return redirect('service_type_list')
    else:
        form = ServiceTypeForm()
    
    return render(request, 'service_type/create.html', {
        'form': form,
        'title': 'Create Service Category'
    })

@login_required
def service_type_edit(request, id):
    instance = get_object_or_404(ServiceType, id=id, is_deleted=False)
    if request.method == 'POST':
        form = ServiceTypeForm(request.POST, instance=instance)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, 'Service Category updated successfully.')
            return redirect('service_type_list')
    else:
        form = ServiceTypeForm(instance=instance)
    
    return render(request, 'service_type/create.html', {
        'form': form,
        'title': 'Edit Service Category'
    })

@login_required
def service_type_delete(request, id):
    instance = get_object_or_404(ServiceType, id=id, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, 'Service Category deleted successfully.')
    return redirect('service_type_list')


@login_required
def service_list(request):
    search = request.GET.get('search', '')
    queryset = Service.objects.filter(is_deleted=False).select_related( 'service_type').order_by('-date_added')

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'service/list.html', {
        'page_obj': page_obj,
        'search': search,
        'title': 'Services'
    })

@login_required
def service_create(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(Service)
            instance.creator = request.user
            instance.save()
            messages.success(request, 'Service created successfully.')
            return redirect('service_list')
    else:
        form = ServiceForm()
    
    return render(request, 'service/create.html', {
        'form': form,
        'title': 'Create Service'
    })

@login_required
def service_edit(request, id):
    instance = get_object_or_404(Service, id=id, is_deleted=False)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=instance)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, 'Service updated successfully.')
            return redirect('service_list')
    else:
        form = ServiceForm(instance=instance)
    
    return render(request, 'service/create.html', {
        'form': form,
        'title': 'Edit Service'
    })

@login_required
def service_delete(request, id):
    instance = get_object_or_404(Service, id=id, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, 'Service deleted successfully.')
    return redirect('service_list')


@login_required
def branch_service_list(request):
    """List view — COMPANY_ADMIN sees all branches of their company; BRANCH_ADMIN sees their branch."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    search = request.GET.get('search', '')

    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        if not company:
            messages.error(request, "No company assigned.")
            return redirect('dashboard')
        
        branches = company.branches.filter(is_deleted=False)
        if search:
            branches = branches.filter(name__icontains=search)
            
        data = []
        for branch in branches:
            services = BranchService.objects.filter(branch=branch, is_enabled=True).select_related('service')
            data.append({
                'branch': branch,
                'services': services
            })
    else:
        branch = getattr(request.user, 'managed_branch', None)
        if not branch:
            messages.error(request, "No branch assigned.")
            return redirect('dashboard')
        
        services = BranchService.objects.filter(branch=branch, is_enabled=True).select_related('service')
        if search and search.lower() not in branch.name.lower():
            data = []
        else:
            data = [{'branch': branch, 'services': services}]

    return render(request, 'branch/branch_service_list.html', {
        'data': data,
        'search': search,
        'role_name': role_name
    })


@login_required
def company_service_manage(request):
    """COMPANY_ADMIN selects which services are available across their company."""
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not company:
        messages.error(request, "No company assigned.")
        return redirect('dashboard')

    all_services = Service.objects.filter(is_deleted=False).order_by('name')
    existing_ids = set(
        CompanyService.objects.filter(company=company, is_enabled=True)
        .values_list('service_id', flat=True)
    )

    if request.method == 'POST':
        selected = request.POST.getlist('services')
        # Disable all, then re-enable selected
        CompanyService.objects.filter(company=company).update(is_enabled=False)
        for service in all_services:
            is_checked = str(service.id) in selected
            obj, created = CompanyService.objects.get_or_create(
                company=company,
                service=service,
                defaults={
                    'auto_id': get_auto_id(CompanyService),
                    'creator': request.user,
                    'is_enabled': is_checked,
                }
            )
            if not created:
                obj.is_enabled = is_checked
                obj.save()

            # Auto-propagate company service enable/disable status to all company branches
            branches = Branch.objects.filter(company=company, is_deleted=False)
            for b in branches:
                bs_obj, bs_created = BranchService.objects.get_or_create(
                    branch=b,
                    service=service,
                    defaults={
                        'auto_id': get_auto_id(BranchService),
                        'creator': request.user,
                        'is_enabled': is_checked,
                    }
                )
                if not bs_created:
                    bs_obj.is_enabled = is_checked
                    bs_obj.save()

        messages.success(request, "Company services updated successfully and synchronized to all branches.")
        return redirect('company_service_manage')

    return render(request, 'branch/company_service_manage.html', {
        'company': company,
        'services': all_services,
        'existing_ids': existing_ids,
        'title': 'Manage Company Services',
    })
    

@login_required
def branch_service_manage(request, branch_id):
    """BRANCH_ADMIN enables services — only from company-allowed services."""
    branch = get_object_or_404(Branch, id=branch_id)

    # Only show services the COMPANY has enabled for this branch's company
    company_enabled_ids = CompanyService.objects.filter(
        company=branch.company, is_enabled=True
    ).values_list('service_id', flat=True)

    services = Service.objects.filter(
        id__in=company_enabled_ids, is_deleted=False
    ).order_by('name')

    existing = BranchService.objects.filter(branch=branch, is_enabled=True)
    existing_service_ids = set(existing.values_list('service_id', flat=True))

    if request.method == 'POST':
        selected_services = request.POST.getlist('services')
        # Only allow selecting from company-enabled services
        BranchService.objects.filter(branch=branch, service_id__in=company_enabled_ids).update(is_enabled=False)

        for service in services:
            is_checked = str(service.id) in selected_services
            obj, created = BranchService.objects.get_or_create(
                branch=branch,
                service=service,
                defaults={
                    'auto_id': get_auto_id(BranchService),
                    'creator': request.user,
                    'is_enabled': is_checked,
                }
            )
            if not created:
                obj.is_enabled = is_checked
                obj.save()

        messages.success(request, "Branch services updated.")
        return redirect('branch_service_list')

    context = {
        'branch': branch,
        'services': services,
        'existing_service_ids': existing_service_ids,
        'title':'Enable Services'
    }
    return render(request, 'branch/branch_services.html', context)


@login_required
def branch_vehicle_price_list(request):

    # get only logged-in user's branch
    branch = getattr(request.user, 'managed_branch', None)

    if not branch:
        return render(request, 'branch/vehicle_price_list.html', {
            'data': [],
            'branch': None
        })

    data = BranchVehiclePrice.objects.select_related(
        'branch', 'vehicle_type'
    ).filter(branch=branch)

    return render(request, 'branch/vehicle_price_list.html', {
        'data': data,
        'branch': branch
    })
    
    
@login_required
def branch_vehicle_price_create(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    print("branch",branch)
    vehicle_types = VehicleType.objects.filter(is_active=True)

    existing = BranchVehiclePrice.objects.filter(branch=branch)
    existing_map = {i.vehicle_type_id: i for i in existing}

    if request.method == "POST":
        for vt in vehicle_types:
            price = request.POST.get(f'price_{vt.id}') or 0

            obj, created = BranchVehiclePrice.objects.get_or_create(
                branch=branch,
                vehicle_type=vt,
                defaults={
                    "auto_id": get_auto_id(BranchVehiclePrice),
                    "creator": request.user,
                    "price": price,
                    "is_active": True
                }
            )

            if not created:
                obj.price = price
                obj.is_active = True
                obj.save()

        return redirect('branch_vehicle_price_list')

    return render(request, 'branch/vehicle_price.html', {
        'branch': branch,
        'vehicle_types': vehicle_types,
        'existing_map': existing_map
    })

# @login_required
# def service_vehicle_price_manage(request, branch_id):
#     """
#     Grid UI: rows = enabled ServiceTypes for branch, columns = VehicleTypes.
#     Each cell holds the price for that service x vehicle type.
#     Accessible by both COMPANY_ADMIN and BRANCH_ADMIN.
#     """
#     branch = get_object_or_404(Branch, id=branch_id)
#     role = request.user.profile.role.name if hasattr(request.user, 'profile') and request.user.profile.role else None

#     # Scope guard
#     if role == 'BRANCH_ADMIN':
#         if getattr(request.user, 'managed_branch', None) != branch:
#             messages.error(request, "Access denied.")
#             return redirect('branch_vehicle_price_list')
#     elif role == 'COMPANY_ADMIN':
#         if branch.company != request.user.profile.company:
#             messages.error(request, "Access denied.")
#             return redirect('dashboard')

#     # Enabled ServiceTypes for this branch → then get individual Services under those types
#     enabled_service_type_ids = BranchService.objects.filter(
#         branch=branch, is_enabled=True, is_deleted=False
#     ).values_list('service_id', flat=True)

#     # Individual services belonging to enabled service types
#     services = Service.objects.filter(
#         service_type_id__in=enabled_service_type_ids,
#         is_active=True,
#         is_deleted=False,
#     ).select_related('service_type').order_by('service_type__name', 'name')

#     vehicle_types = VehicleType.objects.filter(is_active=True, is_deleted=False).order_by('name')

#     # Build existing price map: {(service_id, vehicle_type_id): price}
#     existing = ServiceVehicleTypePrice.objects.filter(branch=branch, is_deleted=False)
#     price_map = {(str(p.service_id), str(p.vehicle_type_id)): p.price for p in existing}

#     if request.method == 'POST':
#         for svc in services:
#             for vt in vehicle_types:
#                 field_name = f'price_{svc.id}_{vt.id}'
#                 raw = request.POST.get(field_name, '').strip()
#                 price_val = float(raw) if raw else 0.0

#                 obj, created = ServiceVehicleTypePrice.objects.get_or_create(
#                     branch=branch,
#                     service=svc,
#                     vehicle_type=vt,
#                     defaults={
#                         'auto_id': ServiceVehicleTypePrice.objects.count() + 1,
#                         'creator': request.user,
#                         'price': price_val,
#                         'is_active': True,
#                     }
#                 )
#                 if not created:
#                     obj.price = price_val
#                     obj.is_active = True
#                     obj.save()

#         messages.success(request, "Service pricing saved successfully.")
#         return redirect('service_vehicle_price_manage', branch_id=branch_id)

#     import json
#     # JSON format: {"svc_id__vt_id": "price_value"} for JS to populate inputs
#     price_map_json = json.dumps({
#         f"{sid}__{vid}": str(price)
#         for (sid, vid), price in price_map.items()
#     })

#     return render(request, 'service/service_vehicle_price.html', {
#         'branch': branch,
#         'services': services,
#         'vehicle_types': vehicle_types,
#         'price_map_json': price_map_json,
#         'title': f'Service Pricing - {branch.name}',
#     })
@login_required
def service_vehicle_price_manage(request, branch_id):

    branch = get_object_or_404(Branch, id=branch_id)

    # Role info — used to show branch switcher for COMPANY_ADMIN
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None
    company_branches = []
    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        if company:
            company_branches = Branch.objects.filter(company=company, is_deleted=False).order_by('name')

    company_enabled_ids = CompanyService.objects.filter(
        company=branch.company,
        is_enabled=True
    ).values_list('service_id', flat=True)

    enabled_service_ids = BranchService.objects.filter(
        branch=branch,
        service_id__in=company_enabled_ids,
        is_enabled=True,
        is_deleted=False
    ).values_list('service_id', flat=True)

    services_qs = Service.objects.filter(
        id__in=enabled_service_ids,
        is_active=True,
        is_deleted=False
    ).select_related('service_type')

    # Service categories (ServiceTypes) for enabled branch services
    categories = ServiceType.objects.filter(
        id__in=services_qs.values_list('service_type_id', flat=True)
    ).order_by('name')

    selected_category_id = request.GET.get('category')
    selected_category = None
    if selected_category_id:
        selected_category = ServiceType.objects.filter(id=selected_category_id).first()
        if selected_category:
            services_qs = services_qs.filter(service_type=selected_category)

    services = services_qs.order_by(
        'service_type__name',
        'name'
    )

    vehicle_types = VehicleType.objects.filter(
        is_active=True,
        is_deleted=False
    )

    selected_vehicle_type_id = request.GET.get('vehicle_type')

    selected_vehicle_type = None
    vehicle_models = []

    if selected_vehicle_type_id:

        selected_vehicle_type = get_object_or_404(
            VehicleType,
            id=selected_vehicle_type_id
        )

        vehicle_models = VehicleTypeModel.objects.filter(
            vehicle_type=selected_vehicle_type,
            is_active=True,
            is_deleted=False
        ).order_by('name')

    existing_prices = ServiceVehicleTypePrice.objects.filter(
        branch=branch,
        is_deleted=False
    )

    price_map = {
        f"{obj.service_id}__{obj.vehicle_model_id}": obj.price
        for obj in existing_prices
    }

    if request.method == 'POST':

        for service in services:

            for model in vehicle_models:

                field_name = f'price_{service.id}_{model.id}'

                raw = request.POST.get(field_name, '').strip()

                price_value = Decimal(raw) if raw else Decimal('0.00')

                obj, created = ServiceVehicleTypePrice.objects.get_or_create(
                    branch=branch,
                    service=service,
                    vehicle_model=model,
                    defaults={
                        'auto_id': get_auto_id(ServiceVehicleTypePrice),
                        'creator': request.user,
                        'price': price_value,
                        'is_active': True,
                    }
                )

                if not created:
                    obj.price = price_value
                    obj.is_active = True
                    obj.save()

        messages.success(request, "Pricing updated successfully.")
        redirect_url = reverse('service_vehicle_price_manage', kwargs={'branch_id': branch.id})
        params = []
        if selected_category:
            params.append(f"category={selected_category.id}")
        if selected_vehicle_type:
            params.append(f"vehicle_type={selected_vehicle_type.id}")
        if params:
            redirect_url += "?" + "&".join(params)
        return redirect(redirect_url)

    return render(request, 'service/service_vehicle_price.html', {
        'branch': branch,
        'categories': categories,
        'selected_category': selected_category,
        'vehicle_types': vehicle_types,
        'selected_vehicle_type': selected_vehicle_type,
        'vehicle_models': vehicle_models,
        'services': services,
        'price_map': price_map,
        'role_name': role_name,
        'company_branches': company_branches,
    })


@login_required
def service_vehicle_price_redirect(request):
    """For COMPANY_ADMIN: show branch-selection page. For BRANCH_ADMIN: go directly to their branch pricing."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        if not company:
            messages.error(request, "No company assigned.")
            return redirect('dashboard')
        branches = Branch.objects.filter(company=company, is_deleted=False).order_by('name')
        if not branches.exists():
            messages.error(request, "No branches found for your company.")
            return redirect('dashboard')
        # Render branch-selection page
        return render(request, 'service/select_branch_pricing.html', {
            'branches': branches,
            'title': 'Service Pricing — Select Branch',
        })
    else:
        branch = getattr(request.user, 'managed_branch', None)
        if not branch:
            messages.error(request, "No branch assigned.")
            return redirect('dashboard')
        return redirect('service_vehicle_price_manage', branch_id=branch.id)
