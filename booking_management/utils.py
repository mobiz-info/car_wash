from .models import (
    Booking,
    BookingSettings,
    HolidayCalendar,
    WeeklyOffDay,
    BookingPause
)

def validate_booking(branch, booking_date):
    setting = BookingSettings.objects.filter(
        branch=branch,
        is_deleted=False
    ).first()

    if setting and not setting.is_booking_enabled:
        return False, "Booking disabled for this branch"

    holiday_exists = HolidayCalendar.objects.filter(
        branch=branch,
        holiday_date=booking_date,
        is_deleted=False
    ).exists()

    if holiday_exists:
        return False, "Selected date is a holiday"

    weekday = booking_date.strftime("%A").lower()

    weekly_off = WeeklyOffDay.objects.filter(
        branch=branch,
        day=weekday,
        is_deleted=False
    ).exists()

    if weekly_off:
        return False, "Selected date is weekly off"

    pause_exists = BookingPause.objects.filter(
        branch=branch,
        from_date__lte=booking_date,
        to_date__gte=booking_date,
        is_deleted=False
    ).exists()

    if pause_exists:
        return False, "Booking paused for selected date"

    if setting:
        count = Booking.objects.filter(
            branch=branch,
            booking_date=booking_date,
            is_deleted=False
        ).count()

        if count >= setting.max_booking_per_day:
            return False, "Maximum booking limit reached"

    return True, "Booking available"