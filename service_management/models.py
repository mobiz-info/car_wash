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
