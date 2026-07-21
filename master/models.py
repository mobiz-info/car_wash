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
    
class Supplier(BaseModel):
    company = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=200)
    address = models.TextField()
    gst_no = models.CharField(max_length=50, blank=True, null=True)
    phone_no = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

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

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_entries'
    )

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )


class VehicleColor(BaseModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class VehicleMake(BaseModel):
    """Manufacturer / Make — e.g. Honda, Toyota, Skoda (optional 3rd level)"""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class VehicleBrandModel(BaseModel):
    vehicle_type_model = models.ForeignKey(VehicleTypeModel, on_delete=models.CASCADE, related_name='brand_models')
    make = models.ForeignKey(VehicleMake, on_delete=models.SET_NULL, null=True, blank=True, related_name='models')
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        if self.make:
            return f"{self.vehicle_type_model.name} - {self.make.name} - {self.name}"
        return f"{self.vehicle_type_model.name} - {self.name}"

    class Meta:
        ordering = ['vehicle_type_model__name', 'name']
        unique_together = ['vehicle_type_model', 'make', 'name']


# ─────────────────────────────────────────────────────────────────────────────
# Oil & Tyre Masters (for multi-category service tracking)
# ─────────────────────────────────────────────────────────────────────────────

class OilProduct(BaseModel):
    """Company-level or Global master list of oil brands and grades."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='oil_products',
        null=True, blank=True, help_text="Leave blank for Superadmin global master"
    )
    brand = models.CharField(max_length=100, help_text="e.g. Castrol, Mobil 1, Shell")
    name = models.CharField(max_length=150, help_text="Product name e.g. GTX, Edge, Helix")
    grade = models.CharField(max_length=50, help_text="Viscosity grade e.g. 5W-30, 10W-40")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'brand', 'name', 'grade')
        ordering = ['brand', 'name']

    def __str__(self):
        return f"{self.brand} — {self.name} ({self.grade})"

    @property
    def display_name(self):
        return f"{self.brand} {self.name} {self.grade}"


class OilProductPrice(BaseModel):
    """Per-company pricing: Oil Product × Vehicle Type × Vehicle Make → price per litre.
    Lookup priority: make match > type match > generic (no type/make).
    """
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='oil_product_prices'
    )
    oil_product = models.ForeignKey(
        OilProduct, on_delete=models.CASCADE, related_name='prices'
    )
    vehicle_type = models.ForeignKey(
        VehicleType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oil_prices', help_text="Leave blank to apply to all vehicle types"
    )
    vehicle_make = models.ForeignKey(
        VehicleMake, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oil_prices', help_text="Leave blank to apply to all makes"
    )
    price_per_litre = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price charged per litre of this oil (e.g. 450.00)"
    )
    recommended_qty_litres = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Recommended fill quantity for this vehicle (e.g. 4.0 for Sedan)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['oil_product__brand', 'oil_product__name']

    def __str__(self):
        parts = [str(self.oil_product)]
        if self.vehicle_make:
            parts.append(self.vehicle_make.name)
        elif self.vehicle_type:
            parts.append(self.vehicle_type.name)
        return ' — '.join(parts) + f' @ {self.price_per_litre}/L'


class TyreBrand(BaseModel):
    """Company-level master list of tyre brands."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='tyre_brands'
    )
    brand = models.CharField(max_length=100, help_text="e.g. MRF, Apollo, Bridgestone, CEAT")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'brand')
        ordering = ['brand']

    def __str__(self):
        return self.brand


class OilStock(BaseModel):
    """Per-branch stock level for a specific oil product."""
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='oil_stocks'
    )
    oil_product = models.ForeignKey(
        OilProduct, on_delete=models.CASCADE, related_name='stocks'
    )
    quantity_litres = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Current stock in litres"
    )
    low_stock_alert_litres = models.DecimalField(
        max_digits=10, decimal_places=2, default=5,
        help_text="Alert when stock falls below this level"
    )

    class Meta:
        unique_together = ('branch', 'oil_product')

    def __str__(self):
        return f"{self.branch.name} — {self.oil_product} : {self.quantity_litres}L"

    @property
    def is_low(self):
        return self.quantity_litres <= self.low_stock_alert_litres


class OilStockTransaction(BaseModel):
    """Ledger of stock-in (purchases) and stock-out (usage on invoices)."""
    TYPE_IN = 'in'
    TYPE_OUT = 'out'
    TYPE_CHOICES = [
        (TYPE_IN, 'Stock In (Purchase)'),
        (TYPE_OUT, 'Stock Out (Used in Service)'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='oil_transactions'
    )
    oil_product = models.ForeignKey(
        OilProduct, on_delete=models.CASCADE, related_name='transactions'
    )
    transaction_type = models.CharField(max_length=5, choices=TYPE_CHOICES)
    quantity_litres = models.DecimalField(max_digits=10, decimal_places=2)
    reference_invoice = models.ForeignKey(
        'finance_management.Invoice',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='oil_transactions',
        help_text="Linked invoice for stock-out entries"
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        direction = '↑' if self.transaction_type == self.TYPE_IN else '↓'
        return f"{direction} {self.quantity_litres}L — {self.oil_product} @ {self.branch.name}"