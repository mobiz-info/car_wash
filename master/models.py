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
    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_types')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    
    
class EmissionStandard(BaseModel):
    FUEL_TYPE_CHOICES = (
        ('ALL', 'All Fuel Types'),
        ('PETROL', 'Petrol'),
        ('DIESEL', 'Diesel'),
        ('CNG', 'CNG'),
        ('LPG', 'LPG'),
        ('ELECTRIC', 'Electric'),
    )

    name = models.CharField(max_length=100, help_text="e.g. BS-3, BS-4, BS-6, EV")
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES, default='ALL')
    validity_months = models.PositiveIntegerField(default=12, help_text="Smoke test validity in months (e.g. 6 or 12)")
    reminder_1_days = models.PositiveIntegerField(default=15, help_text="1st reminder sent X days before expiry")
    reminder_2_days = models.PositiveIntegerField(default=3, help_text="2nd reminder sent X days before expiry")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['validity_months', 'name']

    def __str__(self):
        fuel = f" ({self.get_fuel_type_display()})" if self.fuel_type != 'ALL' else ""
        return f"{self.name}{fuel} — {self.validity_months} Months"


class VehicleTypeModel(BaseModel):
    company = models.ForeignKey('client_management.Client', on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_segments')
    vehicle_type = models.ForeignKey(VehicleType,on_delete=models.CASCADE,related_name='models')

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    emission_standard = models.ForeignKey(EmissionStandard, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicle_segments')

    is_active = models.BooleanField(default=True)
    disabled_companies = models.ManyToManyField('client_management.Client', blank=True, related_name='disabled_global_vehicle_segments')

    def __str__(self):
        return f"{self.vehicle_type.name} - {self.name}"

    class Meta:
        unique_together = ['company', 'vehicle_type', 'name']


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
    branch = models.ForeignKey('client_management.Branch', on_delete=models.SET_NULL, blank=True, null=True, related_name='suppliers')
    name = models.CharField(max_length=200)
    address = models.TextField()
    gst_no = models.CharField(max_length=50, blank=True, null=True)
    phone_no = models.CharField(max_length=50)
    supplier_type = models.CharField(max_length=20, default='cash', choices=(('cash', 'Cash'), ('credit', 'Credit'), ('bill_to_bill', 'Bill to Bill')))
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit_days = models.PositiveIntegerField(default=30, help_text="Default credit period in days")
    no_of_invoices = models.PositiveIntegerField(default=0)
    payables = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Total outstanding payables amount")
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

    # Stock Purchase linkage
    CATEGORY_GENERAL = 'GENERAL'
    CATEGORY_OIL = 'OIL'
    CATEGORY_TYRE = 'TYRE'
    CATEGORY_OIL_FILTER = 'OIL_FILTER'
    CATEGORY_BATTERY = 'BATTERY'
    ITEM_CATEGORY_CHOICES = (
        (CATEGORY_GENERAL, 'General Stock'),
        (CATEGORY_OIL, 'Engine Oil / Fluid'),
        (CATEGORY_TYRE, 'Tyre'),
        (CATEGORY_OIL_FILTER, 'Oil Filter'),
        (CATEGORY_BATTERY, 'Battery'),
    )
    item_category = models.CharField(
        max_length=20,
        choices=ITEM_CATEGORY_CHOICES,
        blank=True,
        null=True
    )
    stock_item = models.ForeignKey(
        'client_management.Stock',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_purchases'
    )
    oil_product = models.ForeignKey(
        'OilProduct',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_purchases'
    )
    tyre = models.ForeignKey(
        'Tyre',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_purchases'
    )
    oil_filter = models.ForeignKey(
        'OilFilter',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_purchases'
    )
    battery = models.ForeignKey(
        'Battery',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_purchases'
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.00
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

class OilBrand(BaseModel):
    """Superadmin / Master list of Oil Brands (e.g. Castrol, Mobil 1, Shell, Total, Motul)."""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OilFilterBrand(BaseModel):
    """Master list of Oil Filter Brands (e.g. Bosch, Mann, FRAM, Mobil 1, Wix, Denso)."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='oil_filter_brands',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OilFilter(BaseModel):
    """Master list of Oil Filters with Brand, Price, and Running KM interval."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='oil_filters',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    oil_filter_brand = models.ForeignKey(
        OilFilterBrand, on_delete=models.CASCADE, related_name='filters'
    )
    name = models.CharField(max_length=150, help_text="Filter part number / model name e.g. OF-101")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Price charged for this filter"
    )
    running_km = models.PositiveIntegerField(
        default=5000,
        help_text="Recommended running KM for this oil filter e.g. 5000"
    )
    stock_qty = models.IntegerField(default=0, help_text="Current stock quantity in units")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['oil_filter_brand__name', 'name']

    def __str__(self):
        brand_name = self.oil_filter_brand.name if self.oil_filter_brand else ''
        return f"{brand_name} - {self.name} (₹{self.price})"

    @property
    def display_name(self):
        brand_name = self.oil_filter_brand.name if self.oil_filter_brand else ''
        return f"{brand_name} - {self.name}"


class OilGrade(BaseModel):
    """Superadmin / Master list of Oil Grades (e.g. 5W-30, 10W-40, 15W-40, 0W-20, 20W-50)."""
    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OilProduct(BaseModel):
    """Master list of Oil Products combining Brand, Grade, Vehicle Type/Make, and Price per Litre."""
    CATEGORY_CHOICES = [
        ('Engine Oil', 'Engine Oil'),
        ('Brake Fluid', 'Brake Fluid'),
        ('Power Steering Oil', 'Power Steering Oil'),
        ('Transmission Fluid', 'Transmission Fluid'),
        ('Differential Oil', 'Differential Oil'),
        ('Coolant', 'Coolant'),
        ('Gear Oil', 'Gear Oil'),
        ('Transfer Case Fluid', 'Transfer Case Fluid'),
    ]

    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='oil_products',
        null=True, blank=True, help_text="Leave blank for Superadmin global master"
    )
    category = models.CharField(
        max_length=100, choices=CATEGORY_CHOICES, default='Engine Oil',
        help_text="Category of oil / fluid"
    )
    oil_brand = models.ForeignKey(
        OilBrand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    oil_grade = models.ForeignKey(
        OilGrade, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    brand = models.CharField(max_length=100, blank=True, null=True, help_text="Legacy string brand fallback")
    name = models.CharField(max_length=150, blank=True, null=True, help_text="Product name e.g. GTX, Edge, Helix")
    grade = models.CharField(max_length=50, blank=True, null=True, help_text="Legacy string grade fallback")
    
    vehicle_type = models.ForeignKey(
        VehicleType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oil_products', help_text="Leave blank to apply to all vehicle types"
    )
    vehicle_make = models.ForeignKey(
        VehicleMake, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oil_products', help_text="Leave blank to apply to all makes"
    )
    price_per_litre = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Price charged per litre of this oil (e.g. 450.00)"
    )
    recommended_qty_litres = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Recommended fill quantity for this vehicle (e.g. 4.0 for Sedan)"
    )
    oil_run_km = models.PositiveIntegerField(
        default=5000,
        help_text="Number of KM this oil lasts for (e.g. 5000)"
    )
    for_petrol = models.BooleanField(default=True, help_text="Suitable for Petrol vehicles")
    for_diesel = models.BooleanField(default=True, help_text="Suitable for Diesel vehicles")
    oil_run_days = models.PositiveIntegerField(
        default=180,
        help_text="Number of days duration this oil lasts for (e.g. 30, 90, 180 days)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['oil_brand__name', 'name']

    def __str__(self):
        brand_name = self.oil_brand.name if self.oil_brand else (self.brand or '')
        grade_name = self.oil_grade.name if self.oil_grade else (self.grade or '')
        parts = [p for p in [brand_name, self.name, grade_name] if p]
        display = " ".join(parts)
        if self.price_per_litre > 0:
            display += f" — ₹{self.price_per_litre}/L"
        return display

    @property
    def display_name(self):
        brand_name = self.oil_brand.name if self.oil_brand else (self.brand or '')
        grade_name = self.oil_grade.name if self.oil_grade else (self.grade or '')
        parts = [p for p in [brand_name, self.name, grade_name] if p]
        return " ".join(parts)


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


class Tyre(BaseModel):
    """Master list of Tyres with Brand, Name, Size, Price, Stock Count, Lifespan KM, and Pattern."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='tyres',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    tyre_brand = models.ForeignKey(
        TyreBrand, on_delete=models.CASCADE, related_name='tyres'
    )
    name = models.CharField(max_length=150, help_text="Tyre model / name e.g. ZLX, Earth-1, Turanza")
    size = models.CharField(max_length=100, help_text="Tyre size e.g. 185/65 R15, 195/55 R16")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Price per tyre"
    )
    stock_qty = models.IntegerField(default=0, help_text="Available stock quantity in units")
    running_km = models.PositiveIntegerField(
        default=40000,
        help_text="Recommended running KM / Lifespan for this tyre e.g. 40000"
    )
    pattern_type = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="Pattern type e.g. Tubeless, Radial, All-Terrain"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['tyre_brand__brand', 'name', 'size']

    def __str__(self):
        brand_name = self.tyre_brand.brand if self.tyre_brand else ''
        return f"{brand_name} - {self.name} ({self.size}) (₹{self.price})"

    @property
    def display_name(self):
        brand_name = self.tyre_brand.brand if self.tyre_brand else ''
        return f"{brand_name} {self.name} {self.size}"


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


# ─────────────────────────────────────────────────────────────────────────────
# Battery Masters & Battery Stock
# ─────────────────────────────────────────────────────────────────────────────

class BatteryMake(BaseModel):
    """Master list of Battery Makes / Brands (e.g. Exide, Amaron, SF Sonic, Tata Green, Bosch)."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='battery_makes',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class BatteryAmpere(BaseModel):
    """Master list of Battery Amperes / Capacities (e.g. 35 Ah, 45 Ah, 60 Ah, 75 Ah, 100 Ah)."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='battery_amperes',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    name = models.CharField(max_length=50, help_text="e.g. 35 Ah, 45 Ah, 60 Ah, 75 Ah")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class BatterySegment(BaseModel):
    """Master list of Battery Segments (e.g. Tubular, Lithium-ion, SMF/VRLA, Conventional Lead-Acid)."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='battery_segments',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    name = models.CharField(max_length=100, help_text="e.g. Tubular, Lithium-ion, SMF, VRLA")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Battery(BaseModel):
    """Master / Vehicle Management list of Batteries combining Make, Ampere, Segment, Warranty, and Price."""
    company = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='batteries',
        null=True, blank=True, help_text="Leave blank for global master"
    )
    make = models.ForeignKey(
        BatteryMake, on_delete=models.CASCADE, related_name='batteries'
    )
    ampere = models.ForeignKey(
        BatteryAmpere, on_delete=models.CASCADE, related_name='batteries'
    )
    segment = models.ForeignKey(
        BatterySegment, on_delete=models.CASCADE, related_name='batteries'
    )
    warranty_years = models.DecimalField(
        max_digits=4, decimal_places=1, default=1.0,
        help_text="Warranty in years e.g. 1.0, 2.0, 3.0, 5.0"
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Default price charged for this battery"
    )
    stock_qty = models.IntegerField(default=0, help_text="Current stock quantity in units")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['make__name', 'ampere__name', 'segment__name']

    def __str__(self):
        make_name = self.make.name if self.make else ''
        amp_name = self.ampere.name if self.ampere else ''
        seg_name = self.segment.name if self.segment else ''
        return f"{make_name} {amp_name} ({seg_name}) - {self.warranty_years} Yrs - ₹{self.price}"

    @property
    def display_name(self):
        make_name = self.make.name if self.make else ''
        amp_name = self.ampere.name if self.ampere else ''
        seg_name = self.segment.name if self.segment else ''
        return f"{make_name} {amp_name} ({seg_name})"


