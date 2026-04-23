from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from .models import ServiceType, Service
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
    queryset = Service.objects.filter(is_deleted=False).select_related('company', 'service_type').order_by('-date_added')

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


