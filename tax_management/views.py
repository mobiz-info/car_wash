from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from core.functions import get_auto_id, log_activity
from .forms import TaxForm
from .models import Tax

# Create your views here.
@login_required
def tax_list(request):
    queryset = Tax.objects.filter(is_deleted=False).order_by('-id')

    search = request.GET.get('search')  
    if search:
        queryset = queryset.filter(name__icontains=search)
    
    # LOG
    username = request.user.username
    log_activity(
        created_by=request.user,
        description=f"{username} viewed tax list."
    )
    
    return render(request, 'tax_list.html', {
        'title': 'Tax List',
        'taxes': queryset,
        'search': search, 
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
            
            # LOG
            username = request.user.username
            log_activity(
                created_by=request.user,
                description=f"{username} created tax '{instance.name}' ({instance.percent}%)."
            )
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

            instance.updater = request.user

            instance.save()
            
            # LOG
            username = request.user.username
            log_activity(
                created_by=request.user,
                description=f"{username} updated tax '{instance.name}' to {instance.percent}%."
            )
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

    # LOG
    tax_name = instance.name
    username = request.user.username
    log_activity(
        created_by=request.user,
        description=f"{username} deleted tax '{tax_name}'."
    )


    messages.success(request, "Tax deleted successfully")
    return redirect('tax_list')
    