from django.db import models
from core.models import BaseModel
from master.models import VehicleType,VehicleTypeModel
from client_management.models import Branch


class ServiceType(BaseModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Service(BaseModel):
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    # duration = models.IntegerField(help_text="Minutes")

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} "


class BranchService(BaseModel):
    branch = models.ForeignKey('client_management.Branch', on_delete=models.CASCADE, related_name='branch_services')
    service = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name='service_branches')

    is_enabled = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.branch} - {self.service}"
    
    
class BranchVehiclePrice(BaseModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='vehicle_prices'
    )

    vehicle_type = models.ForeignKey(
        VehicleType,
        on_delete=models.CASCADE,
        related_name='branch_prices'
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'vehicle_type')

    def __str__(self):
        return f"{self.branch} - {self.vehicle_type} - {self.price}"

class ServiceVehicleTypePrice(BaseModel):
    """Price for a specific individual Service x VehicleType per branch (per-service pricing)."""
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='service_vehicle_prices'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='vehicle_type_prices'
    )
    vehicle_model = models.ForeignKey(
        VehicleTypeModel,
        null=True,
        blank=True,

        on_delete=models.CASCADE,
        related_name='service_type_prices'
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'service', 'vehicle_model')

    def __str__(self):
        return f"{self.branch} | {self.service.name} | {self.vehicle_model} - Rs.{self.price}"
