from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.models import User
import datetime
from datetime import date,datetime,timedelta
from django.utils import timezone


from .models import *
from client_management.models import Subscription
from .forms import UserCreationAdminForm, UserProfileForm, RoleForm, UserEditForm
from core.functions import get_auto_id

# Roles allowed to access this admin portal
ALLOWED_ROLES = ('SUPER_ADMIN', 'COMPANY_ADMIN', 'BRANCH_ADMIN')

@csrf_protect
def custom_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Check if user has a profile with an allowed role
            try:
                role_name = user.profile.role.name
            except Exception:
                role_name = None

            if role_name in ALLOWED_ROLES:
                login(request, user)
                return redirect('dashboard')
            else:
                # Authenticated but not an allowed role — deny access
                error = "You do not have permission to access this portal."
        else:
            error = "Invalid username or password."

    return render(request, 'auth/login.html', {'error': error})
from client_management.models import Client, Branch, Staff, CustomerVehicle, Subscription, RenewalTransaction
from finance_management.models import Invoice, Receipt
from django.db.models import Sum, Count, Q

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        try:
            role_name = user.profile.role.name
        except Exception:
            role_name = None
            
        context['subscription_notification'] = None
        context['role_name'] = role_name

        if role_name == 'SUPER_ADMIN':
            today = timezone.now().date()
            
            total_companies = Client.objects.filter(is_deleted=False).count()
            active_companies = Client.objects.filter(is_deleted=False, status=True).count()
            total_branches = Branch.objects.filter(is_deleted=False).count()
            total_staff = Staff.objects.filter(is_deleted=False).count()
            total_users = User.objects.filter(is_active=True).count()
            total_vehicles = CustomerVehicle.objects.filter(is_deleted=False).count()
            
            # Financial & Invoicing metrics
            inv_qs = Invoice.objects.filter(is_deleted=False)
            total_invoices = inv_qs.count()
            total_revenue_sum = inv_qs.aggregate(s=Sum('total'))['s'] or 0.0
            
            sub_qs = Subscription.objects.filter(is_deleted=False)
            sub_revenue_sum = sub_qs.aggregate(s=Sum('usage_fee'))['s'] or 0.0
            
            active_subs_count = sub_qs.filter(end_date__gte=today).count()
            expiring_subs_count = sub_qs.filter(end_date__gte=today, end_date__lte=today + timedelta(days=30)).count()

            context['stats'] = [
                {'label': 'Total Companies', 'value': f"{active_companies} / {total_companies}", 'icon': 'ph-fill ph-buildings', 'color': '#3b82f6', 'subtext': 'Active / Total'},
                {'label': 'Total Branches', 'value': total_branches, 'icon': 'ph-fill ph-git-branch', 'color': '#10b981', 'subtext': 'Across all companies'},
                {'label': 'Subscription Revenue', 'value': f"₹{sub_revenue_sum:,.2f}", 'icon': 'ph-fill ph-currency-circle-dollar', 'color': '#059669', 'subtext': 'Total usage fees'},
                {'label': 'System Invoices', 'value': total_invoices, 'icon': 'ph-fill ph-receipt', 'color': '#6366f1', 'subtext': f"₹{total_revenue_sum:,.2f} Total"},
                {'label': 'Vehicles Registered', 'value': total_vehicles, 'icon': 'ph-fill ph-car', 'color': '#f59e0b', 'subtext': 'Serviced in platform'},
                {'label': 'Active Subscriptions', 'value': active_subs_count, 'icon': 'ph-fill ph-check-circle', 'color': '#0284c7', 'subtext': f"{expiring_subs_count} due in 30 days"},
                {'label': 'Total Staff', 'value': total_staff, 'icon': 'ph-fill ph-users', 'color': '#ec4899', 'subtext': 'All branch employees'},
                {'label': 'Active Users', 'value': total_users, 'icon': 'ph-fill ph-user-check', 'color': '#8b5cf6', 'subtext': 'Logins active'},
            ]

            # Recent Companies List
            context['recent_companies'] = Client.objects.filter(is_deleted=False).order_by('-date_added')[:6]
            
            # Expiring Subscriptions List
            context['expiring_subscriptions'] = Subscription.objects.filter(
                is_deleted=False,
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30)
            ).select_related('company').order_by('end_date')[:6]

            # Recent Invoices List
            context['recent_invoices'] = Invoice.objects.filter(
                is_deleted=False
            ).select_related('branch', 'branch__company', 'customer').order_by('-date_added')[:6]

        elif role_name == 'COMPANY_ADMIN':
            company = user.profile.company
            if company:
                context['stats'] = [
                    {'label': 'Total Branches', 'value': Branch.objects.filter(company=company, is_deleted=False).count(), 'icon': 'ph-fill ph-git-branch', 'color': '#3b82f6'},
                    {'label': 'Total Staff', 'value': Staff.objects.filter(company=company, is_deleted=False).count(), 'icon': 'ph-fill ph-users', 'color': '#10b981'},
                    {'label': 'Active Branches', 'value': Branch.objects.filter(company=company, is_deleted=False).count(), 'icon': 'ph-fill ph-buildings', 'color': '#f59e0b'},
                ]
                
            # SUBSCRIPTION CHECK
            subscription = Subscription.objects.filter(
                    company=company
                ).order_by('-end_date').first()

            if subscription:

                today = timezone.now().date()
                days_left = (subscription.end_date - today).days

                if days_left < 0:
                    context['subscription_notification'] = {
                            'type': 'danger',
                            'message': 'Your subscription has expired.'
                        }

                elif days_left == 0:
                    context['subscription_notification'] = {
                            'type': 'danger',
                            'message': 'Your subscription expires today.'
                        }

                elif days_left == 1:
                    context['subscription_notification'] = {
                            'type': 'warning',
                            'message': 'Your subscription will expire tomorrow.'
                        }

                elif days_left <= 7:
                    context['subscription_notification'] = {
                            'type': 'warning',
                            'message': f'Your subscription will expire in {days_left} days.'
                        }

            else:
                context['stats'] = []
            

        elif role_name == 'BRANCH_ADMIN':
            try:
                branch = user.managed_branch
                company = branch.company if branch else None
            except Exception:
                branch = None
                company = None

            if branch:
                context['stats'] = [
                    {'label': 'Branch Staff', 'value': Staff.objects.filter(branch=branch, is_deleted=False).count(), 'icon': 'ph-fill ph-users', 'color': '#3b82f6'},
                    {'label': 'Branch', 'value': branch.name, 'icon': 'ph-fill ph-git-branch', 'color': '#10b981'},
                    {'label': 'Company', 'value': company.company_name if company else '-', 'icon': 'ph-fill ph-buildings', 'color': '#f59e0b'},
                ]
            else:
                context['stats'] = []
        # App users who opened/used app today
        today_date = timezone.now().date()
        today_app_users = UserProfile.objects.filter(
            last_app_open__date=today_date
        ).select_related('user', 'role', 'company').order_by('-last_app_open')

        if role_name == 'COMPANY_ADMIN' and hasattr(user, 'profile') and user.profile and user.profile.company:
            today_app_users = today_app_users.filter(company=user.profile.company)
        elif role_name == 'BRANCH_ADMIN':
            try:
                branch = getattr(user, 'managed_branch', None)
                if branch and branch.company:
                    today_app_users = today_app_users.filter(company=branch.company)
            except Exception:
                pass

        context['today_app_users'] = today_app_users
        context['today_app_users_count'] = today_app_users.count()

        return context



