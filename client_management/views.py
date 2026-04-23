from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from .models import Client
from .forms import ClientForm
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

