import json
from decimal import Decimal
from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.db.models import Q
from django.db import IntegrityError
from decimal import Decimal

from .models import *
from .forms import *
from core.functions import get_auto_id


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
def vehicle_type_list(request):
    search = request.GET.get('search', '')
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        data = VehicleType.objects.filter(company__isnull=True, is_deleted=False)
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)
        data = VehicleType.objects.filter(
            Q(company=company) | Q(company__isnull=True),
            is_deleted=False
        )

    if search:
        data = data.filter(name__icontains=search)

    data = data.order_by('name')
    paginator = Paginator(data, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'vehicle_type/list.html', {
        'data': page_obj,
        'page_obj': page_obj,
        'search': search
    })

@login_required
def vehicle_type_create(request):
    form = VehicleTypeForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleType)

            role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
            role_name = role_name.name if role_name else None

            if role_name == "SUPER_ADMIN" or request.user.is_superuser:
                company = None
            else:
                company = getattr(getattr(request.user, 'profile', None), 'company', None)

            instance.company = company
            instance.save()
            messages.success(request, "Vehicle Type created successfully")
            return redirect('vehicle_type_list')

    return render(request, 'vehicle_type/create.html', {
        'form': form,
        'title': 'Create Vehicle Type'
    })
    
    
@login_required
def vehicle_type_edit(request, id):
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        instance = get_object_or_404(VehicleType, id=id, is_deleted=False)
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)
        instance = VehicleType.objects.filter(id=id, is_deleted=False).first()
        if not instance or instance.company != company:
            messages.error(request, "Superadmin created vehicle types cannot be edited.")
            return redirect('vehicle_type_list')

    form = VehicleTypeForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Vehicle Type updated successfully")
            return redirect('vehicle_type_list')

    return render(request, 'vehicle_type/create.html', {
        'form': form,
        'title': 'Edit Vehicle Type'
    })
    
    
@login_required
def vehicle_type_delete(request, id):
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        instance = get_object_or_404(VehicleType, id=id)
        instance.is_deleted = True
        instance.save()
        VehicleTypeModel.objects.filter(vehicle_type=instance).update(is_deleted=True)
        messages.success(request, "Vehicle Type deleted successfully")
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)
        instance = VehicleType.objects.filter(id=id, is_deleted=False).first()
        if instance and instance.company == company:
            instance.is_deleted = True
            instance.save()
            VehicleTypeModel.objects.filter(vehicle_type=instance).update(is_deleted=True)
            messages.success(request, "Vehicle Type deleted successfully")
        else:
            messages.error(request, "Superadmin created vehicle types cannot be deleted.")

    return redirect('vehicle_type_list')


@login_required
def vehicle_type_model_list(request):
    search = request.GET.get('search', '')
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        data = VehicleTypeModel.objects.filter(company__isnull=True, is_deleted=False, vehicle_type__is_deleted=False)
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)
        data = VehicleTypeModel.objects.filter(
            Q(company=company) | Q(company__isnull=True),
            is_deleted=False,
            vehicle_type__is_deleted=False
        )
        if company:
            data = data.exclude(disabled_companies=company)

    data = data.select_related('vehicle_type', 'company', 'emission_standard')

    if search:
        data = data.filter(
            Q(name__icontains=search) |
            Q(vehicle_type__name__icontains=search)
        )

    data = data.order_by('vehicle_type__name', 'name')

    paginator = Paginator(data, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'vehicle_type_model/list.html',
        {
            'data': page_obj,
            'page_obj': page_obj,
            'search': search
        }
    )

@login_required
def emission_standard_list(request):
    search = request.GET.get('search', '')
    data = EmissionStandard.objects.filter(is_deleted=False)
    if search:
        data = data.filter(Q(name__icontains=search) | Q(fuel_type__icontains=search))
    data = data.order_by('validity_months', 'name')
    paginator = Paginator(data, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'emission_standard/list.html', {
        'data': page_obj,
        'page_obj': page_obj,
        'search': search,
        'title': 'Emission Standards Master'
    })

@login_required
def emission_standard_create(request):
    form = EmissionStandardForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(EmissionStandard)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Emission Standard created successfully.")
            return redirect('emission_standard_list')
    return render(request, 'emission_standard/create.html', {
        'form': form,
        'title': 'Create Emission Standard'
    })

@login_required
def emission_standard_edit(request, id):
    instance = get_object_or_404(EmissionStandard, id=id, is_deleted=False)
    form = EmissionStandardForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Emission Standard updated successfully.")
            return redirect('emission_standard_list')
    return render(request, 'emission_standard/create.html', {
        'form': form,
        'title': 'Edit Emission Standard'
    })

@login_required
def emission_standard_delete(request, id):
    instance = get_object_or_404(EmissionStandard, id=id, is_deleted=False)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Emission Standard deleted successfully.")
    return redirect('emission_standard_list')

@login_required
def vehicle_type_model_toggle_enable(request, id):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not company:
        messages.error(request, "Company profile not found.")
        return redirect('vehicle_type_model_list')

    instance = get_object_or_404(VehicleTypeModel, id=id, company__isnull=True, is_deleted=False)

    if instance.disabled_companies.filter(id=company.id).exists():
        instance.disabled_companies.remove(company)
        messages.success(request, f"Global segment '{instance.name}' has been ENABLED for your company.")
    else:
        instance.disabled_companies.add(company)
        messages.success(request, f"Global segment '{instance.name}' has been DISABLED for your company.")

    return redirect('vehicle_type_model_list')

@login_required
def vehicle_type_model_create(request):
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        company = None
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)

    form = VehicleTypeModelForm(request.POST or None, company=company)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleTypeModel)
            instance.creator = request.user
            instance.company = company
            name = instance.name.strip() if instance.name else ''

            existing = VehicleTypeModel.objects.filter(
                company=company,
                vehicle_type=instance.vehicle_type,
                name__iexact=name
            ).first()

            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.emission_standard = instance.emission_standard
                    existing.is_active = instance.is_active
                    existing.updater = request.user
                    existing.save()
                    if company:
                        from client_management.models import Branch
                        for b in Branch.objects.filter(company=company, is_deleted=False):
                            if b.enabled_vehicle_segments.exists():
                                b.enabled_vehicle_segments.add(existing)
                    messages.success(request, f"Vehicle Segment '{existing.name}' restored and updated successfully.")
                    return redirect('vehicle_type_model_list')
                else:
                    form.add_error('name', f"A vehicle segment named '{name}' already exists for this vehicle type.")
            else:
                try:
                    instance.save()
                    if company:
                        from client_management.models import Branch
                        for b in Branch.objects.filter(company=company, is_deleted=False):
                            if b.enabled_vehicle_segments.exists():
                                b.enabled_vehicle_segments.add(instance)
                    messages.success(request, "Vehicle Segment created successfully")
                    return redirect('vehicle_type_model_list')
                except IntegrityError:
                    form.add_error('name', f"A vehicle segment named '{name}' already exists for this vehicle type.")

    return render(request, 'vehicle_type_model/create.html', {
        'form': form,
        'title': 'Create Vehicle Segment'
    })


