from django.db import models
from core.models import BaseModel

class Country(BaseModel):
    name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=10, blank=True, null=True, help_text="e.g. INR, AED")
    currency_symbol = models.CharField(max_length=10, blank=True, null=True, help_text="e.g. ₹, AED")

    def __str__(self):
        return self.name


class State(BaseModel):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class District(BaseModel):
    state = models.ForeignKey(State, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Area(BaseModel):
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class VehicleType(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    
class VehicleTypeModel(BaseModel):
    vehicle_type = models.ForeignKey(VehicleType,on_delete=models.CASCADE,related_name='models')

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.vehicle_type.name} - {self.name}"

    class Meta:
        unique_together = ['vehicle_type', 'name']


class SchemeType(BaseModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']