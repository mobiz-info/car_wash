from django.db import models
from core.models import BaseModel
from client_management.models import Customer, CustomerVehicle, Branch
from service_management.models import Service

class Invoice(BaseModel):
    invoice_number = models.CharField(max_length=50, unique=True)
    date = models.DateField(auto_now_add=True)
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='invoices')
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE, related_name='invoices')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='invoices')
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"INV-{self.invoice_number} - {self.customer.name}"

class InvoiceItem(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    service_name = models.CharField(max_length=150)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.service_name}"
