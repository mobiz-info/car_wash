from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

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
    data = VehicleType.objects.filter(is_deleted=False)
    return render(request, 'vehicle_type/list.html', {'data': data})

@login_required
def vehicle_type_create(request):
    form = VehicleTypeForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleType)
            instance.save()
            messages.success(request, "Vehicle Type created successfully")
            return redirect('vehicle_type_list')

    return render(request, 'vehicle_type/create.html', {
        'form': form,
        'title': 'Create Vehicle Type'
    })
    
    
@login_required
def vehicle_type_edit(request, id):
    instance = get_object_or_404(VehicleType, id=id, is_deleted=False)

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
    instance = get_object_or_404(VehicleType, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Vehicle Type deleted successfully")
    return redirect('vehicle_type_list')


@login_required
def vehicle_type_model_list(request):
    data = VehicleTypeModel.objects.filter(is_deleted=False)
    return render(request, 'vehicle_type_model/list.html', {'data': data})


@login_required
def vehicle_type_model_create(request):
    form = VehicleTypeModelForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(VehicleTypeModel)
            instance.save()
            messages.success(request, "Vehicle Model created successfully")
            return redirect('vehicle_type_model_list')

    return render(request, 'vehicle_type_model/create.html', {
        'form': form,
        'title': 'Create Vehicle Model'
    })


@login_required
def vehicle_type_model_edit(request, id):
    instance = get_object_or_404(VehicleTypeModel, id=id, is_deleted=False)

    form = VehicleTypeModelForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Vehicle Model updated successfully")
            return redirect('vehicle_type_model_list')

    return render(request, 'vehicle_type_model/create.html', {
        'form': form,
        'title': 'Edit Vehicle Model'
    })


@login_required
def vehicle_type_model_delete(request, id):
    instance = get_object_or_404(VehicleTypeModel, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Vehicle Model deleted successfully")
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
    search = request.GET.get('search', '')
    queryset = ExpenseHead.objects.filter(is_deleted=False)
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'expense_head/list.html', {'page_obj': page_obj, 'search': search})


@login_required
def expense_head_create(request):
    form = ExpenseHeadForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.auto_id = get_auto_id(ExpenseHead)
            instance.creator = request.user
            instance.save()
            messages.success(request, "Expense Head created successfully")
            return redirect('expense_head_list')
    return render(request, 'expense_head/create.html', {'form': form, 'title': 'Create Expense Head'})


@login_required
def expense_head_edit(request, id):
    instance = get_object_or_404(ExpenseHead, id=id, is_deleted=False)
    form = ExpenseHeadForm(request.POST or None, instance=instance)
    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updater = request.user
            instance.save()
            messages.success(request, "Expense Head updated successfully")
            return redirect('expense_head_list')
    return render(request, 'expense_head/create.html', {'form': form, 'title': 'Edit Expense Head'})


@login_required
def expense_head_delete(request, id):
    instance = get_object_or_404(ExpenseHead, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Expense Head deleted successfully")
    return redirect('expense_head_list')


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

    expense_heads = ExpenseHead.objects.filter(
        is_deleted=False
    )

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
            expense_date=expense_date,
            remarks=remarks
        )

        messages.success(request, "Expense Created Successfully")
        return redirect('expense_list')

    context = {
        'expense_heads': expense_heads,
        'expenses': expenses,
        'branches': branches,
        'role_name': role_name,
        'title': 'Expense Create'
    }

    return render(request, 'expense/create.html', context)


@login_required
def expense_edit(request, pk):

    expense_entry = get_object_or_404(
        ExpenseEntry,
        pk=pk,
        is_deleted=False
    )

    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    expense_heads = ExpenseHead.objects.filter(
        is_deleted=False
    )

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

    context = {
        'expense_entry': expense_entry,
        'expense_heads': expense_heads,
        'branches': branches,
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

    expense = get_object_or_404(
        ExpenseEntry,
        pk=pk,
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