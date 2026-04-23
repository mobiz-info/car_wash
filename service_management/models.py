from django.db import models
from core.models import BaseModel

class ServiceType(BaseModel):
    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Service(BaseModel):
    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE)
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.IntegerField(help_text="Minutes")

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (₹{self.price})"
