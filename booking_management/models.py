from django.db import models
from django.utils import timezone
from core.models import BaseModel
from client_management.models import Customer, CustomerVehicle, Branch


class Booking(BaseModel):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bookings')
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE, related_name='bookings')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey('service_management.Service', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    service_name = models.CharField(max_length=150, blank=True, null=True)

    booking_number = models.CharField(max_length=20, unique=True, null=True, blank=True, help_text="Human-readable booking ID e.g. BK1, BK2")
    booking_date = models.DateField()
    booking_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"{self.customer.name} - {self.vehicle.vehicle_number} on {self.booking_date}"

    
class BookingSettings(BaseModel):
    branch = models.OneToOneField(
        Branch,
        on_delete=models.CASCADE,
        related_name="booking_settings"
    )

    is_booking_enabled = models.BooleanField(default=True)
    max_booking_per_day = models.PositiveIntegerField(default=50)

    booking_closing_time = models.TimeField(
        null=True,
        blank=True,
        help_text="No bookings allowed after this time"
    )

    whatsapp_welcome_message = models.TextField(
        null=True,
        blank=True,
        help_text="Custom welcome message. Use {customer_name}, {vehicle_number}, {branch_name}, {company_name} as placeholders."
    )

    whatsapp_ready_message = models.TextField(
        null=True,
        blank=True,
        help_text="Ready alert message. Use {customer_name}, {vehicle_number}, {branch_name}, {company_name} as placeholders."
    )

    whatsapp_thanks_message = models.TextField(
        null=True,
        blank=True,
        help_text="Thank you message. Use {customer_name}, {vehicle_number}, {branch_name}, {company_name} as placeholders."
    )

    def __str__(self):
        return f"{self.branch.name}"
    
class HolidayCalendar(BaseModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="holidays"
    )

    holiday_date = models.DateField()
    repeat_yearly = models.BooleanField(default=False)

    class Meta:
        unique_together = ('branch', 'holiday_date')

    def __str__(self):
        return str(self.holiday_date)
    
    
class WeeklyOffDay(BaseModel):
    DAYS = (
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='weekly_offs'
    )

    day = models.CharField(max_length=20, choices=DAYS)


    def __str__(self):
        return self.day
    
    
class BookingPause(BaseModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='booking_pauses'
    )

    from_date = models.DateField()
    to_date = models.DateField()

    reason = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.from_date} - {self.to_date}"


class ChatSession(BaseModel):
    phone_number = models.CharField(max_length=30, unique=True)
    state = models.CharField(max_length=50)
    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.phone_number} - {self.state}"


class ServiceReminder(BaseModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='service_reminders')
    service = models.ForeignKey('service_management.Service', on_delete=models.CASCADE, related_name='reminders')
    reminder_message = models.TextField(help_text="Template for the reminder. Use placeholders: {customer_name}, {vehicle_number}, {service_name}")
    days_after = models.PositiveIntegerField(help_text="Number of days after service to send this reminder")
    template_name = models.CharField(max_length=100, blank=True, null=True, help_text="Official Wawy/WhatsApp template name (e.g. batteryservice, servicereminder)")

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(ServiceReminder)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service.name} Reminder - {self.days_after} Days"


class SentServiceReminder(BaseModel):
    reminder = models.ForeignKey(ServiceReminder, on_delete=models.CASCADE, related_name='sent_instances')
    invoice = models.ForeignKey('finance_management.Invoice', on_delete=models.CASCADE, related_name='sent_reminders')
    sent_date = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(SentServiceReminder)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sent to {self.invoice.customer.name} on {self.sent_date}"