@login_required
def vehicle_type_model_edit(request, id):
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        instance = get_object_or_404(VehicleTypeModel, id=id, is_deleted=False)
        company = None
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)
        instance = VehicleTypeModel.objects.filter(id=id, is_deleted=False).first()
        if not instance or instance.company != company:
            messages.error(request, "Superadmin created segments cannot be edited.")
            return redirect('vehicle_type_model_list')

    form = VehicleTypeModelForm(request.POST or None, instance=instance, company=company)

    if request.method == 'POST':
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updater = request.user
            if role_name != "SUPER_ADMIN" and not request.user.is_superuser:
                company = getattr(getattr(request.user, 'profile', None), 'company', None)
            else:
                company = obj.company

            obj.company = company
            name = obj.name.strip() if obj.name else ''

            existing = VehicleTypeModel.objects.filter(
                company=company,
                vehicle_type=obj.vehicle_type,
                name__iexact=name
            ).exclude(id=instance.id).first()

            if existing:
                if existing.is_deleted:
                    existing.delete()
                    try:
                        obj.save()
                        messages.success(request, "Vehicle Segment updated successfully")
                        return redirect('vehicle_type_model_list')
                    except IntegrityError:
                        form.add_error('name', f"A vehicle segment named '{name}' already exists for this vehicle type.")
                else:
                    form.add_error('name', f"A vehicle segment named '{name}' already exists for this vehicle type.")
            else:
                try:
                    obj.save()
                    messages.success(request, "Vehicle Segment updated successfully")
                    return redirect('vehicle_type_model_list')
                except IntegrityError:
                    form.add_error('name', f"A vehicle segment named '{name}' already exists for this vehicle type.")

    return render(request, 'vehicle_type_model/create.html', {
        'form': form,
        'title': 'Edit Vehicle Segment'
    })


@login_required
def vehicle_type_model_delete(request, id):
    role_name = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role_name.name if role_name else None

    if role_name == "SUPER_ADMIN" or request.user.is_superuser:
        instance = get_object_or_404(VehicleTypeModel, id=id, is_deleted=False)
        instance.is_deleted = True
        instance.save()
        messages.success(request, "Vehicle Segment deleted successfully")
    else:
        company = getattr(getattr(request.user, 'profile', None), 'company', None)
        instance = VehicleTypeModel.objects.filter(id=id, is_deleted=False).first()
        if instance and instance.company == company:
            instance.is_deleted = True
            instance.save()
            messages.success(request, "Vehicle Segment deleted successfully")
        else:
            messages.error(request, "Superadmin created segments cannot be deleted.")

    return redirect('vehicle_type_model_list')



# ==========================================
# SCHEME TYPE
# ==========================================

from .models import SchemeType

@login_required
def scheme_type_list(request):
    search = request.GET.get('search', '')
    queryset = SchemeType.objects.filter(is_deleted=False)
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'scheme_type/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def scheme_type_create(request):
    form = SchemeTypeForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(SchemeType)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Scheme Type created successfully")
            return redirect('scheme_type_list')
    return render(request, 'scheme_type/create.html', {'form': form, 'title': 'Create Scheme Type'})


@login_required
def scheme_type_edit(request, id):
    instance = get_object_or_404(SchemeType, id=id, is_deleted=False)
    form = SchemeTypeForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Scheme Type updated successfully")
            return redirect('scheme_type_list')
    return render(request, 'scheme_type/create.html', {'form': form, 'title': 'Edit Scheme Type'})


@login_required
def scheme_type_delete(request, id):
    instance = get_object_or_404(SchemeType, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Scheme Type deleted successfully")
    return redirect('scheme_type_list')



# ==========================================
# EXPENSE HEAD
# ==========================================


@login_required
def expense_head_list(request):

    company = request.user.profile.company

    search = request.GET.get('search', '')

    from django.db.models import Q

    role_name = request.user.profile.role.name

    if role_name == "SUPER_ADMIN":

        queryset = ExpenseHead.objects.filter(
            is_deleted=False,company=None
        )

    else:

        company = request.user.profile.company

        queryset = ExpenseHead.objects.filter(
            Q(company=company) |
            Q(company__isnull=True),
            is_deleted=False
        )

    if search:

        queryset = queryset.filter(
            name__icontains=search
        )

    paginator = Paginator(queryset, 10)

    page_obj = paginator.get_page(
        request.GET.get('page')
    )

    return render(
        request,
        'expense_head/list.html',
        {
            'page_obj': page_obj,
            'search': search
        }
    )

@login_required
def expense_head_create(request):

    form = ExpenseHeadForm(request.POST or None)

    if request.method == 'POST':

        if form.is_valid():

            instance = form.save(commit=False)

            instance.auto_id = get_auto_id(ExpenseHead)
            instance.creator = request.user

            if request.user.profile.role.name == "SUPER_ADMIN":

                instance.company = None

            else:

                instance.company = request.user.profile.company

            instance.save()

            messages.success(
                request,
                "Expense Head created successfully"
            )

            return redirect('expense_head_list')

    return render(
        request,
        'expense_head/create.html',
        {
            'form': form,
            'title': 'Create Expense Head'
        }
    )

@login_required
def expense_head_edit(request, id):

    role_name = request.user.profile.role.name

    if role_name == "SUPER_ADMIN":

        instance = get_object_or_404(
            ExpenseHead,
            id=id,
            is_deleted=False
        )

    else:

        company = request.user.profile.company

        instance = get_object_or_404(
            ExpenseHead,
            id=id,
            company=company,
            is_deleted=False
        )

    form = ExpenseHeadForm(
        request.POST or None,
        instance=instance
    )
    if not request.user.is_superuser and instance.company is None:
        messages.error(request, "You cannot edit system expense heads.")
        return redirect('expense_head_list')
    if request.method == "POST":

        if form.is_valid():

            obj = form.save(commit=False)

            obj.updater = request.user

            # Don't change company for global heads
            if role_name != "SUPER_ADMIN":
                obj.company = company

            obj.save()

            messages.success(
                request,
                "Expense Head updated successfully"
            )

            return redirect("expense_head_list")

    return render(
        request,
        "expense_head/create.html",
        {
            "form": form,
            "title": "Edit Expense Head"
        }
    )

@login_required
def expense_head_delete(request, id):

    role_name = request.user.profile.role.name

    if role_name == "SUPER_ADMIN":

        instance = get_object_or_404(
            ExpenseHead,
            id=id,
            is_deleted=False
        )

    else:

        company = request.user.profile.company

        instance = get_object_or_404(
            ExpenseHead,
            id=id,
            company=company,
            is_deleted=False
        )

    # Check if this expense head is protected (Salary or Purchase)
    if not instance.is_deletable:
        messages.error(request, f"Deletion is disabled for '{instance.name}' expense head.")
        return redirect('expense_head_list')

    # Check if trying to delete a system expense head
    if not request.user.is_superuser and instance.company is None:
        messages.error(request, "You cannot delete system expense heads.")
        return redirect('expense_head_list')

    instance.is_deleted = True
    instance.save()
    
    messages.success(
        request,
        "Expense Head deleted successfully"
    )

    return redirect("expense_head_list")


# ==========================================
# EXPENSE ITEM
# ==========================================

from master.models import Expense

@login_required
def expense_item_list(request):
    search = request.GET.get('search', '')
    from django.db.models import Q
    queryset = Expense.objects.filter(is_deleted=False).select_related('expense_head').order_by('expense_head__name', 'name')
    
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(expense_head__name__icontains=search)
        )

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'expense_item/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def expense_item_create(request):
    from master.models import ExpenseHead
    from django.db.models import Q

    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    heads = ExpenseHead.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).order_by('name')

    if request.method == 'POST':
        expense_head_id = request.POST.get('expense_head')
        name = request.POST.get('name', '').strip()

        if not expense_head_id or not name:
            messages.error(request, "Expense Head and Item Name are required.")
        else:
            head = get_object_or_404(ExpenseHead, id=expense_head_id, is_deleted=False)
            item, created = Expense.objects.get_or_create(
                expense_head=head,
                name=name,
                defaults={'auto_id': get_auto_id(Expense), 'creator': request.user}
            )
            if not created and item.is_deleted:
                item.is_deleted = False
                item.save()

            messages.success(request, f"Expense Item '{name}' saved successfully under '{head.name}'")
            return redirect('expense_item_list')

    return render(request, 'expense_item/create.html', {
        'expense_heads': heads,
        'title': 'Create Expense Item'
    })


