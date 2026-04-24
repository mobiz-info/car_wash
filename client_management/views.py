from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import JsonResponse
from .models import Client
from .forms import ClientForm
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