class ReminderPlan(BaseModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='reminder_plans')
    invoice = models.ForeignKey('finance_management.Invoice', on_delete=models.CASCADE, related_name='reminder_plans')
    reminder = models.ForeignKey(ServiceReminder, on_delete=models.SET_NULL, null=True, blank=True, related_name='reminder_plans')
    template_name = models.CharField(max_length=100, blank=True, null=True, help_text="Custom or rule template name (e.g. servicereminder, batteryservice)")
    reminder_no = models.PositiveIntegerField(default=1)
    scheduled_date = models.DateField()
    is_sent = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(ReminderPlan)
        super().save(*args, **kwargs)

    def __str__(self):
        title = self.reminder.service.name if (self.reminder and self.reminder.service) else (self.template_name or 'Reminder')
        return f"{self.invoice.customer.name} - {title} - No.{self.reminder_no} on {self.scheduled_date}"


class JobCard(BaseModel):
    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DELAYED = 'delayed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DELAYED, 'Delayed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE, related_name='job_cards')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='job_cards')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='job_cards')
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE, related_name='job_cards')
    quotation = models.OneToOneField(
        'client_management.Quotation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_card',
    )
    job_quotation = models.OneToOneField(
        'booking_management.JobQuotation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_card',
    )

    job_number = models.CharField(max_length=50, unique=True, db_index=True)
    job_date = models.DateField(default=timezone.now)
    expected_delivery_date = models.DateTimeField(null=True, blank=True)
    delivery_lead_time = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 2 hours, 1 day")
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    current_section = models.CharField(max_length=100, default='General Inspection')
    current_service = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)

    additional_remarks = models.TextField(blank=True, null=True)
    appointment_details = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-date_added']

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(JobCard)
        if not self.job_number:
            self.job_number = f"JC-{self.auto_id:04d}"
        super().save(*args, **kwargs)

    def calculate_estimated_cost(self):
        s_tot = sum((item.total_amount or 0) for item in self.service_items.filter(is_deleted=False))
        p_tot = sum((item.total_amount or 0) for item in self.part_items.filter(is_deleted=False))
        l_tot = sum((item.total_amount or 0) for item in self.labour_items.filter(is_deleted=False))
        e_tot = sum((item.total_amount or 0) for item in self.extra_items.filter(is_deleted=False))
        self.estimated_cost = s_tot + p_tot + l_tot + e_tot
        return self.estimated_cost

    def __str__(self):
        return f"{self.job_number} - {self.vehicle.vehicle_number} ({self.customer.name})"


class JobCardServiceItem(BaseModel):
    job_card = models.ForeignKey(JobCard, on_delete=models.CASCADE, related_name='service_items')
    service = models.ForeignKey('service_management.Service', on_delete=models.SET_NULL, null=True, blank=True)
    service_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    unit = models.CharField(max_length=50, default='Unit')
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    warranty = models.CharField(max_length=100, blank=True, null=True)
    warranty_period = models.CharField(max_length=100, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(JobCardServiceItem)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service_name} ({self.job_card.job_number})"


class JobCardPartItem(BaseModel):
    job_card = models.ForeignKey(JobCard, on_delete=models.CASCADE, related_name='part_items')
    stock_item = models.ForeignKey('client_management.Stock', on_delete=models.SET_NULL, null=True, blank=True)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    alternate_part_number = models.CharField(max_length=100, blank=True, null=True)
    product_code = models.CharField(max_length=100, blank=True, null=True)
    product_name = models.CharField(max_length=200)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=50, default='Pcs')
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    rate_with_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(JobCardPartItem)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.job_card.job_number})"


class JobCardLabourItem(BaseModel):
    job_card = models.ForeignKey(JobCard, on_delete=models.CASCADE, related_name='labour_items')
    labour_particulars = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(JobCardLabourItem)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.labour_particulars} ({self.job_card.job_number})"


class JobCardExtraItem(BaseModel):
    job_card = models.ForeignKey(JobCard, on_delete=models.CASCADE, related_name='extra_items')
    extra_details = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_type = models.CharField(max_length=20, default='amount')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.auto_id:
            from core.functions import get_auto_id
            self.auto_id = get_auto_id(JobCardExtraItem)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.extra_details} ({self.job_card.job_number})"