@login_required
def expense_item_edit(request, id):
    item = get_object_or_404(Expense, id=id, is_deleted=False)
    from master.models import ExpenseHead
    from django.db.models import Q

    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    heads = ExpenseHead.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).order_by('name')

    if request.method == 'POST':
        expense_head_id = request.POST.get('expense_head')
        name = request.POST.get('name', '').strip()

        if not expense_head_id or not name:
            messages.error(request, "Expense Head and Item Name are required.")
        else:
            head = get_object_or_404(ExpenseHead, id=expense_head_id, is_deleted=False)
            item.expense_head = head
            item.name = name
            item.updater = request.user
            item.save()
            messages.success(request, "Expense Item updated successfully.")
            return redirect('expense_item_list')

    return render(request, 'expense_item/create.html', {
        'item': item,
        'expense_heads': heads,
        'title': 'Edit Expense Item'
    })


@login_required
def expense_item_delete(request, id):
    item = get_object_or_404(Expense, id=id)
    item.is_deleted = True
    item.save()
    messages.success(request, "Expense Item deleted successfully.")
    return redirect('expense_item_list')


@login_required
def expense_list(request):

    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    search = request.GET.get('search', '')


    if role_name == 'COMPANY_ADMIN':

        company = getattr(request.user.profile, 'company', None)

        expenses = ExpenseEntry.objects.filter(
            company=company,
            is_deleted=False
        )

    else:

        branch = getattr(request.user, 'managed_branch', None)

        expenses = ExpenseEntry.objects.filter(
            branch=branch,
            is_deleted=False
        )


    if search:

        expenses = expenses.filter(
            expense__name__icontains=search
        )

    expenses = expenses.order_by('-id')

    paginator = Paginator(expenses, 10)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search,
    }

    return render(request, 'expense/list.html', context)

@login_required
def expense_create(request):

    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None
    print("role_name",role_name)

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

        branches = Branch.objects.filter(
            company=company,
            is_deleted=False
        )

    else:

        branch = request.user.managed_branch

        if not branch:
            messages.error(request, "No branch assigned.")
            return redirect('dashboard')

        company = branch.company


    from django.db.models import Q

    expense_heads = ExpenseHead.objects.filter(
        Q(company=company) |
        Q(company__isnull=True),
        is_deleted=False
    ).order_by('name')

    expenses = Expense.objects.filter(
        is_deleted=False
    )

    branches = None
    branch = None
    company = None

    if role_name == 'COMPANY_ADMIN':

        company = getattr(request.user.profile, 'company', None)
        print("company",company)

        branches = Branch.objects.filter(
            company=company,
            is_deleted=False
        )
    else:

        branch = getattr(request.user, 'managed_branch', None)

        if not branch:
            messages.error(request, "No branch assigned.")
            return redirect('dashboard')

        company = branch.company


    if request.method == 'POST':

        expense_head_id = request.POST.get('expense_head')
        expense_name = request.POST.get('expense_name')

        amount = request.POST.get('amount')
        paid_amount = request.POST.get('paid_amount') or amount
        supplier_id = request.POST.get('supplier') or None
        expense_date = request.POST.get('expense_date')
        remarks = request.POST.get('remarks')

        if role_name == 'COMPANY_ADMIN':

            branch_id = request.POST.get('branch')

        else:

            branch_id = branch.id

        expense, created = Expense.objects.get_or_create(
            expense_head_id=expense_head_id,
            name=expense_name,
            defaults={
                'auto_id': get_auto_id(Expense),
                'creator': request.user
            }
        )

        ExpenseEntry.objects.create(
            auto_id=get_auto_id(ExpenseEntry),
            creator=request.user,
            company=company,
            branch_id=branch_id,
            expense=expense,
            amount=amount,
            paid_amount=paid_amount,
            supplier_id=supplier_id,
            expense_date=expense_date,
            remarks=remarks
        )

        messages.success(request, "Expense Created Successfully")
        return redirect('expense_list')

    from client_management.models import Stock, Staff
    from master.models import Supplier
    from django.db.models import Q
    stocks = Stock.objects.filter(
        Q(company=company) | Q(company__isnull=True),
        is_deleted=False
    ).select_related('expense_head')

    staffs = Staff.objects.filter(
        company=company,
        is_deleted=False
    )
    if branch:
        staffs = staffs.filter(branch=branch)

    suppliers = Supplier.objects.filter(
        company=company,
        is_deleted=False
    ).order_by('name')

    context = {
        'expense_heads': expense_heads,
        'expenses': expenses,
        'branches': branches,
        'stocks': stocks,
        'staffs': staffs,
        'suppliers': suppliers,
        'role_name': role_name,
        'title': 'Add Expense'
    }

    return render(request, 'expense/create.html', context)


@login_required
def expense_edit(request, pk):

    if role_name == 'COMPANY_ADMIN':

        expense_entry = get_object_or_404(
            ExpenseEntry,
            pk=pk,
            company=request.user.profile.company,
            is_deleted=False
        )

    else:

        expense_entry = get_object_or_404(
            ExpenseEntry,
            pk=pk,
            branch=request.user.managed_branch,
            is_deleted=False
        )

    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

    else:

        company = request.user.managed_branch.company


    expense_heads = ExpenseHead.objects.filter(
        Q(company=company) |
        Q(company__isnull=True),
        is_deleted=False
    ).order_by('name')

    branches = None
    branch = None

    if role_name == 'COMPANY_ADMIN':

        company = getattr(
            request.user.profile,
            'company',
            None
        )

        branches = Branch.objects.filter(
            company=company,
            is_deleted=False
        )


    else:

        branch = getattr(
            request.user,
            'managed_branch',
            None
        )

        if expense_entry.branch != branch:

            messages.error(
                request,
                "Permission denied"
            )

            return redirect('expense_list')


    if request.method == 'POST':

        expense_head_id = request.POST.get(
            'expense_head'
        )

        expense_name = request.POST.get(
            'expense_name'
        )

        amount = request.POST.get(
            'amount'
        )

        expense_date = request.POST.get(
            'expense_date'
        )

        remarks = request.POST.get(
            'remarks'
        )


        if role_name == 'COMPANY_ADMIN':

            branch_id = request.POST.get(
                'branch'
            )

            expense_entry.branch_id = branch_id

        else:

            expense_entry.branch = branch


        expense, created = Expense.objects.get_or_create(
            expense_head_id=expense_head_id,
            name=expense_name,
            defaults={
                'auto_id': get_auto_id(Expense),
                'creator': request.user
            }
        )
        
        expense_entry.expense = expense

        expense_entry.amount = amount

        expense_entry.expense_date = expense_date

        expense_entry.remarks = remarks

        expense_entry.save()

        messages.success(
            request,
            "Expense Updated Successfully"
        )

        return redirect('expense_list')

    from client_management.models import Stock, Staff
    from django.db.models import Q
    stocks = Stock.objects.filter(
        Q(company=company) | Q(company__isnull=True),
        is_deleted=False
    ).select_related('expense_head')

    staffs = Staff.objects.filter(
        company=company,
        is_deleted=False
    )
    if branch:
        staffs = staffs.filter(branch=branch)

    context = {
        'expense_entry': expense_entry,
        'expense_heads': expense_heads,
        'branches': branches,
        'stocks': stocks,
        'staffs': staffs,
        'role_name': role_name,
        'title': 'Expense Update'
    }

    return render(
        request,
        'expense/create.html',
        context
    )


