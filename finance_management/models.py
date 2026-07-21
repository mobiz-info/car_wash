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
    invoice_type = models.CharField(
        max_length=20, 
        choices=[('cashinvoice', 'Cash Invoice'), ('creditinvoice', 'Credit Invoice')], 
        default='cashinvoice'
    )
    
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


# ─────────────────────────────────────────────────────────────────────────────
# Category-specific invoice metadata
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceServiceDetail(BaseModel):
    """Stores category-specific metadata for an invoice line item.
    Only created for oil_change, tyre_change, wheel_alignment items.
    Washing items have no extra detail.
    """
    CATEGORY_WASHING = 'washing'
    CATEGORY_OIL = 'oil_change'
    CATEGORY_TYRE = 'tyre_change'
    CATEGORY_ALIGNMENT = 'wheel_alignment'
    CATEGORY_CHOICES = [
        (CATEGORY_WASHING, 'Washing'),
        (CATEGORY_OIL, 'Oil Change'),
        (CATEGORY_TYRE, 'Tyre Change'),
        (CATEGORY_ALIGNMENT, 'Wheel Alignment'),
    ]

    invoice_item = models.OneToOneField(
        InvoiceItem, on_delete=models.CASCADE, related_name='service_detail'
    )
    service_category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)

    # ── Oil Change fields ────────────────────────────────────────────────────
    oil_product = models.ForeignKey(
        'master.OilProduct', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='invoice_details'
    )
    oil_litres_used = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Litres of oil used in this service"
    )
    oil_filter_changed = models.BooleanField(default=False)
    odometer_at_service = models.PositiveIntegerField(
        null=True, blank=True, help_text="Vehicle km at time of service"
    )
    next_oil_change_km = models.PositiveIntegerField(
        null=True, blank=True, help_text="Recommended next oil change odometer reading"
    )
    next_oil_change_date = models.DateField(
        null=True, blank=True, help_text="Recommended next oil change date (optional)"
    )

    # ── Tyre Change fields ───────────────────────────────────────────────────
    tyre_brand = models.ForeignKey(
        'master.TyreBrand', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='invoice_details'
    )
    tyre_size = models.CharField(
        max_length=50, blank=True, help_text="e.g. 195/65 R15"
    )
    tyres_changed_count = models.PositiveSmallIntegerField(
        default=0, help_text="Number of tyres replaced (0-4)"
    )
    next_tyre_change_km = models.PositiveIntegerField(
        null=True, blank=True, help_text="Recommended next tyre change odometer reading"
    )
    next_tyre_change_date = models.DateField(
        null=True, blank=True, help_text="Recommended next tyre change date"
    )

    # ── Wheel Alignment / Balancing fields ───────────────────────────────────
    alignment_done = models.BooleanField(default=False)
    balancing_done = models.BooleanField(default=False)
    alignment_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_service_category_display()} — {self.invoice_item.invoice.invoice_number}"