# ==========================================
# USER MANAGEMENT MODULE
# ==========================================

@login_required
def user_list(request):
    search_query = request.GET.get('search', '')
    users = User.objects.exclude(
        profile__role__name='SUPER_ADMIN'
    ).order_by('-date_joined')

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
        role_id = request.POST.get('role')
        role = Role.objects.filter(id=role_id).first()

        user_form = UserCreationAdminForm(request.POST, role=role)
        profile_form = UserProfileForm(request.POST)

        
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            profile = profile_form.save(commit=False)
            profile.user = user
            profile.auto_id = get_auto_id(UserProfile)
            profile.creator = request.user
            profile.raw_password = user_form.cleaned_data.get("password")
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


@login_required
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user_obj)
    if request.method == 'POST':
        if form.is_valid():
            role = form.save(commit=False)
            role.auto_id = get_auto_id(User)
            role.creator = request.user
            role.save()
            messages.success(request, f"User '{user_obj.username}' updated successfully.")
            return redirect('user_list')
    return render(request, 'user/edit.html', {
        'form': form,
        'title': f'Edit User — {user_obj.username}',
        'user_obj': user_obj,
    })


@login_required
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('user_list')
    username = user_obj.username
    user_obj.delete()
    messages.success(request, f"User '{username}' deleted successfully.")
    return redirect('user_list')

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

