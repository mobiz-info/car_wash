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
                    default_tmpl = 'wheelalignment'
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

            tmpl = (rem.get('template_name') or default_tmpl or 'servicesreminder').strip()
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

    # ── Smoke Test: create ReminderPlans from next_smoke_test_date ──────────────
    # These are independent of custom_reminders and ServiceReminder rules.
    # For each invoice item that is a smoke/pollution test, schedule reminder plans
    # at (next_smoke_test_date - r1_days) and (next_smoke_test_date - r2_days).
    for item in invoice.items.all():
        s_name = (item.service_name or (item.service.name if item.service else '')).lower()
        cat_slug = item.service.service_type.slug if (item.service and item.service.service_type) else ''
        is_smoke_item = 'smoke' in s_name or 'pollution' in s_name or 'smoke' in cat_slug

        if not is_smoke_item:
            continue

        # Resolve next_smoke_test_date from service_detail → vehicle
        next_smoke_date = None
        sd = getattr(item, 'service_detail', None)
        if sd and getattr(sd, 'next_smoke_test_date', None):
            next_smoke_date = sd.next_smoke_test_date
        elif invoice.vehicle and getattr(invoice.vehicle, 'next_smoke_test_date', None):
            next_smoke_date = invoice.vehicle.next_smoke_test_date

        if not next_smoke_date:
            continue

        # Resolve reminder windows from EmissionStandard → defaults (15, 3)
        r1_days, r2_days = 15, 3
        if (invoice.vehicle and
                getattr(invoice.vehicle, 'vehicle_type_model', None) and
                getattr(invoice.vehicle.vehicle_type_model, 'emission_standard', None)):
            es = invoice.vehicle.vehicle_type_model.emission_standard
            r1_days = getattr(es, 'reminder_1_days', 15)
            r2_days = getattr(es, 'reminder_2_days', 3)

        # Archive any older unsent smoke test reminder plans for this vehicle
        if invoice.vehicle:
            ReminderPlan.objects.filter(
                invoice__vehicle=invoice.vehicle,
                template_name='smoketest',
                is_sent=False,
                is_deleted=False
            ).exclude(invoice=invoice).update(is_deleted=True)

        reminder_stages = [
            (1, next_smoke_date - timedelta(days=r1_days)),
            (2, next_smoke_date - timedelta(days=r2_days)),
        ]
        for idx, scheduled_date in reminder_stages:
            # Skip if already exists
            if ReminderPlan.objects.filter(
                invoice=invoice,
                template_name='smoketest',
                reminder_no=idx,
                is_deleted=False
            ).exists():
                continue
            ReminderPlan.objects.create(
                branch=branch,
                invoice=invoice,
                reminder=None,
                template_name='smoketest',
                reminder_no=idx,
                scheduled_date=scheduled_date,
                auto_id=get_auto_id(ReminderPlan)
            )

    # If there were only smoke-test items and no custom reminders, we're done
    has_only_smoke = all(
        ('smoke' in (item.service_name or (item.service.name if item.service else '')).lower() or
         'pollution' in (item.service_name or (item.service.name if item.service else '')).lower())
        for item in invoice.items.all()
        if item.service or item.service_name
    ) and invoice.items.filter(service__isnull=False).exists()
    if has_only_smoke and not custom_reminders:
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
                    default_tmpl = 'wheelalignment'
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

            tmpl = (rem.get('template_name') or default_tmpl or 'servicesreminder').strip()
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
        # Skip smoke test items (already handled above)
        s_name_chk = item.service.name.lower() if item.service else ''
        if 'smoke' in s_name_chk or 'pollution' in s_name_chk:
            continue

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
                    template_name=rule.template_name or 'servicesreminder',
                    reminder_no=idx,
                    scheduled_date=scheduled_date,
                    auto_id=get_auto_id(ReminderPlan)
                )