import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')

import django
django.setup()

from master.models import OilFilterBrand, OilFilter
from core.functions import get_auto_id

print("Seeding Oil Filter Brands and Filters...")

brands = ["Bosch", "Mann-Filter", "FRAM"]
created_brands = {}
for name in brands:
    b, _ = OilFilterBrand.objects.get_or_create(
        name=name,
        defaults={'auto_id': get_auto_id(OilFilterBrand), 'is_active': True}
    )
    created_brands[name] = b
    print(f"Created/Found Oil Filter Brand: {b.name}")

filters_data = [
    {"brand": created_brands["Bosch"], "name": "OF-101 Premium Filter", "price": 250.00, "running_km": 5000},
    {"brand": created_brands["Mann-Filter"], "name": "W 712/95 Spin-On Filter", "price": 280.00, "running_km": 7500},
    {"brand": created_brands["FRAM"], "name": "Extra Guard PH6607 Filter", "price": 220.00, "running_km": 5000},
]

for f_item in filters_data:
    filt, created = OilFilter.objects.get_or_create(
        oil_filter_brand=f_item["brand"],
        name=f_item["name"],
        defaults={
            'auto_id': get_auto_id(OilFilter),
            'price': f_item["price"],
            'running_km': f_item["running_km"],
            'is_active': True,
        }
    )
    if not created:
        filt.price = f_item["price"]
        filt.running_km = f_item["running_km"]
        filt.save()
    print(f"Seeded Oil Filter: {filt.display_name} — ₹{filt.price} ({filt.running_km} KM)")

print("\nOil Filter seed completed successfully!")
