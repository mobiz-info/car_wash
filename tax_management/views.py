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
    
@login_required
def company_tax_enable(request):
    user = request.user
    if not hasattr(user, 'profile') or user.profile.role.name != 'COMPANY_ADMIN' or not user.profile.company:
        messages.error(request, "Access denied. Only Company Admin can manage taxes.")
        return redirect('dashboard')

    company = user.profile.company
    country = company.country
    
    if not country:
        messages.error(request, "Your company does not have a country assigned. Please update company details.")
        return redirect('dashboard')

    # Get all taxes available in the company's country
    available_taxes = Tax.objects.filter(country=country, is_deleted=False).order_by('name')

    from .models import CompanyTax

    if request.method == 'POST':
        enabled_tax_ids = request.POST.getlist('taxes')
        
        from core.functions import get_auto_id
        for tax in available_taxes:
            company_tax = CompanyTax.objects.filter(company=company, tax=tax).first()
            if not company_tax:
                company_tax = CompanyTax(
                    company=company, 
                    tax=tax,
                    auto_id=get_auto_id(CompanyTax),
                    creator=request.user
                )
                
            if str(tax.id) in enabled_tax_ids:
                company_tax.is_enabled = True
            else:
                company_tax.is_enabled = False
            
            # update updater if it already existed
            if company_tax.id:
                company_tax.updater = request.user
                
            company_tax.save()
            
        username = request.user.username
        log_activity(
            created_by=request.user,
            description=f"{username} updated company tax settings."
        )
        
        messages.success(request, 'Tax settings updated successfully.')
        return redirect('company_tax_enable')

    # Get enabled tax IDs
    enabled_tax_ids = CompanyTax.objects.filter(company=company, is_enabled=True).values_list('tax_id', flat=True)
    enabled_tax_ids_str = [str(tid) for tid in enabled_tax_ids]

    return render(request, 'company_tax_enable.html', {
        'title': 'Tax Enable',
        'available_taxes': available_taxes,
        'enabled_tax_ids': enabled_tax_ids_str,
    })