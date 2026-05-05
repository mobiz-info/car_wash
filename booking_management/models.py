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

    booking_date = models.DateField()
    booking_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"{self.customer.name} - {self.vehicle.vehicle_number} on {self.booking_date}"
