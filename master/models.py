from django.db import models
from core.models import BaseModel
from client_management.models import Branch,Client

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
        
        
class ExpenseHead(BaseModel):
    company = models.ForeignKey(Client,on_delete=models.CASCADE,null=True,blank=True)
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name

    @property
    def is_deletable(self):
        if self.name:
            return self.name.strip().lower() not in ['salary', 'purchase']
        return True

    def delete(self, *args, **kwargs):
        if not self.is_deletable:
            raise PermissionError("Salary and Purchase expense heads cannot be deleted.")
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.is_deleted and not self.is_deletable:
            raise PermissionError("Salary and Purchase expense heads cannot be deleted.")
        super().save(*args, **kwargs)
    
class Expense(BaseModel):
    expense_head = models.ForeignKey(
        ExpenseHead,
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name
    
class ExpenseEntry(BaseModel):
    company = models.ForeignKey(
        Client,
        on_delete=models.CASCADE
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE
    )

    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    expense_date = models.DateField()

    remarks = models.TextField(
        blank=True,
        null=True
    )


class VehicleColor(BaseModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class VehicleCompany(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


    