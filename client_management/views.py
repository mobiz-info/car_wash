from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import JsonResponse
from .models import Client, Subscription, Branch, Staff
from .forms import ClientForm, SubscriptionForm, BranchForm, StaffForm
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