@login_required
def expense_delete(request, pk):

    if role_name == 'COMPANY_ADMIN':

        expense = get_object_or_404(
            ExpenseEntry,
            pk=pk,
            company=request.user.profile.company,
            is_deleted=False
        )

    else:

        expense = get_object_or_404(
            ExpenseEntry,
            pk=pk,
            branch=request.user.managed_branch,
            is_deleted=False
        )

    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    if role_name != 'COMPANY_ADMIN':

        branch = getattr(request.user, 'managed_branch', None)

        if expense.branch != branch:
            messages.error(request, "Permission denied")
            return redirect('expense_list')

    expense.is_deleted = True
    expense.save()

    messages.success(request, "Expense Deleted Successfully")

    return redirect('expense_list')


# ==========================================
# VEHICLE COLOR
# ==========================================

@login_required
def vehicle_color_list(request):
    search = request.GET.get('search', '')
    queryset = VehicleColor.objects.filter(is_deleted=False)
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'vehicle_color/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def vehicle_color_create(request):
    form = VehicleColorForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleColor)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Vehicle Color created successfully")
            return redirect('vehicle_color_list')
    return render(request, 'vehicle_color/create.html', {'form': form, 'title': 'Create Vehicle Color'})


@login_required
def vehicle_color_edit(request, id):
    instance = get_object_or_404(VehicleColor, id=id, is_deleted=False)
    form = VehicleColorForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Vehicle Color updated successfully")
            return redirect('vehicle_color_list')
    return render(request, 'vehicle_color/create.html', {'form': form, 'title': 'Edit Vehicle Color'})


@login_required
def vehicle_color_delete(request, id):
    instance = get_object_or_404(VehicleColor, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Vehicle Color deleted successfully")
    return redirect('vehicle_color_list')


# ==========================================
# VEHICLE BRAND/MODEL
# ==========================================

@login_required
def vehicle_brand_model_list(request):
    search = request.GET.get('search', '')
    from django.db.models import Q
    queryset = VehicleBrandModel.objects.filter(is_deleted=False).select_related('vehicle_type_model')
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(vehicle_type_model__name__icontains=search)
        )
    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'vehicle_brand_model/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def vehicle_brand_model_create(request):
    form = VehicleBrandModelForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleBrandModel)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Vehicle Brand created successfully")
            return redirect('vehicle_brand_model_list')
    return render(request, 'vehicle_brand_model/create.html', {'form': form, 'title': 'Create Vehicle Brand'})


@login_required
def vehicle_brand_model_edit(request, id):
    instance = get_object_or_404(VehicleBrandModel, id=id, is_deleted=False)
    form = VehicleBrandModelForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Vehicle Brand updated successfully")
            return redirect('vehicle_brand_model_list')
    return render(request, 'vehicle_brand_model/create.html', {'form': form, 'title': 'Edit Vehicle Brand'})


@login_required
def vehicle_brand_model_delete(request, id):
    instance = get_object_or_404(VehicleBrandModel, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Vehicle Brand deleted successfully")
    return redirect('vehicle_brand_model_list')


# ==========================================
# VEHICLE MAKE (MANUFACTURER)
# ==========================================

@login_required
def vehicle_make_list(request):
    search = request.GET.get('search', '')
    queryset = VehicleMake.objects.filter(is_deleted=False)
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'vehicle_make/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def vehicle_make_create(request):
    form = VehicleMakeForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleMake)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Vehicle Make created successfully")
            return redirect('vehicle_make_list')
    return render(request, 'vehicle_make/create.html', {'form': form, 'title': 'Create Vehicle Make'})


@login_required
def vehicle_make_edit(request, id):
    instance = get_object_or_404(VehicleMake, id=id, is_deleted=False)
    form = VehicleMakeForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Vehicle Make updated successfully")
            return redirect('vehicle_make_list')
    return render(request, 'vehicle_make/create.html', {'form': form, 'title': 'Edit Vehicle Make'})


