from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from .functions import *
from .models import *
from .forms import *
from .models import Country, Client, UserProfile, Role
from .forms import CountryForm, ClientForm, UserCreationAdminForm, UserProfileForm, RoleForm

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'


@login_required
def country_list(request):
    search = request.GET.get('search', '')

    queryset = Country.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'country/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def country_create(request):
    form = CountryForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Country)
            instance.creator = request.user

            instance.save()

            messages.success(request, "Country created successfully")
            return redirect('country_list')

    return render(request, 'country/create.html', {
        'form': form,
        'title': 'Create Country'
    })


@login_required
def country_edit(request, id):
    instance = get_object_or_404(Country, id=id, is_deleted=False)
    form = CountryForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Country)
            instance.updater = request.user

            instance.save()
            
            messages.success(request, "Country updated successfully")
            return redirect('country_list')

    return render(request, 'country/create.html', {
        'form': form,
        'title': 'Edit Country'
    })


@login_required
def country_delete(request, id):
    instance = get_object_or_404(Country, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Country deleted successfully")
    return redirect('country_list')


@login_required
def state_list(request):
    search = request.GET.get('search', '')

    queryset = State.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'state/list.html', {
        'page_obj': page_obj,
        'search': search
    })

@login_required   
def state_create(request):
    form = StateForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(State)
            instance.creator = request.user

            instance.save()

            messages.success(request, "State created successfully")
            return redirect('state_list')

    return render(request, 'state/create.html', {
        'form': form,
        'title': 'Create State'
    })

@login_required
def state_edit(request, id):
    instance = get_object_or_404(State, id=id, is_deleted=False)
    form = StateForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            # instance.auto_id = get_auto_id(State)
            instance.updater = request.user

            instance.save()
            
            messages.success(request, "State updated successfully")
            return redirect('state_list')

    return render(request, 'state/create.html', {
        'form': form,
        'title': 'Edit State'
    })


@login_required
def state_delete(request, id):
    instance = get_object_or_404(State, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "State deleted successfully")
    return redirect('state_list')


@login_required
def district_list(request):
    search = request.GET.get('search', '')

    queryset = District.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'district/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def district_create(request):
    form = DistrictForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(District)
            instance.creator = request.user

            instance.save()

            messages.success(request, "District created successfully")
            return redirect('district_list')

    return render(request, 'district/create.html', {
        'form': form,
        'title': 'Create District'
    })


@login_required
def district_edit(request, id):
    instance = get_object_or_404(District, id=id, is_deleted=False)
    form = DistrictForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(District)
            instance.updater = request.user

            instance.save()
            
            messages.success(request, "District updated successfully")
            return redirect('district_list')

    return render(request, 'district/create.html', {
        'form': form,
        'title': 'Edit District'
    })


@login_required
def district_delete(request, id):
    instance = get_object_or_404(District, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "District deleted successfully")
    return redirect('district_list')



@login_required
def area_list(request):
    search = request.GET.get('search', '')

    queryset = Area.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'area/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def area_create(request):
    form = AreaForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Area)
            instance.creator = request.user

            instance.save()

            messages.success(request, "Area created successfully")
            return redirect('area_list')

    return render(request, 'area/create.html', {
        'form': form,
        'title': 'Create Area'
    })


@login_required
def area_edit(request, id):
    instance = get_object_or_404(Area, id=id, is_deleted=False)
    form = AreaForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Area)
            instance.updater = request.user

            instance.save()
            
            messages.success(request, "Area updated successfully")
            return redirect('area_list')

    return render(request, 'area/create.html', {
        'form': form,
        'title': 'Edit Area'
    })


@login_required
def area_delete(request, id):
    instance = get_object_or_404(Area, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Area deleted successfully")
    return redirect('area_list')

          
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
    form = ClientForm(request.POST or None)
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
    form = ClientForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   
            instance.auto_id = get_auto_id(Client)
            instance.save()
            messages.success(request, "Client updated successfully")
            return redirect('client_list')
    return render(request, 'client/create.html', {
        'form': form,
        'title': 'Edit Client'
    })


@login_required
def client_delete(request, id):
    instance = get_object_or_404(Client, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Client deleted successfully")
    return redirect('client_list')


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
