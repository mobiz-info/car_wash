from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from datetime import datetime
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import *
from .forms import *
from core.functions import get_auto_id


@login_required
def booking_list(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    bookings = Booking.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).order_by('-booking_date', '-auto_id')

    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        bookings = bookings.filter(branch__company=user.profile.company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        bookings = bookings.filter(branch=user.managed_branch)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if from_date:
        bookings = bookings.filter(booking_date__gte=from_date)

    if to_date:
        bookings = bookings.filter(booking_date__lte=to_date)

    search = request.GET.get('search', '').strip()
    if search:
        bookings = bookings.filter(
            Q(customer__name__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search) |
            Q(customer__phone__icontains=search)
        )

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    return render(request, 'booking/list.html', {
        'bookings': bookings,
        'search': search,
        'status_filter': status_filter,
        'from_date': from_date,
        'to_date': to_date,
        'title': 'Bookings',
    })

    
    
@login_required
def holiday_calendar(request):

    search = request.GET.get('search', '')
    selected_date = request.GET.get('holiday_date', '')

    holidays = HolidayCalendar.objects.filter(
        is_deleted=False
    ).select_related(
        'branch'
    )

    if search:
        holidays = holidays.filter(
            branch__name__icontains=search
        )

    display_holidays = []

    if selected_date:

        selected_date_obj = datetime.strptime(
            selected_date,
            "%Y-%m-%d"
        ).date()

        holidays = holidays.filter(
            Q(
                holiday_date=selected_date_obj
            )
            |
            Q(
                repeat_yearly=True,
                holiday_date__month=selected_date_obj.month,
                holiday_date__day=selected_date_obj.day
            )
        )

        for holiday in holidays:

            if holiday.repeat_yearly:

                display_date = holiday.holiday_date.replace(
                    year=selected_date_obj.year
                )

            else:
                display_date = holiday.holiday_date

            holiday.display_date = display_date

            display_holidays.append(
                holiday
            )

    else:

        for holiday in holidays.order_by('-holiday_date'):

            holiday.display_date = holiday.holiday_date

            display_holidays.append(
                holiday
            )

    context = {
        'holidays': display_holidays,
        'search': search,
        'selected_date': selected_date,
    }

    return render(
        request,
        'booking/holiday_calendar.html',
        context
    )
    
    
@login_required
def holiday_create(request):

    if request.method == "POST":

        form = HolidayCalendarForm(
            request.POST,
            user=request.user
        )

        if form.is_valid():

            holiday = form.save(commit=False)

            holiday.creator = request.user
            holiday.auto_id = get_auto_id(HolidayCalendar)

            holiday.save()

            messages.success(
                request,
                "Holiday created successfully"
            )

            return redirect(
                "holiday_calendar"
            )

    else:

        form = HolidayCalendarForm(
            user=request.user
        )

    context = {
        "form": form,
    }

    return render(
        request,
        "booking/holiday_create.html",
        context
    )

@login_required
def holiday_delete(request, id):

    holiday = get_object_or_404(
        HolidayCalendar,
        id=id,
        is_deleted=False
    )

    holiday.is_deleted = True
    holiday.save()

    messages.success(
        request,
        "Holiday deleted successfully"
    )

    return redirect("holiday_calendar")
 
    
@login_required
def weekly_off_list(request):

    search = request.GET.get('search', '')

    weekly_offs = WeeklyOffDay.objects.filter(
        is_deleted=False
    ).select_related(
        'branch'
    )

    if search:
        weekly_offs = weekly_offs.filter(
            branch__name__icontains=search
        )

    context = {
        'weekly_offs': weekly_offs.order_by(
            'branch__name',
            'day'
        ),
        'search': search,
    }

    return render(
        request,
        'booking/weekly_off.html',
        context
    )


@login_required
def weekly_off_create(request):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

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

        branches = Branch.objects.filter(
            id=branch.id,
            is_deleted=False
        ) if branch else Branch.objects.none()

    if request.method == "POST":

        branch_id = request.POST.get("branch")
        day = request.POST.get("day")

        if not branches.filter(id=branch_id).exists():

            messages.error(
                request,
                "Invalid branch selected."
            )

            return redirect("weekly_off_create")

        weekly_off = WeeklyOffDay.objects.filter(
            branch_id=branch_id,
            day=day
        ).first()

        if weekly_off:

            if weekly_off.is_deleted:

                weekly_off.is_deleted = False
                weekly_off.creator = request.user
                weekly_off.save()

                messages.success(
                    request,
                    "Weekly Off Day restored successfully."
                )

            else:

                messages.error(
                    request,
                    "This day is already added for the selected branch."
                )

        else:

            WeeklyOffDay.objects.create(
                branch_id=branch_id,
                day=day,
                creator=request.user,
                auto_id=get_auto_id(WeeklyOffDay)
            )

            messages.success(
                request,
                "Weekly Off Day created successfully."
            )

        return redirect("weekly_off_list")

    context = {
        "branches": branches,
        "days": WeeklyOffDay.DAYS,
    }

    return render(
        request,
        "booking/weekly_off_create.html",
        context
    )
    
     
@login_required
def weekly_off_delete(request, id):

    weekly_off = get_object_or_404(
        WeeklyOffDay,
        id=id,
        is_deleted=False
    )

    weekly_off.is_deleted = True
    weekly_off.save()

    messages.success(
        request,
        "Weekly Off Day deleted successfully."
    )

    return redirect(
        "weekly_off_list"
    )
    
    
@login_required
def booking_settings(request):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

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

        branches = Branch.objects.filter(
            id=branch.id,
            is_deleted=False
        ) if branch else Branch.objects.none()

    if request.method == "POST":

        for branch in branches:

            booking_enabled = (
                request.POST.get(
                    f"is_booking_enabled_{branch.id}"
                ) == "on"
            )

            max_booking = (
                request.POST.get(
                    f"max_booking_{branch.id}"
                ) or 0
            )

            closing_time = request.POST.get(
                f"closing_time_{branch.id}"
            )

            BookingSettings.objects.update_or_create(
                branch=branch,
                defaults={
                    "is_booking_enabled": booking_enabled,
                    "max_booking_per_day": max_booking,
                    "booking_closing_time": (
                        closing_time if closing_time else None
                    ),
                    "creator": request.user,
                }
            )

        messages.success(
            request,
            "Booking settings updated successfully"
        )

        return HttpResponseRedirect(
            reverse('booking_settings')
        )

    for branch in branches:

        BookingSettings.objects.get_or_create(
            branch=branch,
            defaults={
                "creator": request.user,
                "auto_id": get_auto_id(BookingSettings),
            }
        )

    booking_settings = {
        item.branch_id: item
        for item in BookingSettings.objects.filter(
            branch__in=branches,
            is_deleted=False
        )
    }

    context = {
        "branches": branches,
        "booking_settings": booking_settings,
    }

    return render(
        request,
        "booking/booking_settings.html",
        context
    )
    
@login_required
def pause_booking_create(request):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

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

        branches = Branch.objects.filter(
            id=branch.id,
            is_deleted=False
        ) if branch else Branch.objects.none()

    if request.method == "POST":

        branch_id = request.POST.get("branch")
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")
        reason = request.POST.get("reason")

        if not branches.filter(id=branch_id).exists():

            messages.error(
                request,
                "Invalid branch selected."
            )

            return redirect(
                "pause_booking_create"
            )

        BookingPause.objects.create(
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            reason=reason,
            creator=request.user,
            auto_id=get_auto_id(BookingPause)
        )

        messages.success(
            request,
            "Booking pause created successfully."
        )

        return redirect(
            "pause_booking_list"
        )

    context = {
        "branches": branches
    }

    return render(
        request,
        "booking/pause_booking_create.html",
        context
    )
    
@login_required
def pause_booking_list(request):

    role = getattr(
        getattr(request.user, 'profile', None),
        'role',
        None
    )

    role_name = role.name if role else None

    if role_name == 'COMPANY_ADMIN':

        company = request.user.profile.company

        pauses = BookingPause.objects.filter(
            branch__company=company,
            is_deleted=False
        ).select_related(
            'branch'
        )

    else:

        branch = getattr(
            request.user,
            'managed_branch',
            None
        )

        pauses = BookingPause.objects.filter(
            branch=branch,
            is_deleted=False
        ).select_related(
            'branch'
        )

    context = {
        "pauses": pauses
    }

    return render(
        request,
        "booking/pause_booking_list.html",
        context
    )
    
@login_required
def pause_booking_delete(request, pk):

    item = get_object_or_404(
        BookingPause,
        pk=pk,
        is_deleted=False
    )

    item.is_deleted = True
    item.save()

    messages.success(
        request,
        "Booking pause deleted successfully."
    )

    return redirect(
        "pause_booking_list"
    )


@login_required
def branch_messages_manage(request):
    """View and edit per-branch WhatsApp message templates (Welcome, Ready Alert, Thank You)."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    from client_management.models import Branch

    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        branches = Branch.objects.filter(company=company, is_deleted=False).order_by('name')
    else:
        managed = getattr(request.user, 'managed_branch', None)
        branches = Branch.objects.filter(id=managed.id, is_deleted=False) if managed else Branch.objects.none()

    # Select active branch (from GET ?branch_id= or first branch)
    selected_branch_id = request.GET.get('branch_id') or request.POST.get('branch_id')
    selected_branch = None
    if selected_branch_id:
        selected_branch = branches.filter(id=selected_branch_id).first()
    if not selected_branch:
        selected_branch = branches.first()

    branch_settings = None
    if selected_branch:
        branch_settings, _ = BookingSettings.objects.get_or_create(
            branch=selected_branch,
            defaults={'creator': request.user, 'auto_id': get_auto_id(BookingSettings)}
        )

    if request.method == 'POST' and selected_branch:
        branch_settings.whatsapp_welcome_message = request.POST.get('welcome_message', '').strip() or None
        branch_settings.whatsapp_ready_message = request.POST.get('ready_message', '').strip() or None
        branch_settings.whatsapp_thanks_message = request.POST.get('thanks_message', '').strip() or None
        branch_settings.updater = request.user
        branch_settings.save()
        messages.success(request, f'Messages updated for {selected_branch.name}.')
        return HttpResponseRedirect(
            reverse('branch_messages_manage') + (f'?branch_id={selected_branch.id}' if selected_branch else '')
        )

    context = {
        'branches': branches,
        'selected_branch': selected_branch,
        'branch_settings': branch_settings,
        'role_name': role_name,
        'default_welcome': 'Hello {customer_name}, thank you for choosing {company_name}. Welcome to our service! We are delighted to have you and your vehicle ({vehicle_number}) with us.',
        'default_ready': 'Hello {customer_name}, your vehicle ({vehicle_number}) is ready for pickup! Thank you for choosing our service.',
        'default_thanks': 'Hello {customer_name}, thank you for choosing our service! We look forward to serving you again. Have a great day!',
    }
    return render(request, 'booking/branch_messages.html', context)


@login_required
def service_reminders_manage(request):
    """View and edit per-branch service top-up reminders."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    from client_management.models import Branch
    from service_management.models import Service

    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        branches = Branch.objects.filter(company=company, is_deleted=False).order_by('name')
    else:
        managed = getattr(request.user, 'managed_branch', None)
        branches = Branch.objects.filter(id=managed.id, is_deleted=False) if managed else Branch.objects.none()

    # Select active branch (from GET ?branch_id= or first branch)
    selected_branch_id = request.GET.get('branch_id') or request.POST.get('branch_id')
    selected_branch = None
    if selected_branch_id:
        selected_branch = branches.filter(id=selected_branch_id).first()
    if not selected_branch:
        selected_branch = branches.first()

    # Fetch services
    services = Service.objects.filter(is_active=True).order_by('name')

    # Fetch existing reminders for this branch
    reminders = []
    if selected_branch:
        reminders = ServiceReminder.objects.filter(
            branch=selected_branch, is_deleted=False
        ).select_related('service').order_by('days_after')

    if request.method == 'POST' and selected_branch:
        service_id = request.POST.get('service_id')
        reminder_message = request.POST.get('reminder_message', '').strip()
        days_after = request.POST.get('days_after', '').strip()

        # Validation
        if not service_id or not reminder_message or not days_after:
            messages.error(request, 'All fields are mandatory to add a reminder.')
        else:
            try:
                days = int(days_after)
                if days <= 0:
                    raise ValueError()
                
                service_obj = Service.objects.get(id=service_id)
                
                # Create the reminder configuration
                ServiceReminder.objects.create(
                    branch=selected_branch,
                    service=service_obj,
                    reminder_message=reminder_message,
                    days_after=days,
                    creator=request.user,
                    auto_id=get_auto_id(ServiceReminder)
                )
                messages.success(request, f'Service reminder added for {service_obj.name}.')
                return HttpResponseRedirect(
                    reverse('service_reminders_manage') + f'?branch_id={selected_branch.id}'
                )
            except ValueError:
                messages.error(request, 'Please enter a valid positive number for days.')
            except Service.DoesNotExist:
                messages.error(request, 'Selected service does not exist.')

    context = {
        'branches': branches,
        'selected_branch': selected_branch,
        'services': services,
        'reminders': reminders,
        'role_name': role_name,
    }
    return render(request, 'booking/service_reminders.html', context)


@login_required
def service_reminder_delete(request, id):
    """Delete a service reminder configuration."""
    reminder = get_object_or_404(ServiceReminder, id=id, is_deleted=False)
    
    # Check permissions
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None
    
    if role_name != 'COMPANY_ADMIN':
        managed = getattr(request.user, 'managed_branch', None)
        if not managed or managed.id != reminder.branch.id:
            messages.error(request, 'You do not have permission to delete this reminder.')
            return redirect('service_reminders_manage')
            
    reminder.is_deleted = True
    reminder.save()
    messages.success(request, 'Service reminder configuration deleted successfully.')
    return HttpResponseRedirect(
        reverse('service_reminders_manage') + f'?branch_id={reminder.branch.id}'
    )


@login_required
def reminder_planner(request):
    """View to list all future scheduled reminder plans and manage them (edit/delete)."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    from client_management.models import Branch
    from booking_management.models import ReminderPlan
    from django.contrib import messages

    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        branches = Branch.objects.filter(company=company, is_deleted=False).order_by('name')
    else:
        managed = getattr(request.user, 'managed_branch', None)
        branches = Branch.objects.filter(id=managed.id, is_deleted=False) if managed else Branch.objects.none()

    # Active branch
    selected_branch_id = request.GET.get('branch_id') or request.POST.get('branch_id')
    selected_branch = None
    if selected_branch_id:
        selected_branch = branches.filter(id=selected_branch_id).first()
    if not selected_branch:
        selected_branch = branches.first()

    # Handle Edit / Delete actions
    if request.method == 'POST' and selected_branch:
        action = request.POST.get('action')
        plan_id = request.POST.get('plan_id')
        
        if action == 'delete' and plan_id:
            plan = get_object_or_404(ReminderPlan, id=plan_id, branch=selected_branch)
            plan.is_deleted = True
            plan.save()
            messages.success(request, 'Scheduled reminder plan deleted successfully.')
            return HttpResponseRedirect(request.path + f'?branch_id={selected_branch.id}')
            
        elif action == 'edit' and plan_id:
            scheduled_date_str = request.POST.get('scheduled_date')
            if scheduled_date_str:
                try:
                    from datetime import datetime
                    new_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
                    plan = get_object_or_404(ReminderPlan, id=plan_id, branch=selected_branch)
                    plan.scheduled_date = new_date
                    plan.save()
                    messages.success(request, 'Reminder scheduled date updated successfully.')
                except ValueError:
                    messages.error(request, 'Invalid date format.')
            return HttpResponseRedirect(request.path + f'?branch_id={selected_branch.id}')

    plans = []
    if selected_branch:
        plans = ReminderPlan.objects.filter(
            branch=selected_branch,
            is_sent=False,
            is_deleted=False
        ).select_related('invoice', 'invoice__customer', 'invoice__vehicle', 'reminder', 'reminder__service').order_by('scheduled_date')

    context = {
        'branches': branches,
        'selected_branch': selected_branch,
        'plans': plans,
        'role_name': role_name,
    }
    return render(request, 'booking/reminder_planner.html', context)


@login_required
def reminder_list(request):
    """View to list currently due reminders and trigger sends."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    role_name = role.name if role else None

    from client_management.models import Branch
    from booking_management.models import ReminderPlan
    from django.utils import timezone
    from datetime import datetime

    if role_name == 'COMPANY_ADMIN':
        company = getattr(request.user.profile, 'company', None)
        branches = Branch.objects.filter(company=company, is_deleted=False).order_by('name')
    else:
        managed = getattr(request.user, 'managed_branch', None)
        branches = Branch.objects.filter(id=managed.id, is_deleted=False) if managed else Branch.objects.none()

    # Active branch
    selected_branch_id = request.GET.get('branch_id') or request.POST.get('branch_id')
    selected_branch = None
    if selected_branch_id:
        selected_branch = branches.filter(id=selected_branch_id).first()
    if not selected_branch:
        selected_branch = branches.first()

    # Selected date
    date_str = request.GET.get('date')
    selected_date = timezone.now().date()
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    plans = []
    if selected_branch:
        # Fetch reminders that are scheduled on or before selected_date
        plans = ReminderPlan.objects.filter(
            branch=selected_branch,
            is_sent=False,
            is_deleted=False,
            scheduled_date__lte=selected_date
        ).select_related('invoice', 'invoice__customer', 'invoice__vehicle', 'reminder', 'reminder__service').order_by('scheduled_date')

    context = {
        'branches': branches,
        'selected_branch': selected_branch,
        'selected_date': selected_date.strftime("%Y-%m-%d"),
        'plans': plans,
        'role_name': role_name,
    }
    return render(request, 'booking/reminder_list.html', context)


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
@login_required
def send_reminder_ajax(request):
    """AJAX endpoint to trigger reminder sending for a list of ReminderPlan IDs."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    try:
        import json
        data = json.loads(request.body)
        plan_ids = data.get('plan_ids', [])
        action = data.get('action')
        
        from booking_management.models import ReminderPlan, SentServiceReminder
        from client_management.models import WhatsAppSetting
        from booking_management.api_views import send_whatsapp_simple, send_whatsapp_template
        import re
        import urllib.parse
        
        # Action: Mark Sent (used after manual fallback)
        if action == 'mark_sent':
            for p_id in plan_ids:
                try:
                    plan = ReminderPlan.objects.get(id=p_id, is_deleted=False, is_sent=False)
                    plan.is_sent = True
                    plan.save()
                    SentServiceReminder.objects.get_or_create(
                        reminder=plan.reminder,
                        invoice=plan.invoice
                    )
                except ReminderPlan.DoesNotExist:
                    pass
            return JsonResponse({'success': True, 'message': 'Marked as sent'})
            
        sent_count = 0
        
        for p_id in plan_ids:
            try:
                plan = ReminderPlan.objects.get(id=p_id, is_deleted=False, is_sent=False)
            except ReminderPlan.DoesNotExist:
                continue
                
            reminder = plan.reminder
            invoice = plan.invoice
            
            # Fetch setting
            company = plan.branch.company if plan.branch else None
            setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
            
            # Prepare phone number & fallback link
            phone = invoice.customer.phone or invoice.customer.whatsapp_number
            cleaned_phone = ""
            if phone:
                cleaned_phone = re.sub(r'\D', '', str(phone))
                if cleaned_phone.startswith('0'):
                    cleaned_phone = cleaned_phone[1:]
                    
            customer_name = invoice.customer.name or "Customer"
            vehicle_no = invoice.vehicle.vehicle_number if invoice.vehicle else "your vehicle"
            
            # Prefilled message (Template text fallback)
            message = reminder.reminder_message.replace('{customer_name}', customer_name) \
                                                .replace('{vehicle_number}', vehicle_no) \
                                                .replace('{service_name}', reminder.service.name)
            
            encoded_message = urllib.parse.quote(message)
            fallback_url = f"https://api.whatsapp.com/send?phone={cleaned_phone}&text={encoded_message}"
            
            # Check if API is available
            if not setting or not setting.username or not setting.password:
                if len(plan_ids) == 1:
                    # Return fallback prefill link directly
                    return JsonResponse({
                        'success': False,
                        'use_fallback': True,
                        'whatsapp_url': fallback_url,
                        'plan_id': plan.id,
                        'message': 'WhatsApp API not configured. Use manual sending.'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'WhatsApp API is not configured. Send individually to use manual prefill.'
                    })
            
            # Send via API
            try:
                send_whatsapp_simple(
                    to_number=cleaned_phone,
                    message=message,
                    setting=setting
                )
            except Exception as api_err:
                # If single send fails, try manual fallback
                if len(plan_ids) == 1:
                    return JsonResponse({
                        'success': False,
                        'use_fallback': True,
                        'whatsapp_url': fallback_url,
                        'plan_id': plan.id,
                        'message': f'API Error: {str(api_err)}. Switch to manual fallback.'
                    })
                else:
                    continue
                
            # Mark sent
            plan.is_sent = True
            plan.save()
            
            # Log sent reminder for reports/compatibility
            SentServiceReminder.objects.get_or_create(
                reminder=reminder,
                invoice=invoice
            )
            sent_count += 1
            
        return JsonResponse({'success': True, 'sent_count': sent_count})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)