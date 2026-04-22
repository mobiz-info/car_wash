from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator

from .functions import *
from .models import *
from .forms import *

class DashboardView(TemplateView):
    template_name = 'dashboard.html'


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


def country_create(request):
    form = CountryForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Country)
            # instance.creator = request.user

            instance.save()

            messages.success(request, "Country created successfully")
            return redirect('country_list')

    return render(request, 'country/create.html', {
        'form': form,
        'title': 'Create Country'
    })


def country_edit(request, id):
    instance = get_object_or_404(Country, id=id, is_deleted=False)
    form = CountryForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Country)
            # instance.creator = request.user

            instance.save()
            
            messages.success(request, "Country updated successfully")
            return redirect('country_list')

    return render(request, 'country/create.html', {
        'form': form,
        'title': 'Edit Country'
    })


def country_delete(request, id):
    instance = get_object_or_404(Country, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "Country deleted successfully")
    return redirect('country_list')



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


def state_create(request):
    form = StateForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(State)
            # instance.creator = request.user

            instance.save()

            messages.success(request, "State created successfully")
            return redirect('state_list')

    return render(request, 'state/create.html', {
        'form': form,
        'title': 'Create State'
    })


def state_edit(request, id):
    instance = get_object_or_404(State, id=id, is_deleted=False)
    form = StateForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            # instance.auto_id = get_auto_id(State)
            # instance.creator = request.user

            instance.save()
            
            messages.success(request, "State updated successfully")
            return redirect('state_list')

    return render(request, 'state/create.html', {
        'form': form,
        'title': 'Edit State'
    })


def state_delete(request, id):
    instance = get_object_or_404(State, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "State deleted successfully")
    return redirect('state_list')



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


def district_create(request):
    form = DistrictForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(District)
            # instance.creator = request.user

            instance.save()

            messages.success(request, "District created successfully")
            return redirect('district_list')

    return render(request, 'district/create.html', {
        'form': form,
        'title': 'Create District'
    })


def district_edit(request, id):
    instance = get_object_or_404(District, id=id, is_deleted=False)
    form = DistrictForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(District)
            # instance.creator = request.user

            instance.save()
            
            messages.success(request, "District updated successfully")
            return redirect('district_list')

    return render(request, 'district/create.html', {
        'form': form,
        'title': 'Edit District'
    })


def district_delete(request, id):
    instance = get_object_or_404(District, id=id)
    instance.is_deleted = True
    instance.save()
    messages.success(request, "District deleted successfully")
    return redirect('district_list')