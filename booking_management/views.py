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