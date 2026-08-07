import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')

import django
django.setup()

from master.models import OilBrand, OilGrade, OilProduct
from core.functions import get_auto_id

print("Seeding 5 Famous Oil Brands, Grades, and Products...")

famous_oils = [
    {
        "category": "Engine Oil",
        "brand": "Mobil",
        "grade": "0W-40",
        "name": "Mobil 1 0W-40 Synthetic",
        "price_per_litre": 850.00,
        "oil_run_km": 10000,
        "oil_run_days": 365,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Engine Oil",
        "brand": "Castrol",
        "grade": "5W-30",
        "name": "Castrol EDGE 5W-30 Titanium",
        "price_per_litre": 750.00,
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Engine Oil",
        "brand": "Shell",
        "grade": "5W-40",
        "name": "Shell Helix Ultra 5W-40",
        "price_per_litre": 680.00,
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Engine Oil",
        "brand": "Motul",
        "grade": "5W-40",
        "name": "Motul 8100 X-cess 5W-40",
        "price_per_litre": 790.00,
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Engine Oil",
        "brand": "Total",
        "grade": "5W-30",
        "name": "Total Quartz 9000 5W-30",
        "price_per_litre": 620.00,
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Brake Fluid",
        "brand": "Bosch",
        "grade": "DOT 4",
        "name": "Bosch High Performance Brake Fluid",
        "price_per_litre": 450.00,
        "oil_run_km": 20000,
        "oil_run_days": 365,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Power Steering Oil",
        "brand": "Castrol",
        "grade": "ATF",
        "name": "Castrol Transmax Power Steering Fluid",
        "price_per_litre": 520.00,
        "oil_run_km": 30000,
        "oil_run_days": 365,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Transmission Fluid",
        "brand": "Mobil",
        "grade": "ATF 3309",
        "name": "Mobil ATF 3309 Automatic Transmission Fluid",
        "price_per_litre": 650.00,
        "oil_run_km": 40000,
        "oil_run_days": 730,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Differential Oil",
        "brand": "Shell",
        "grade": "80W-90",
        "name": "Shell Spirax S2 A 80W-90 Differential Gear Oil",
        "price_per_litre": 580.00,
        "oil_run_km": 40000,
        "oil_run_days": 730,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Coolant",
        "brand": "Total",
        "grade": "Ready Mix",
        "name": "Total Coolelf Auto Supra Coolant",
        "price_per_litre": 380.00,
        "oil_run_km": 30000,
        "oil_run_days": 365,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Gear Oil",
        "brand": "Motul",
        "grade": "75W-90",
        "name": "Motul Motylgear 75W-90 Manual Transmission & Gear Oil",
        "price_per_litre": 720.00,
        "oil_run_km": 40000,
        "oil_run_days": 730,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "category": "Transfer Case Fluid",
        "brand": "Castrol",
        "grade": "75W-140",
        "name": "Castrol Syntrax Transfer Case Fluid",
        "price_per_litre": 890.00,
        "oil_run_km": 40000,
        "oil_run_days": 730,
        "for_petrol": True,
        "for_diesel": True,
    },
]

for item in famous_oils:
    # 1. Get or create OilBrand
    b_obj, _ = OilBrand.objects.get_or_create(
        name=item["brand"],
        defaults={'auto_id': get_auto_id(OilBrand), 'is_active': True}
    )

    # 2. Get or create OilGrade
    g_obj, _ = OilGrade.objects.get_or_create(
        name=item["grade"],
        defaults={'auto_id': get_auto_id(OilGrade), 'is_active': True}
    )

    # 3. Get or create OilProduct
    cat = item.get("category", "Engine Oil")
    prod, created = OilProduct.objects.get_or_create(
        oil_brand=b_obj,
        name=item["name"],
        defaults={
            'auto_id': get_auto_id(OilProduct),
            'category': cat,
            'oil_grade': g_obj,
            'brand': item["brand"],
            'grade': item["grade"],
            'price_per_litre': item["price_per_litre"],
            'oil_run_km': item["oil_run_km"],
            'oil_run_days': item["oil_run_days"],
            'for_petrol': item["for_petrol"],
            'for_diesel': item["for_diesel"],
            'is_active': True,
        }
    )

    if not created:
        prod.category = cat
        prod.oil_grade = g_obj
        prod.brand = item["brand"]
        prod.grade = item["grade"]
        prod.price_per_litre = item["price_per_litre"]
        prod.oil_run_km = item["oil_run_km"]
        prod.oil_run_days = item["oil_run_days"]
        prod.save()

    print(f"✓ Seeded Oil Product: {prod.display_name} — ₹{prod.price_per_litre}/L ({prod.oil_run_km} KM / {prod.oil_run_days} days)")

print("\nFamous Oil Products seeded successfully!")
