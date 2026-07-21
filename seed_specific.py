import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')
sys.path.append('/Users/muhammedanshid/Desktop/Mobiz Car Wash/Mobiz Carwash Admin')
if sys.platform == 'darwin':
    os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = '/opt/homebrew/lib:' + os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')

django.setup()

from service_management.models import ServiceType, Service, BranchService, BranchServiceCategory, ServiceVehicleTypePrice
from client_management.models import Branch
from master.models import VehicleTypeModel, OilProduct, TyreBrand, OilStock
from core.functions import get_auto_id

branches = list(Branch.objects.filter(is_deleted=False))
print(f"Seeding for {len(branches)} branches...")

types_mapping = {
    'Washing': 'washing',
    'Oil Change': 'oil_change',
    'Tyre Change': 'tyre_change',
    'Wheel Balancing & Alignment': 'wheel_alignment'
}

# Ensure categories exist
for name, slug in types_mapping.items():
    st, _ = ServiceType.objects.get_or_create(name=name)
    st.slug = slug
    st.save()

# Ensure global services exist
global_services = []
services_to_create = [
    {'name': 'Premium Oil Change', 'type_slug': 'oil_change'},
    {'name': 'Tyre Replacement Service', 'type_slug': 'tyre_change'},
    {'name': 'Wheel Alignment & Balancing', 'type_slug': 'wheel_alignment'},
]

next_service_id = get_auto_id(Service)
for s_data in services_to_create:
    st = ServiceType.objects.filter(slug=s_data['type_slug']).first()
    svc, created = Service.objects.get_or_create(
        name=s_data['name'],
        defaults={
            'service_type': st,
            'description': f"Default {s_data['name']} service.",
            'auto_id': next_service_id
        }
    )
    if created:
        next_service_id += 1
    global_services.append(svc)

vehicle_models = list(VehicleTypeModel.objects.filter(is_deleted=False))

# Pre-fetch current max IDs
next_bsc_id = get_auto_id(BranchServiceCategory)
next_bs_id = get_auto_id(BranchService)
next_svtp_id = get_auto_id(ServiceVehicleTypePrice)
next_op_id = get_auto_id(OilProduct)
next_tb_id = get_auto_id(TyreBrand)
next_stock_id = get_auto_id(OilStock)

for branch in branches:
    client = branch.company
    print(f"Branch: {branch.name} (Company: {client.company_name})")
    
    # 1. Enable categories for branch
    for slug in types_mapping.values():
        st = ServiceType.objects.filter(slug=slug).first()
        if st:
            bsc, created = BranchServiceCategory.objects.get_or_create(
                branch=branch,
                service_type=st,
                defaults={
                    'is_enabled': True,
                    'auto_id': next_bsc_id
                }
            )
            if created:
                next_bsc_id += 1
            elif not bsc.is_enabled:
                bsc.is_enabled = True
                bsc.save()
    
    # 2. Ensure oil products & tyre brands exist for company
    oil_items = [
        {'brand': 'Castrol', 'name': 'GTX Premium', 'grade': '5W-30'},
        {'brand': 'Mobil 1', 'name': 'Super Synthetic', 'grade': '0W-20'},
    ]
    for item in oil_items:
        op, created = OilProduct.objects.get_or_create(
            company=client,
            brand=item['brand'],
            name=item['name'],
            grade=item['grade'],
            defaults={'auto_id': next_op_id}
        )
        if created:
            next_op_id += 1
        
    tyre_items = ['MRF', 'Bridgestone', 'Michelin']
    for brand in tyre_items:
        tb, created = TyreBrand.objects.get_or_create(
            company=client,
            brand=brand,
            defaults={'auto_id': next_tb_id}
        )
        if created:
            next_tb_id += 1

    # 3. Enable services and assign prices
    for svc in global_services:
        bs, created = BranchService.objects.get_or_create(
            branch=branch,
            service=svc,
            defaults={
                'is_enabled': True,
                'auto_id': next_bs_id
            }
        )
        if created:
            next_bs_id += 1
        elif not bs.is_enabled:
            bs.is_enabled = True
            bs.save()

        # Seed prices
        for vm in vehicle_models:
            svtp, created = ServiceVehicleTypePrice.objects.get_or_create(
                branch=branch,
                service=svc,
                vehicle_model=vm,
                defaults={
                    'price': 450.00,
                    'is_active': True,
                    'auto_id': next_svtp_id
                }
            )
            if created:
                next_svtp_id += 1
            elif not svtp.is_active:
                svtp.is_active = True
                svtp.save()

    # 4. Stock
    for op in OilProduct.objects.filter(company=client):
        stock, created = OilStock.objects.get_or_create(
            branch=branch,
            oil_product=op,
            defaults={
                'quantity_litres': 100.00,
                'low_stock_alert_litres': 15.00,
                'auto_id': next_stock_id
            }
        )
        if created:
            next_stock_id += 1

print("SUCCESS")
