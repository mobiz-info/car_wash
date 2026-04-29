from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

from .models import ServiceType, Service,BranchService, BranchVehiclePrice
from master.models import VehicleType
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
        'title': 'Service Types'
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
            messages.success(request, 'Service Type created successfully.')
            return redirect('service_type_list')
    else:
        form = ServiceTypeForm()
    
    return render(request, 'service_type/create.html', {
        'form': form,
        'title': 'Create Service Type'
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
            messages.success(request, 'Service Type updated successfully.')
            return redirect('service_type_list')
    else:
        form = ServiceTypeForm(instance=instance)
    
    return render(request, 'service_type/create.html', {
        'form': form,
        'title': 'Edit Service Type'
    })

@login_required
def service_type_delete(request, id):
    instance = get_object_or_404(ServiceType, id=id, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, 'Service Type deleted successfully.')
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
    branch = getattr(request.user, 'managed_branch', None)

    if not branch:
        messages.error(request, "No branch assigned")
        return redirect('dashboard')

    services = BranchService.objects.filter(
        branch=branch,
        is_enabled=True
    ).select_related('service')

    data = [{
        'branch': branch,
        'services': services
    }]

    return render(request, 'branch/branch_service_list.html', {'data': data})
    

@login_required
def branch_service_manage(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)

    services = ServiceType.objects.all()

    existing = BranchService.objects.filter(branch=branch, is_enabled=True)
    existing_service_ids = existing.values_list('service_id', flat=True)

    if request.method == 'POST':
        selected_services = request.POST.getlist('services')

        # Disable all first
        BranchService.objects.filter(branch=branch).update(is_enabled=False)

        for service in services:
            is_checked = str(service.id) in selected_services

            obj, created = BranchService.objects.get_or_create(
                auto_id = get_auto_id(BranchService),
                creator = request.user,
                branch=branch,
                service=service
            )

            
            obj.is_enabled = is_checked
            obj.save()

        return redirect('branch_service_list')  # better redirect

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