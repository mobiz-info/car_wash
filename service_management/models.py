from django.db import models
from core.models import BaseModel
from master.models import VehicleType,VehicleTypeModel
from client_management.models import Branch


from django.utils.text import slugify

class ServiceType(BaseModel):
    SLUG_WASHING = 'washing'
    SLUG_OIL_CHANGE = 'oil_change'
    SLUG_TYRE_CHANGE = 'tyre_change'
    SLUG_WHEEL_ALIGNMENT = 'wheel_alignment'

    name = models.CharField(max_length=100)
    slug = models.SlugField(
        max_length=50, unique=True, blank=True, null=True,
        help_text="Machine-readable key: washing | oil_change | tyre_change | wheel_alignment"
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name).replace('-', '_')
            slug = base_slug
            counter = 1
            while ServiceType.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base_slug}_{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

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
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='service_branches')

    is_enabled = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.branch} - {self.service}"


class CompanyService(BaseModel):
    """Services enabled at the company level. Branches can only enable a subset of these."""
    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE, related_name='company_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='company_service_entries')
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'service')

    def __str__(self):
        return f"{self.company} - {self.service}"
    
    
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


class BranchServiceCategory(BaseModel):
    """Controls which service categories (ServiceType) are enabled for a branch.
    Only enabled categories appear in the mobile app.
    """
    branch = models.ForeignKey(
        'client_management.Branch',
        on_delete=models.CASCADE,
        related_name='enabled_categories'
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE,
        related_name='branch_categories'
    )
    is_enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = ('branch', 'service_type')

    def __str__(self):
        status = 'ON' if self.is_enabled else 'OFF'
        return f"{self.branch.name} — {self.service_type.name} ({status})"
