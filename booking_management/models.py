from django.db import models
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

    def __str__(self):
        return f"{self.service.name} Reminder - {self.days_after} Days"


class SentServiceReminder(BaseModel):
    reminder = models.ForeignKey(ServiceReminder, on_delete=models.CASCADE, related_name='sent_instances')
    invoice = models.ForeignKey('finance_management.Invoice', on_delete=models.CASCADE, related_name='sent_reminders')
    sent_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Sent to {self.invoice.customer.name} on {self.sent_date}"