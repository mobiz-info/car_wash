import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')

import django
django.setup()

from master.models import OilBrand, OilGrade, OilProduct, OilStock, OilStockTransaction, VehicleType, VehicleMake
from client_management.models import Branch
from core.functions import get_auto_id

print("Clearing existing oil transactions, stocks, products, brands, and grades...")
OilStockTransaction.objects.all().delete()
OilStock.objects.all().delete()
OilProduct.objects.all().delete()
OilBrand.objects.all().delete()
OilGrade.objects.all().delete()

# 1. Create Famous Oil Brands
brands_list = ["Castrol", "Mobil 1", "Shell", "TotalEnergies", "Motul"]
created_brands = {}
for name in brands_list:
    b, _ = OilBrand.objects.get_or_create(
        name=name,
        defaults={'auto_id': get_auto_id(OilBrand), 'is_active': True}
    )
    created_brands[name] = b
    print(f"Created Brand: {b.name}")

# 2. Create Famous Oil Grades
grades_list = ["5W-30", "10W-40", "15W-40", "0W-20", "20W-50"]
created_grades = {}
for name in grades_list:
    g, _ = OilGrade.objects.get_or_create(
        name=name,
        defaults={'auto_id': get_auto_id(OilGrade), 'is_active': True}
    )
    created_grades[name] = g
    print(f"Created Grade: {g.name}")

# Fetch vehicle types and makes for sample scoping
sedan = VehicleType.objects.filter(name__icontains="Sedan").first()
suv = VehicleType.objects.filter(name__icontains="SUV").first()
hatchback = VehicleType.objects.filter(name__icontains="Hatchback").first()

honda = VehicleMake.objects.filter(name__icontains="Honda").first()
toyota = VehicleMake.objects.filter(name__icontains="Toyota").first()

# 3. Create Oil Products with Multiple Volumes (Variants)
products_data = [
    # Castrol GTX 5W-30 variants
    {
        "brand": created_brands["Castrol"],
        "grade": created_grades["5W-30"],
        "name": "GTX Fully Synthetic",
        "vehicle_type": sedan,
        "vehicle_make": honda,
        "price_per_litre": 450.00,
        "recommended_qty_litres": 1.0,
        "initial_stock": 5.0,
    },
    {
        "brand": created_brands["Castrol"],
        "grade": created_grades["5W-30"],
        "name": "GTX Fully Synthetic",
        "vehicle_type": sedan,
        "vehicle_make": honda,
        "price_per_litre": 450.00,
        "recommended_qty_litres": 3.0,
        "initial_stock": 10.0,
    },
    # Mobil 1 0W-20 variants
    {
        "brand": created_brands["Mobil 1"],
        "grade": created_grades["0W-20"],
        "name": "Advanced Fuel Economy",
        "vehicle_type": suv,
        "vehicle_make": toyota,
        "price_per_litre": 620.00,
        "recommended_qty_litres": 1.0,
        "initial_stock": 5.0,
    },
    {
        "brand": created_brands["Mobil 1"],
        "grade": created_grades["0W-20"],
        "name": "Advanced Fuel Economy",
        "vehicle_type": suv,
        "vehicle_make": toyota,
        "price_per_litre": 620.00,
        "recommended_qty_litres": 4.0,
        "initial_stock": 10.0,
    },
    # Shell Helix 10W-40 variants
    {
        "brand": created_brands["Shell"],
        "grade": created_grades["10W-40"],
        "name": "Helix HX7 Synthetic Technology",
        "vehicle_type": hatchback,
        "vehicle_make": None,
        "price_per_litre": 380.00,
        "recommended_qty_litres": 1.0,
        "initial_stock": 5.0,
    },
    {
        "brand": created_brands["Shell"],
        "grade": created_grades["10W-40"],
        "name": "Helix HX7 Synthetic Technology",
        "vehicle_type": hatchback,
        "vehicle_make": None,
        "price_per_litre": 380.00,
        "recommended_qty_litres": 3.0,
        "initial_stock": 10.0,
    },
]

active_branches = list(Branch.objects.filter(is_deleted=False))

for pdata in products_data:
    p = OilProduct.objects.create(
        auto_id=get_auto_id(OilProduct),
        company=None,  # Superadmin global master
        oil_brand=pdata["brand"],
        oil_grade=pdata["grade"],
        name=pdata["name"],
        vehicle_type=pdata["vehicle_type"],
        vehicle_make=pdata["vehicle_make"],
        price_per_litre=pdata["price_per_litre"],
        recommended_qty_litres=pdata["recommended_qty_litres"],
        is_active=True
    )
    print(f"Created Oil Product Variant: {p.display_name} ({p.recommended_qty_litres}L)")

    # Seed stock for all branches
    for b in active_branches:
        stock = OilStock.objects.create(
            auto_id=get_auto_id(OilStock),
            branch=b,
            oil_product=p,
            quantity_litres=pdata["initial_stock"],
            low_stock_alert_litres=2.0,
        )
        print(f"  -> Seeded Stock for Branch {b.name}: {stock.quantity_litres} units")

print("\nFinished seeding oil brands, grades, variants, and stock successfully!")