@login_required
def vehicle_make_delete(request, id):
    instance = get_object_or_404(VehicleMake, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Vehicle Make deleted successfully")
    return redirect('vehicle_make_list')


# ==========================================
# SUPPLIER
# ==========================================

@login_required
def supplier_list(request):
    search = request.GET.get('search', '')
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not company:
        queryset = Supplier.objects.filter(is_deleted=False)
    else:
        queryset = Supplier.objects.filter(company=company, is_deleted=False)
        
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'supplier/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def supplier_create(request):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    form = SupplierForm(request.POST or None, company=company)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(Supplier)
            instance.creator = request.user
            instance.company = company
            if getattr(request.user, 'managed_branch', None):
                instance.branch = request.user.managed_branch
            instance.save()
            messages.success(request, "Supplier created successfully")
            return redirect('supplier_list')
    return render(request, 'supplier/create.html', {'form': form, 'title': 'Create Supplier'})


@login_required
def supplier_edit(request, id):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not company:
        instance = get_object_or_404(Supplier, id=id, is_deleted=False)
    else:
        instance = get_object_or_404(Supplier, id=id, company=company, is_deleted=False)
        
    form = SupplierForm(request.POST or None, instance=instance, company=company)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Supplier updated successfully")
            return redirect('supplier_list')
    return render(request, 'supplier/create.html', {'form': form, 'title': 'Edit Supplier'})


@login_required
def supplier_delete(request, id):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not company:
        instance = get_object_or_404(Supplier, id=id)
    else:
        instance = get_object_or_404(Supplier, id=id, company=company)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Supplier deleted successfully")
    return redirect('supplier_list')


# ==========================================
# OIL BRAND MASTER
# ==========================================

@login_required
def oil_brand_list(request):
    search = request.GET.get('search', '')
    queryset = OilBrand.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'oil_brand/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def oil_brand_create(request):
    form = OilBrandForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(OilBrand)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Oil Brand created successfully")
            return redirect('oil_brand_list')
    return render(request, 'oil_brand/create.html', {
        'form': form,
        'title': 'Create Oil Brand'
    })


@login_required
def oil_brand_edit(request, id):
    instance = get_object_or_404(OilBrand, id=id, is_deleted=False)
    form = OilBrandForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Oil Brand updated successfully")
            return redirect('oil_brand_list')
    return render(request, 'oil_brand/create.html', {
        'form': form,
        'title': 'Edit Oil Brand'
    })


@login_required
def oil_brand_delete(request, id):
    instance = get_object_or_404(OilBrand, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Oil Brand deleted successfully")
    return redirect('oil_brand_list')


# ==========================================
# OIL FILTER BRAND MASTER
# ==========================================

@login_required
def oil_filter_brand_list(request):
    search = request.GET.get('search', '')
    queryset = OilFilterBrand.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'oil_filter_brand/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def oil_filter_brand_create(request):
    form = OilFilterBrandForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(OilFilterBrand)
            instance.creator = request.user
            profile = getattr(request.user, 'profile', None)
            instance.company = getattr(profile, 'company', None) if profile else None
            instance.save()
            messages.success(request, "Oil Filter Brand created successfully")
            return redirect('oil_filter_brand_list')
    return render(request, 'oil_filter_brand/create.html', {
        'form': form,
        'title': 'Create Oil Filter Brand'
    })


@login_required
def oil_filter_brand_edit(request, id):
    instance = get_object_or_404(OilFilterBrand, id=id, is_deleted=False)
    form = OilFilterBrandForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Oil Filter Brand updated successfully")
            return redirect('oil_filter_brand_list')
    return render(request, 'oil_filter_brand/create.html', {
        'form': form,
        'title': 'Edit Oil Filter Brand'
    })


@login_required
def oil_filter_brand_delete(request, id):
    instance = get_object_or_404(OilFilterBrand, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Oil Filter Brand deleted successfully")
    return redirect('oil_filter_brand_list')


# ==========================================
# OIL FILTER MASTER
# ==========================================

@login_required
def oil_filter_list(request):
    search = request.GET.get('search', '')
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None

    if company:
        queryset = OilFilter.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False)
    else:
        queryset = OilFilter.objects.filter(is_deleted=False)

    queryset = queryset.select_related('oil_filter_brand')

    if search:
        queryset = queryset.filter(
            Q(oil_filter_brand__name__icontains=search) |
            Q(name__icontains=search)
        )

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'oil_filter/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def oil_filter_create(request):
    form = OilFilterForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(OilFilter)
            instance.creator = request.user
            profile = getattr(request.user, 'profile', None)
            instance.company = getattr(profile, 'company', None) if profile else None
            instance.save()
            messages.success(request, "Oil Filter created successfully")
            return redirect('oil_filter_list')
    return render(request, 'oil_filter/create.html', {
        'form': form,
        'title': 'Create Oil Filter'
    })


@login_required
def oil_filter_edit(request, id):
    instance = get_object_or_404(OilFilter, id=id, is_deleted=False)
    form = OilFilterForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Oil Filter updated successfully")
            return redirect('oil_filter_list')
    return render(request, 'oil_filter/create.html', {
        'form': form,
        'title': 'Edit Oil Filter'
    })


@login_required
def oil_filter_delete(request, id):
    instance = get_object_or_404(OilFilter, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Oil Filter deleted successfully")
    return redirect('oil_filter_list')


# ==========================================
# OIL GRADE MASTER
# ==========================================

@login_required
def oil_grade_list(request):
    search = request.GET.get('search', '')
    queryset = OilGrade.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'oil_grade/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def oil_grade_create(request):
    form = OilGradeForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(OilGrade)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Oil Grade created successfully")
            return redirect('oil_grade_list')
    return render(request, 'oil_grade/create.html', {
        'form': form,
        'title': 'Create Oil Grade'
    })


@login_required
def oil_grade_edit(request, id):
    instance = get_object_or_404(OilGrade, id=id, is_deleted=False)
    form = OilGradeForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Oil Grade updated successfully")
            return redirect('oil_grade_list')
    return render(request, 'oil_grade/create.html', {
        'form': form,
        'title': 'Edit Oil Grade'
    })


@login_required
def oil_grade_delete(request, id):
    instance = get_object_or_404(OilGrade, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Oil Grade deleted successfully")
    return redirect('oil_grade_list')


# ==========================================
# OIL PRODUCT MASTER
# ==========================================

@login_required
def oil_product_list(request):
    search = request.GET.get('search', '')
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None

    if company:
        queryset = OilProduct.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False)
    else:
        queryset = OilProduct.objects.filter(is_deleted=False)

    queryset = queryset.select_related('oil_brand', 'oil_grade', 'vehicle_type', 'vehicle_make')

    if search:
        queryset = queryset.filter(
            Q(oil_brand__name__icontains=search) |
            Q(oil_grade__name__icontains=search) |
            Q(name__icontains=search) |
            Q(vehicle_make__name__icontains=search) |
            Q(vehicle_type__name__icontains=search)
        )

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'oil_product/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def oil_product_create(request):
    form = OilProductForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(OilProduct)
            instance.creator = request.user
            profile = getattr(request.user, 'profile', None)
            instance.company = getattr(profile, 'company', None) if profile else None
            instance.save()
            messages.success(request, "Oil Product created successfully")
            return redirect('oil_product_list')
    return render(request, 'oil_product/create.html', {
        'form': form,
        'title': 'Create Oil Product'
    })


@login_required
def oil_product_edit(request, id):
    instance = get_object_or_404(OilProduct, id=id, is_deleted=False)
    form = OilProductForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Oil Product updated successfully")
            return redirect('oil_product_list')
    return render(request, 'oil_product/create.html', {
        'form': form,
        'title': 'Edit Oil Product'
    })


@login_required
def oil_product_delete(request, id):
    instance = get_object_or_404(OilProduct, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Oil Product deleted successfully")
    return redirect('oil_product_list')


# ==========================================
# TYRE BRAND MASTER
# ==========================================

@login_required
def tyre_brand_list(request):
    search = request.GET.get('search', '')
    company = request.user.profile.company
    queryset = TyreBrand.objects.filter(company=company, is_deleted=False)

    if search:
        queryset = queryset.filter(brand__icontains=search)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'tyre_brand/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def tyre_brand_create(request):
    form = TyreBrandForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(TyreBrand)
            instance.creator = request.user
            instance.company = request.user.profile.company
            instance.save()
            messages.success(request, "Tyre Brand created successfully")
            return redirect('tyre_brand_list')
    return render(request, 'tyre_brand/create.html', {
        'form': form,
        'title': 'Create Tyre Brand'
    })


@login_required
def tyre_brand_edit(request, id):
    company = request.user.profile.company
    instance = get_object_or_404(TyreBrand, id=id, company=company, is_deleted=False)
    form = TyreBrandForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Tyre Brand updated successfully")
            return redirect('tyre_brand_list')
    return render(request, 'tyre_brand/create.html', {
        'form': form,
        'title': 'Edit Tyre Brand'
    })


@login_required
def tyre_brand_delete(request, id):
    company = request.user.profile.company
    instance = get_object_or_404(TyreBrand, id=id, company=company)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Tyre Brand deleted successfully")
    return redirect('tyre_brand_list')


# ==========================================
# OIL PRODUCT PRICE MASTER
# ==========================================

@login_required
def oil_product_price_list(request):
    search = request.GET.get('search', '')
    company = request.user.profile.company
    queryset = OilProductPrice.objects.filter(
        company=company, is_deleted=False
    ).select_related('oil_product', 'vehicle_type', 'vehicle_make')

    if search:
        queryset = queryset.filter(
            Q(oil_product__brand__icontains=search) |
            Q(oil_product__name__icontains=search) |
            Q(vehicle_make__name__icontains=search) |
            Q(vehicle_type__name__icontains=search)
        )

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'oil_product_price/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def oil_product_price_create(request):
    company = request.user.profile.company
    form = OilProductPriceForm(request.POST or None, company=company)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(OilProductPrice)
            instance.creator = request.user
            instance.company = company
            instance.save()
            messages.success(request, "Oil Product Price saved successfully")
            return redirect('oil_product_price_list')
    return render(request, 'oil_product_price/create.html', {
        'form': form,
        'title': 'Add Oil Product Price'
    })


@login_required
def oil_product_price_edit(request, id):
    company = request.user.profile.company
    instance = get_object_or_404(OilProductPrice, id=id, company=company, is_deleted=False)
    form = OilProductPriceForm(request.POST or None, instance=instance, company=company)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Oil Product Price updated successfully")
            return redirect('oil_product_price_list')
    return render(request, 'oil_product_price/create.html', {
        'form': form,
        'title': 'Edit Oil Product Price'
    })


@login_required
def oil_product_price_delete(request, id):
    company = request.user.profile.company
    instance = get_object_or_404(OilProductPrice, id=id, company=company)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Oil Product Price deleted successfully")
    return redirect('oil_product_price_list')


# ==========================================
# TYRE MASTER & STOCK
# ==========================================

@login_required
def tyre_list(request):
    search = request.GET.get('search', '')
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None

    if company:
        queryset = Tyre.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False)
    else:
        queryset = Tyre.objects.filter(is_deleted=False)

    queryset = queryset.select_related('tyre_brand')

    if search:
        queryset = queryset.filter(
            Q(tyre_brand__brand__icontains=search) |
            Q(name__icontains=search) |
            Q(size__icontains=search) |
            Q(pattern_type__icontains=search)
        )

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'tyre/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def tyre_create(request):
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None
    form = TyreForm(request.POST or None, company=company)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(Tyre)
            instance.creator = request.user
            instance.company = company
            instance.save()
            messages.success(request, "Tyre product created successfully")
            return redirect('tyre_list')
    return render(request, 'tyre/create.html', {
        'form': form,
        'title': 'Create Tyre Product'
    })


@login_required
def tyre_edit(request, id):
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None
    if company:
        instance = get_object_or_404(Tyre, id=id, is_deleted=False)
    else:
        instance = get_object_or_404(Tyre, id=id, is_deleted=False)
        
    form = TyreForm(request.POST or None, instance=instance, company=company)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Tyre product updated successfully")
            return redirect('tyre_list')
    return render(request, 'tyre/create.html', {
        'form': form,
        'title': 'Edit Tyre Product'
    })


@login_required
def tyre_delete(request, id):
    instance = get_object_or_404(Tyre, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Tyre product deleted successfully")
    return redirect('tyre_list')


# ==========================================
# BATTERY MAKE MASTER
# ==========================================

@login_required
def battery_make_list(request):
    search = request.GET.get('search', '')
    queryset = BatteryMake.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'battery_make/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def battery_make_create(request):
    form = BatteryMakeForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(BatteryMake)
            instance.creator = request.user
            profile = getattr(request.user, 'profile', None)
            instance.company = getattr(profile, 'company', None) if profile else None
            instance.save()
            messages.success(request, "Battery Make created successfully")
            return redirect('battery_make_list')
    return render(request, 'battery_make/create.html', {
        'form': form,
        'title': 'Create Battery Make'
    })


@login_required
def battery_make_edit(request, id):
    instance = get_object_or_404(BatteryMake, id=id, is_deleted=False)
    form = BatteryMakeForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Battery Make updated successfully")
            return redirect('battery_make_list')
    return render(request, 'battery_make/create.html', {
        'form': form,
        'title': 'Edit Battery Make'
    })


@login_required
def battery_make_delete(request, id):
    instance = get_object_or_404(BatteryMake, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Battery Make deleted successfully")
    return redirect('battery_make_list')


# ==========================================
# BATTERY AMPERE MASTER
# ==========================================

@login_required
def battery_ampere_list(request):
    search = request.GET.get('search', '')
    queryset = BatteryAmpere.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'battery_ampere/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def battery_ampere_create(request):
    form = BatteryAmpereForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(BatteryAmpere)
            instance.creator = request.user
            profile = getattr(request.user, 'profile', None)
            instance.company = getattr(profile, 'company', None) if profile else None
            instance.save()
            messages.success(request, "Battery Ampere created successfully")
            return redirect('battery_ampere_list')
    return render(request, 'battery_ampere/create.html', {
        'form': form,
        'title': 'Create Battery Ampere'
    })


@login_required
def battery_ampere_edit(request, id):
    instance = get_object_or_404(BatteryAmpere, id=id, is_deleted=False)
    form = BatteryAmpereForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Battery Ampere updated successfully")
            return redirect('battery_ampere_list')
    return render(request, 'battery_ampere/create.html', {
        'form': form,
        'title': 'Edit Battery Ampere'
    })


@login_required
def battery_ampere_delete(request, id):
    instance = get_object_or_404(BatteryAmpere, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Battery Ampere deleted successfully")
    return redirect('battery_ampere_list')


# ==========================================
# BATTERY SEGMENT MASTER
# ==========================================

@login_required
def battery_segment_list(request):
    search = request.GET.get('search', '')
    queryset = BatterySegment.objects.filter(is_deleted=False)

    if search:
        queryset = queryset.filter(name__icontains=search)

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'battery_segment/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def battery_segment_create(request):
    form = BatterySegmentForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(BatterySegment)
            instance.creator = request.user
            profile = getattr(request.user, 'profile', None)
            instance.company = getattr(profile, 'company', None) if profile else None
            instance.save()
            messages.success(request, "Battery Segment created successfully")
            return redirect('battery_segment_list')
    return render(request, 'battery_segment/create.html', {
        'form': form,
        'title': 'Create Battery Segment'
    })


@login_required
def battery_segment_edit(request, id):
    instance = get_object_or_404(BatterySegment, id=id, is_deleted=False)
    form = BatterySegmentForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Battery Segment updated successfully")
            return redirect('battery_segment_list')
    return render(request, 'battery_segment/create.html', {
        'form': form,
        'title': 'Edit Battery Segment'
    })


@login_required
def battery_segment_delete(request, id):
    instance = get_object_or_404(BatterySegment, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Battery Segment deleted successfully")
    return redirect('battery_segment_list')


# ==========================================
# BATTERY MASTER & MANAGEMENT
# ==========================================

@login_required
def battery_list(request):
    search = request.GET.get('search', '')
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None

    if company:
        queryset = Battery.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False)
    else:
        queryset = Battery.objects.filter(is_deleted=False)

    queryset = queryset.select_related('make', 'ampere', 'segment')

    if search:
        queryset = queryset.filter(
            Q(make__name__icontains=search) |
            Q(ampere__name__icontains=search) |
            Q(segment__name__icontains=search)
        )

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'battery/list.html', {
        'page_obj': page_obj,
        'search': search
    })


@login_required
def battery_create(request):
    profile = getattr(request.user, 'profile', None)
    company = getattr(profile, 'company', None) if profile else None
    form = BatteryForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(Battery)
            instance.creator = request.user
            instance.company = company
            instance.save()
            messages.success(request, "Battery created successfully")
            return redirect('battery_list')
    return render(request, 'battery/create.html', {
        'form': form,
        'title': 'Add Battery'
    })


@login_required
def battery_edit(request, id):
    instance = get_object_or_404(Battery, id=id, is_deleted=False)
    form = BatteryForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Battery updated successfully")
            return redirect('battery_list')
    return render(request, 'battery/create.html', {
        'form': form,
        'title': 'Edit Battery'
    })


@login_required
def battery_delete(request, id):
    instance = get_object_or_404(Battery, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Battery deleted successfully")
    return redirect('battery_list')


# ==========================================
# STOCK GROUP & SUB-GROUP CRUD
# ==========================================

from master.models import StockGroup, StockSubGroup, PurchaseInvoice, PurchaseInvoiceItem, SupplierPayment
from master.services import process_purchase_invoice_save, update_supplier_payables

@login_required
def stock_group_list(request):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    groups = StockGroup.objects.filter(is_deleted=False)
    if company:
        groups = groups.filter(Q(company=company) | Q(company__isnull=True))
    return render(request, 'stock_group/list.html', {'groups': groups, 'title': 'Stock Groups'})

@login_required
def stock_group_create(request):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            StockGroup.objects.create(
                auto_id=get_auto_id(StockGroup),
                creator=request.user,
                company=company,
                name=name
            )
            messages.success(request, f"Stock Group '{name}' created successfully")
            return redirect('stock_group_list')
        messages.error(request, "Group Name is required")
    return render(request, 'stock_group/create.html', {'title': 'Add Stock Group'})

@login_required
def stock_group_edit(request, id):
    group = get_object_or_404(StockGroup, id=id, is_deleted=False)
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not request.user.is_superuser:
        if group.company is None or group.company != company:
            messages.error(request, "Superadmin Global Stock Groups cannot be edited by companies.")
            return redirect('stock_group_list')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            group.name = name
            group.updater = request.user
            group.save()
            messages.success(request, "Stock Group updated successfully")
            return redirect('stock_group_list')
        messages.error(request, "Group Name is required")
    return render(request, 'stock_group/create.html', {'group': group, 'title': 'Edit Stock Group'})

@login_required
def stock_group_delete(request, id):
    group = get_object_or_404(StockGroup, id=id)
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not request.user.is_superuser:
        if group.company is None or group.company != company:
            messages.error(request, "Superadmin Global Stock Groups cannot be deleted by companies.")
            return redirect('stock_group_list')
    group.is_deleted = True
    group.save()
    messages.success(request, "Stock Group deleted successfully")
    return redirect('stock_group_list')


@login_required
def stock_subgroup_list(request):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    subgroups = StockSubGroup.objects.filter(is_deleted=False).select_related('group')
    if company:
        subgroups = subgroups.filter(Q(company=company) | Q(company__isnull=True))
    return render(request, 'stock_subgroup/list.html', {'subgroups': subgroups, 'title': 'Stock Sub-Groups'})

@login_required
def stock_subgroup_create(request):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    groups = StockGroup.objects.filter(is_deleted=False)
    if company:
        groups = groups.filter(Q(company=company) | Q(company__isnull=True))

    if request.method == 'POST':
        group_id = request.POST.get('group')
        name = request.POST.get('name', '').strip()
        if group_id and name:
            grp = get_object_or_404(StockGroup, id=group_id)
            StockSubGroup.objects.create(
                auto_id=get_auto_id(StockSubGroup),
                creator=request.user,
                company=company,
                group=grp,
                name=name
            )
            messages.success(request, f"Sub-Group '{name}' created successfully under '{grp.name}'")
            return redirect('stock_subgroup_list')
        messages.error(request, "Group and Sub-Group Name are required")
    return render(request, 'stock_subgroup/create.html', {'groups': groups, 'title': 'Add Stock Sub-Group'})

@login_required
def stock_subgroup_edit(request, id):
    subgroup = get_object_or_404(StockSubGroup, id=id, is_deleted=False)
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not request.user.is_superuser:
        if subgroup.company is None or subgroup.company != company:
            messages.error(request, "Superadmin Global Stock Sub-Groups cannot be edited by companies.")
            return redirect('stock_subgroup_list')
    groups = StockGroup.objects.filter(is_deleted=False)
    if company:
        groups = groups.filter(Q(company=company) | Q(company__isnull=True))

    if request.method == 'POST':
        group_id = request.POST.get('group')
        name = request.POST.get('name', '').strip()
        if group_id and name:
            grp = get_object_or_404(StockGroup, id=group_id)
            subgroup.group = grp
            subgroup.name = name
            subgroup.updater = request.user
            subgroup.save()
            messages.success(request, "Stock Sub-Group updated successfully")
            return redirect('stock_subgroup_list')
    return render(request, 'stock_subgroup/create.html', {'subgroup': subgroup, 'groups': groups, 'title': 'Edit Stock Sub-Group'})

@login_required
def stock_subgroup_delete(request, id):
    subgroup = get_object_or_404(StockSubGroup, id=id)
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    if not request.user.is_superuser:
        if subgroup.company is None or subgroup.company != company:
            messages.error(request, "Superadmin Global Stock Sub-Groups cannot be deleted by companies.")
            return redirect('stock_subgroup_list')
    subgroup.is_deleted = True
    subgroup.save()
    messages.success(request, "Stock Sub-Group deleted successfully")
    return redirect('stock_subgroup_list')


# ==========================================
# SENIOR ERP PURCHASE INVOICE SYSTEM
# ==========================================

@login_required
def purchase_invoice_list(request):
    role_name = getattr(getattr(getattr(request.user, 'profile', None), 'role', None), 'name', None)
    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        invoices = PurchaseInvoice.objects.filter(company=company, is_deleted=False)
    else:
        branch = getattr(request.user, 'managed_branch', None)
        invoices = PurchaseInvoice.objects.filter(branch=branch, is_deleted=False)

    invoices = invoices.select_related('supplier', 'branch').order_by('-invoice_date', '-date_added')
    return render(request, 'purchase_invoice/list.html', {'invoices': invoices, 'title': 'Purchase Invoices'})


@login_required
def purchase_invoice_create(request):
    role_name = getattr(getattr(getattr(request.user, 'profile', None), 'role', None), 'name', None)
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    branch = getattr(request.user, 'managed_branch', None)
    if not branch and company:
        branch = Branch.objects.filter(company=company, is_deleted=False).first()

    if not company and branch:
        company = branch.company

    from client_management.models import Stock
    from master.models import Supplier

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        inv_no = request.POST.get('purchase_inv_number', '').strip()
        inv_date = request.POST.get('invoice_date')
        purchase_type = request.POST.get('purchase_type', 'CASH')
        payment_mode = request.POST.get('payment_mode', 'CASH')
        amount_paid = Decimal(str(request.POST.get('amount_paid', 0) or 0))

        bank_name = request.POST.get('bank_name', '').strip()
        cheque_number = request.POST.get('cheque_number', '').strip()
        cheque_date = request.POST.get('cheque_date') or None

        supplier = get_object_or_404(Supplier, id=supplier_id)

        # Parse item rows from dynamic form
        items_data = json.loads(request.POST.get('items_json', '[]'))
        if not items_data:
            messages.error(request, "At least one purchase item is required.")
            return redirect('purchase_invoice_create')

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')
        grand_total = Decimal('0.00')

        parsed_items = []
        for row in items_data:
            stk_id = row.get('stock_id')
            stk = get_object_or_404(Stock, id=stk_id) if stk_id else None
            rate = Decimal(str(row.get('rate', 0)))
            qty = Decimal(str(row.get('qty', 1)))
            tax_pct = Decimal(str(row.get('tax', 0)))
            conv = Decimal(str(row.get('conversion_count', 1)))

            line_sub = rate * qty
            line_tax = line_sub * (tax_pct / Decimal('100'))
            line_total = line_sub + line_tax

            subtotal += line_sub
            tax_total += line_tax
            grand_total += line_total

            parsed_items.append({
                'stock_item': stk,
                'hsn_code': row.get('hsn', getattr(stk, 'hsn_code', '')),
                'rate': rate,
                'quantity': qty,
                'main_unit': row.get('main_unit', getattr(stk, 'main_unit', '')),
                'base_unit': row.get('base_unit', getattr(stk, 'base_unit', '')),
                'conversion_count': conv,
                'tax_percent': tax_pct,
                'tax_amount': line_tax,
                'total_including_tax': line_total,
            })

        balance_to_pay = grand_total - amount_paid
        if balance_to_pay < Decimal('0.00'):
            balance_to_pay = Decimal('0.00')

        invoice = PurchaseInvoice.objects.create(
            auto_id=get_auto_id(PurchaseInvoice),
            creator=request.user,
            company=company,
            branch=branch,
            supplier=supplier,
            purchase_inv_number=inv_no,
            invoice_date=inv_date,
            purchase_type=purchase_type,
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
            amount_paid=amount_paid,
            balance_to_pay=balance_to_pay,
            payment_mode=payment_mode,
            bank_name=bank_name if payment_mode == 'CHEQUE' else '',
            cheque_number=cheque_number if payment_mode == 'CHEQUE' else '',
            cheque_date=cheque_date if payment_mode == 'CHEQUE' else None,
            remarks=request.POST.get('remarks', '')
        )

        for p_item in parsed_items:
            PurchaseInvoiceItem.objects.create(
                auto_id=get_auto_id(PurchaseInvoiceItem),
                creator=request.user,
                purchase_invoice=invoice,
                **p_item
            )

        # Trigger Senior's 4-Way Auto System Sync!
        process_purchase_invoice_save(invoice, creator_user=request.user)

        messages.success(request, f"Purchase Invoice #{inv_no} created & synchronized across Stock, Expense, & Payables!")
        return redirect('purchase_invoice_list')

    from master.models import StockGroup
    if request.user.is_superuser or not company:
        groups = StockGroup.objects.filter(is_deleted=False).order_by('name')
        suppliers = Supplier.objects.filter(is_deleted=False, is_active=True).order_by('name')
        stocks = Stock.objects.filter(is_deleted=False).select_related('group', 'sub_group').order_by('item_name')
    else:
        groups = StockGroup.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).order_by('name')
        suppliers = Supplier.objects.filter(company=company, is_deleted=False, is_active=True).order_by('name')
        stocks = Stock.objects.filter(Q(company=company) | Q(company__isnull=True), is_deleted=False).select_related('group', 'sub_group').order_by('item_name')

    return render(request, 'purchase_invoice/create.html', {
        'suppliers': suppliers,
        'stocks': stocks,
        'groups': groups,
        'title': 'New Purchase Entry'
    })


@login_required
def purchase_invoice_detail(request, id):
    invoice = get_object_or_404(PurchaseInvoice, id=id, is_deleted=False)
    return render(request, 'purchase_invoice/detail.html', {'invoice': invoice, 'title': f"Purchase Inv #{invoice.purchase_inv_number}"})


# ==========================================
# SUPPLIER PAYABLES & SETTLEMENT
# ==========================================

@login_required
def supplier_payables_list(request):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    from master.models import Supplier
    suppliers = Supplier.objects.filter(company=company, is_deleted=False).order_by('name')

    # Recalculate payables for accuracy
    for s in suppliers:
        update_supplier_payables(s)

    return render(request, 'supplier_payables/list.html', {'suppliers': suppliers, 'title': 'Supplier Payables'})


@login_required
def supplier_payment_create(request, supplier_id):
    company = getattr(getattr(request.user, 'profile', None), 'company', None)
    branch = getattr(request.user, 'managed_branch', None)
    if not branch and company:
        branch = Branch.objects.filter(company=company, is_deleted=False).first()

    supplier = get_object_or_404(Supplier, id=supplier_id, is_deleted=False)

    if request.method == 'POST':
        amt = Decimal(str(request.POST.get('amount_paid', 0)))
        pay_date = request.POST.get('payment_date')
        pay_mode = request.POST.get('payment_mode', 'CASH')
        bank_name = request.POST.get('bank_name', '').strip()
        cheque_no = request.POST.get('cheque_number', '').strip()
        cheque_date = request.POST.get('cheque_date') or None

        SupplierPayment.objects.create(
            auto_id=get_auto_id(SupplierPayment),
            creator=request.user,
            supplier=supplier,
            company=company,
            branch=branch,
            amount_paid=amt,
            payment_date=pay_date,
            payment_mode=pay_mode,
            bank_name=bank_name if pay_mode == 'CHEQUE' else '',
            cheque_number=cheque_no if pay_mode == 'CHEQUE' else '',
            cheque_date=cheque_date if pay_mode == 'CHEQUE' else None,
            remarks=request.POST.get('remarks', '')
        )

        # Deduct payment from pending invoices or payables
        pending_invoices = PurchaseInvoice.objects.filter(supplier=supplier, balance_to_pay__gt=0, is_deleted=False).order_by('invoice_date')
        remaining_payment = amt
        for inv in pending_invoices:
            if remaining_payment <= 0:
                break
            if inv.balance_to_pay <= remaining_payment:
                remaining_payment -= inv.balance_to_pay
                inv.amount_paid += inv.balance_to_pay
                inv.balance_to_pay = Decimal('0.00')
            else:
                inv.balance_to_pay -= remaining_payment
                inv.amount_paid += remaining_payment
                remaining_payment = Decimal('0.00')
            inv.save()

        update_supplier_payables(supplier)
        messages.success(request, f"Payment of ₹{amt} recorded for Supplier '{supplier.name}' successfully!")
        return redirect('supplier_payables_list')

    return render(request, 'supplier_payables/pay.html', {'supplier': supplier, 'title': f"Record Payment - {supplier.name}"})