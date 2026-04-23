from django.db import models

from master.models import Country
from core.models import BaseModel

# Create your models here.
class Tax(BaseModel):
    TAX_TYPE = (
        ('direct', 'Direct'),
        ('tax_on_tax', 'Tax on Tax'), 
    )

    MODE = (
        ('interstate', 'Interstate'),
        ('intrastate', 'Intrastate'),
    )

    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    tax_type = models.CharField(max_length=10, choices=TAX_TYPE)
    mode = models.CharField(max_length=15, choices=MODE)