class JobLead(BaseModel):
    STATUS_FOLLOW_UP = 'follow_up'
    STATUS_QUOTED = 'quoted'
    STATUS_SUCCESS = 'success'
    STATUS_LOST = 'lost'
    STATUS_CHOICES = (
        (STATUS_FOLLOW_UP, 'Follow-up'),
        (STATUS_QUOTED, 'Quoted'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_LOST, 'Lost'),
    )

    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE, related_name='job_leads')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='job_leads', null=True, blank=True)
    lead_date = models.DateField(null=True, blank=True)
    staff = models.ForeignKey('client_management.Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    customer_type = models.ForeignKey('client_management.CustomerType', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    customer_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=50)
    whatsapp_number = models.CharField(max_length=50, blank=True, null=True)
    lead_generation_mode = models.CharField(max_length=100, blank=True, null=True)
    reference = models.CharField(max_length=200, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    expected_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_FOLLOW_UP, db_index=True)
    success_chance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lost_reason = models.CharField(max_length=200, blank=True, null=True)
    next_follow_up_date = models.DateField(null=True, blank=True)
    service_name = models.CharField(max_length=200, blank=True, null=True)
    staff_name = models.CharField(max_length=200, blank=True, null=True)
    vehicle_number = models.CharField(max_length=100, blank=True, null=True)
    vehicle_make = models.CharField(max_length=150, blank=True, null=True)
    vehicle_model = models.CharField(max_length=150, blank=True, null=True)
    vehicle_type = models.ForeignKey('master.VehicleType', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    vehicle_segment = models.ForeignKey('master.VehicleTypeModel', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    vehicle_color = models.ForeignKey('master.VehicleColor', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    vehicle_emission_standard = models.ForeignKey('master.EmissionStandard', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    vehicle_fuel_type = models.CharField(max_length=20, blank=True, null=True)
    vehicle_wheel_type = models.CharField(max_length=20, blank=True, null=True)
    vehicle_make_master = models.ForeignKey('master.VehicleMake', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')
    vehicle_model_master = models.ForeignKey('master.VehicleBrandModel', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_leads')

    class Meta:
        ordering = ['-date_added']


class JobLeadGenerationMode(BaseModel):
    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE, related_name='job_lead_generation_modes')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']
        unique_together = ('company', 'name')


class JobLeadServiceInterest(BaseModel):
    lead = models.ForeignKey(JobLead, on_delete=models.CASCADE, related_name='service_interests')
    service = models.ForeignKey('service_management.Service', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_lead_interests')
    category_name = models.CharField(max_length=150, blank=True, null=True)
    service_name = models.CharField(max_length=200)
    expected_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class JobLeadFollowUp(BaseModel):
    lead = models.ForeignKey(JobLead, on_delete=models.CASCADE, related_name='follow_ups')
    remarks = models.TextField()
    next_follow_up_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=JobLead.STATUS_CHOICES, default=JobLead.STATUS_FOLLOW_UP)
    success_chance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lost_reason = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ['-date_added']


class JobQuotation(BaseModel):
    quotation_number = models.CharField(max_length=50, unique=True)
    lead = models.ForeignKey(JobLead, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotations')
    revised_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisions')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='job_quotations')
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE, related_name='job_quotations')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='job_quotations', null=True, blank=True)
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_job_quotations')
    customer_comments = models.TextField(blank=True, null=True)
    additional_services = models.TextField(blank=True, null=True)
    additional_days_needed = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=20, default='amount')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_grand_total = models.BooleanField(default=True)


class JobQuotationItem(BaseModel):
    quotation = models.ForeignKey(JobQuotation, on_delete=models.CASCADE, related_name='items')
    service = models.ForeignKey('service_management.Service', on_delete=models.SET_NULL, null=True, blank=True)
    service_name = models.CharField(max_length=200)
    stock_item = models.ForeignKey('client_management.Stock', on_delete=models.SET_NULL, null=True, blank=True)
    stock_item_name = models.CharField(max_length=200, blank=True, null=True)
    warranty_years = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_topup = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)


class JobQuotationExtra(BaseModel):
    quotation = models.ForeignKey(JobQuotation, on_delete=models.CASCADE, related_name='extras')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=20, default='amount')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.TextField(blank=True, null=True)
