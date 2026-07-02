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
    scheme = models.ForeignKey('client_management.Scheme', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    
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
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # per-item scheme/manual discount

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.service_name}"



class Receipt(BaseModel):
    PAYMENT_CHOICES = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('digital_payments', 'Digital payments'),
    )

    receipt_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='receipts'
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_CHOICES)

    remarks = models.TextField(blank=True, null=True)

    cheque_no = models.CharField(max_length=100, blank=True, null=True)
    cheque_date = models.DateField(blank=True, null=True)
    bank_name = models.CharField(max_length=150, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.receipt_number