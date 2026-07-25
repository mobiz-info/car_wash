import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')

import django
django.setup()

from master.models import OilBrand, OilGrade, OilProduct
from core.functions import get_auto_id

print("Seeding famous Oil Brands, Oil Grades, and Oil Products...")

brands_data = ["Mobil 1", "Shell", "Liqui Moly", "Motul", "Castrol", "Valvoline", "TotalEnergies"]
created_brands = {}
for b_name in brands_data:
    b, _ = OilBrand.objects.get_or_create(name=b_name, defaults={'auto_id': get_auto_id(OilBrand), 'is_active': True})
    created_brands[b_name] = b
    print(f"Brand: {b.name}")

grades_data = ["0W-20", "5W-30", "5W-40", "10W-40", "15W-40"]
created_grades = {}
for g_name in grades_data:
    g, _ = OilGrade.objects.get_or_create(name=g_name, defaults={'auto_id': get_auto_id(OilGrade), 'is_active': True})
    created_grades[g_name] = g
    print(f"Grade: {g.name}")

products_data = [
    {
        "brand": created_brands["Mobil 1"],
        "grade": created_grades["0W-20"],
        "name": "Advanced Fuel Economy",
        "price_per_litre": 650.00,
        "volumes": [1.0, 4.0],
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "brand": created_brands["Shell"],
        "grade": created_grades["5W-40"],
        "name": "Helix Ultra Fully Synthetic",
        "price_per_litre": 550.00,
        "volumes": [1.0, 3.5, 4.0],
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "brand": created_brands["Liqui Moly"],
        "grade": created_grades["5W-30"],
        "name": "Leichtlauf High Tech",
        "price_per_litre": 750.00,
        "volumes": [1.0, 4.0],
        "oil_run_km": 12000,
        "oil_run_days": 365,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "brand": created_brands["Motul"],
        "grade": created_grades["10W-40"],
        "name": "6100 Synergie+",
        "price_per_litre": 480.00,
        "volumes": [1.0, 4.0],
        "oil_run_km": 7500,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "brand": created_brands["Castrol"],
        "grade": created_grades["5W-30"],
        "name": "GTX Fully Synthetic",
        "price_per_litre": 500.00,
        "volumes": [1.0, 3.5, 4.0],
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
    {
        "brand": created_brands["Valvoline"],
        "grade": created_grades["15W-40"],
        "name": "All Fleet Premium",
        "price_per_litre": 420.00,
        "volumes": [1.0, 5.0],
        "oil_run_km": 5000,
        "oil_run_days": 90,
        "for_petrol": False,
        "for_diesel": True,
    },
    {
        "brand": created_brands["TotalEnergies"],
        "grade": created_grades["5W-30"],
        "name": "Quartz 9000 Future",
        "price_per_litre": 520.00,
        "volumes": [1.0, 4.0],
        "oil_run_km": 10000,
        "oil_run_days": 180,
        "for_petrol": True,
        "for_diesel": True,
    },
]

for p_item in products_data:
    for vol in p_item["volumes"]:
        prod, created = OilProduct.objects.get_or_create(
            oil_brand=p_item["brand"],
            oil_grade=p_item["grade"],
            name=p_item["name"],
            recommended_qty_litres=vol,
            company=None,
            defaults={
                'auto_id': get_auto_id(OilProduct),
                'price_per_litre': p_item["price_per_litre"],
                'oil_run_km': p_item["oil_run_km"],
                'oil_run_days': p_item["oil_run_days"],
                'for_petrol': p_item["for_petrol"],
                'for_diesel': p_item["for_diesel"],
                'is_active': True,
            }
        )
        if not created:
            prod.price_per_litre = p_item["price_per_litre"]
            prod.oil_run_km = p_item["oil_run_km"]
            prod.oil_run_days = p_item["oil_run_days"]
            prod.for_petrol = p_item["for_petrol"]
            prod.for_diesel = p_item["for_diesel"]
            prod.save()
        print(f"Seeded Oil Product: {prod.display_name} ({vol}L) - ₹{prod.price_per_litre}/L")

print("\nFamous Oil Products seed completed successfully!")