# ─────────────────────────────────────────────────────────────────────────────
# Senior ERP Purchase & Stock Management Models
# ─────────────────────────────────────────────────────────────────────────────

class StockGroup(BaseModel):
    company = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='stock_groups', null=True, blank=True)
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class StockSubGroup(BaseModel):
    company = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='stock_sub_groups', null=True, blank=True)
    group = models.ForeignKey(StockGroup, on_delete=models.CASCADE, related_name='sub_groups')
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ['group__name', 'name']

    def __str__(self):
        return f"{self.group.name} — {self.name}"


class PurchaseInvoice(BaseModel):
    PURCHASE_TYPE_CASH = 'CASH'
    PURCHASE_TYPE_CREDIT = 'CREDIT'
    PURCHASE_TYPE_BILL = 'BILL_TO_BILL'
    PURCHASE_TYPE_CHOICES = (
        (PURCHASE_TYPE_CASH, 'Cash'),
        (PURCHASE_TYPE_CREDIT, 'Credit'),
        (PURCHASE_TYPE_BILL, 'Bill to Bill'),
    )

    PAYMENT_MODE_CASH = 'CASH'
    PAYMENT_MODE_DIGITAL = 'DIGITAL'
    PAYMENT_MODE_CHEQUE = 'CHEQUE'
    PAYMENT_MODE_CHOICES = (
        (PAYMENT_MODE_CASH, 'Cash'),
        (PAYMENT_MODE_DIGITAL, 'Digital'),
        (PAYMENT_MODE_CHEQUE, 'Cheque'),
    )

    company = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='purchase_invoices')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='purchase_invoices')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_invoices')
    purchase_inv_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    purchase_type = models.CharField(max_length=20, choices=PURCHASE_TYPE_CHOICES, default=PURCHASE_TYPE_CASH)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance_to_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default=PAYMENT_MODE_CASH)
    bank_name = models.CharField(max_length=150, blank=True, null=True)
    cheque_number = models.CharField(max_length=100, blank=True, null=True)
    cheque_date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-invoice_date', '-date_added']

    def __str__(self):
        return f"Purchase Inv #{self.purchase_inv_number} - {self.supplier.name}"


class PurchaseInvoiceItem(BaseModel):
    purchase_invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name='items')
    stock_item = models.ForeignKey('client_management.Stock', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_items')
    hsn_code = models.CharField(max_length=50, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    main_unit = models.CharField(max_length=50, blank=True, null=True)
    base_unit = models.CharField(max_length=50, blank=True, null=True)
    conversion_count = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_including_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        item_name = self.stock_item.item_name if self.stock_item else 'Item'
        return f"{item_name} x {self.quantity} @ {self.rate}"


class SupplierPayment(BaseModel):
    PAYMENT_MODE_CHOICES = (
        ('CASH', 'Cash'),
        ('DIGITAL', 'Digital'),
        ('CHEQUE', 'Cheque'),
    )

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payments')
    company = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='supplier_payments')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='supplier_payments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='CASH')
    bank_name = models.CharField(max_length=150, blank=True, null=True)
    cheque_number = models.CharField(max_length=100, blank=True, null=True)
    cheque_date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-payment_date', '-date_added']

    def __str__(self):
        return f"Payment to {self.supplier.name} - ₹{self.amount_paid} ({self.payment_mode})"