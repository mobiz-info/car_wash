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


def create_reminder_plans_for_invoice(invoice, custom_reminders=None):
    """Create scheduled ReminderPlan entries for an invoice.
    Supports both custom per-customer reminder schedules and default branch rules.
    """
    from booking_management.models import ServiceReminder, ReminderPlan
    from datetime import timedelta
    from core.functions import get_auto_id
    
    branch = invoice.branch
    if not branch:
        return

    # Handle custom per-customer reminder schedule if provided
    if custom_reminders and isinstance(custom_reminders, list) and len(custom_reminders) > 0:
        default_tmpl = None
        for item in invoice.items.all():
            if item.service:
                sr = ServiceReminder.objects.filter(branch=branch, service=item.service, is_deleted=False).first()
                if sr and sr.template_name:
                    default_tmpl = sr.template_name
                    break
                if not default_tmpl and item.service.service_type:
                    sr = ServiceReminder.objects.filter(branch=branch, service__service_type=item.service.service_type, is_deleted=False).first()
                    if sr and sr.template_name:
                        default_tmpl = sr.template_name
                        break
            s_name = (item.service_name or (item.service.name if item.service else '')).lower()
            cat_slug = item.service.service_type.slug if (item.service and item.service.service_type) else ''
            if not default_tmpl:
                if 'wheel' in s_name or 'balance' in s_name or 'alignment' in s_name or 'wheel' in cat_slug or 'alignment' in cat_slug:
                    default_tmpl = 'wheelbalancing'
                elif 'smoke' in s_name or 'pollution' in s_name or 'smoke' in cat_slug:
                    default_tmpl = 'smoketest'
                elif 'battery' in s_name or 'battery' in cat_slug:
                    default_tmpl = 'batteryservice'
                elif 'oil' in s_name or 'oil' in cat_slug:
                    default_tmpl = 'oilreminder'

        for idx, rem in enumerate(custom_reminders, start=1):
            days = 0
            try:
                days = int(rem.get('days_after') or rem.get('days') or 0)
            except (ValueError, TypeError):
                days = 0
            if days <= 0:
                continue

            tmpl = (rem.get('template_name') or default_tmpl or 'servicereminder').strip()
            scheduled_date = invoice.date + timedelta(days=days)

            ReminderPlan.objects.create(
                branch=branch,
                invoice=invoice,
                reminder=None,
                template_name=tmpl,
                reminder_no=idx,
                scheduled_date=scheduled_date,
                auto_id=get_auto_id(ReminderPlan)
            )
        return

    # Fallback to default branch ServiceReminder rules
    for item in invoice.items.filter(service__isnull=False):
        # Auto-archive older unsent ReminderPlans for the SAME vehicle and SAME service
        if invoice.vehicle:
            ReminderPlan.objects.filter(
                invoice__vehicle=invoice.vehicle,
                reminder__service=item.service,
                is_sent=False,
                is_deleted=False
            ).exclude(invoice=invoice).update(is_deleted=True)

        reminder_rules = ServiceReminder.objects.filter(
            branch=branch,
            service=item.service,
            is_deleted=False
        ).order_by('days_after')
        
        if not reminder_rules.exists() and item.service and item.service.service_type:
            reminder_rules = ServiceReminder.objects.filter(
                branch=branch,
                service__service_type=item.service.service_type,
                is_deleted=False
            ).order_by('days_after')
        
        for idx, rule in enumerate(reminder_rules, start=1):
            scheduled_date = invoice.date + timedelta(days=rule.days_after)
            
            exists = ReminderPlan.objects.filter(
                invoice=invoice,
                reminder=rule,
                is_deleted=False
            ).exists()
            
            if not exists:
                ReminderPlan.objects.create(
                    branch=branch,
                    invoice=invoice,
                    reminder=rule,
                    template_name=rule.template_name or 'servicereminder',
                    reminder_no=idx,
                    scheduled_date=scheduled_date,
                    auto_id=get_auto_id(ReminderPlan)
                )