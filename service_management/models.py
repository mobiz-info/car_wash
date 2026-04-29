from django.db import models
from core.models import BaseModel

class ServiceType(BaseModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Service(BaseModel):
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    duration = models.IntegerField(help_text="Minutes")

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} "


class BranchService(BaseModel):
    branch = models.ForeignKey('Branch', on_delete=models.CASCADE, related_name='branch_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='service_branches')

    is_enabled = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.branch} - {self.service}"