from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from core.functions import get_auto_id
from .forms import TaxForm
from .models import Tax

# Create your views here.
@login_required
def tax_list(request):
    queryset = Tax.objects.filter(is_deleted=False).order_by('-id')

    search = request.GET.get('q')
    if search:
        queryset = queryset.filter(name__icontains=search)

    return render(request, 'tax_list.html', {
        'title': 'Tax List',
        'taxes': queryset
    })
    
@login_required    
def tax_create(request):
    form = TaxForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Tax)
            instance.creator = request.user

            instance.save()

            messages.success(request, "Tax created successfully")
            return redirect('tax_list')

    return render(request, 'tax_create.html', {
        'form': form,
        'title': 'Create Tax'
    })
    
@login_required    
def tax_edit(request, id):
    instance = get_object_or_404(Tax, id=id, is_deleted=False)
    form = TaxForm(request.POST or None, instance=instance)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)   

            instance.auto_id = get_auto_id(Tax)
            instance.updater = request.user

            instance.save()
            
            messages.success(request, "Tax updated successfully")
            return redirect('tax_list')

    return render(request, 'tax_create.html', {
        'form': form,
        'title': 'Edit Tax'
    })


@login_required    
def tax_delete(request, id):
    instance = get_object_or_404(Tax, id=id, is_deleted=False)
    instance.is_deleted = True
    instance.save()

    messages.success(request, "Tax deleted successfully")
    return redirect('tax_list')
    