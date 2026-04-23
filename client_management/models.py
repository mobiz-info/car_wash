from django.db import models
from core.models import BaseModel

class Client(BaseModel):
    company_name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)
    gst_number = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.ForeignKey('master.State', on_delete=models.SET_NULL, blank=True, null=True)
    country = models.ForeignKey('master.Country', on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return f"{self.company_name} ({self.owner_name})"
