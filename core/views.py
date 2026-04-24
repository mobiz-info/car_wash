from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
import datetime
from datetime import date,datetime

from .models import *
from .forms import UserCreationAdminForm, UserProfileForm, RoleForm
from core.functions import get_auto_id
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'


# ==========================================
# USER MANAGEMENT MODULE
# ==========================================

@login_required
def user_list(request):
    search_query = request.GET.get('search', '')
    users = User.objects.all().order_by('-date_joined')
    if search_query:
        users = users.filter(username__icontains=search_query) | users.filter(email__icontains=search_query)

    paginator = Paginator(users, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search_query,
        'title': 'System Users'
    }
    return render(request, 'user/list.html', context)

@login_required
def user_create(request):
    if request.method == 'POST':
        user_form = UserCreationAdminForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()
            
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.auto_id = get_auto_id(UserProfile)
            profile.creator = request.user
            profile.save()
            return redirect('user_list')
    else:
        user_form = UserCreationAdminForm()
        profile_form = UserProfileForm()

    return render(request, 'user/create.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': 'Add New User'
    })

# ==========================================
# ROLE MANAGEMENT
# ==========================================

@login_required
def role_list(request):
    search_query = request.GET.get('search', '')
    roles = Role.objects.filter(is_deleted=False).order_by('-date_added')
    if search_query:
        roles = roles.filter(name__icontains=search_query)

    paginator = Paginator(roles, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'user/role_list.html', {
        'page_obj': page_obj,
        'search': search_query,
        'title': 'System Roles'
    })

@login_required
def role_create(request):
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save(commit=False)
            role.auto_id = get_auto_id(Role)
            role.creator = request.user
            role.save()
            messages.success(request, 'Role created successfully.')
            return redirect('role_list')
    else:
        form = RoleForm()
    
    return render(request, 'user/role_create.html', {
        'form': form,
        'title': 'Create Role'
    })

@login_required
def role_edit(request, pk):
    role = get_object_or_404(Role, pk=pk, is_deleted=False)
    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            role = form.save(commit=False)
            role.updater = request.user
            role.save()
            messages.success(request, 'Role updated successfully.')
            return redirect('role_list')
    else:
        form = RoleForm(instance=role)
    
    return render(request, 'user/role_create.html', {
        'form': form,
        'title': 'Edit Role',
        'is_edit': True
    })

@login_required
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk, is_deleted=False)
    role.is_deleted = True
    role.save()
    messages.success(request, 'Role deleted successfully.')
    return redirect('role_list')


@login_required
def log_list(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Use today's date as the default if no date is provided
    if not start_date:
        start_date = date.today()
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

    if not end_date:
        end_date = date.today()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    logs = Processing_Log.objects.filter(created_date__date__range=(start_date, end_date)).order_by("-created_date")
    
    context = {
        'logs': logs,
    }
    
    return render(request, 'log_list.html', context)

