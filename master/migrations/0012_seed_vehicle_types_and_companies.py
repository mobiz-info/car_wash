from django.db import migrations

def seed_types_and_companies(apps, schema_editor):
    VehicleType = apps.get_model('master', 'VehicleType')
    VehicleCompany = apps.get_model('master', 'VehicleCompany')
    
    car_type = VehicleType.objects.filter(name__icontains='Car').first()
    bike_type = VehicleType.objects.filter(name__icontains='Bike').first()
    rickshaw_type = VehicleType.objects.filter(name__icontains='Auto').first()
    bus_type = VehicleType.objects.filter(name__icontains='Bus').first()
    tempo_type = VehicleType.objects.filter(name__icontains='Tempo').first()
    heavy_type = VehicleType.objects.filter(name__icontains='Heavy').first()
    
    # 1. Car companies
    car_companies = [
        'Toyota', 'Hyundai', 'Honda', 'Ford', 'Chevrolet', 
        'Nissan', 'Volkswagen', 'BMW', 'Mercedes-Benz', 'Tesla'
    ]
    for i, name in enumerate(car_companies, start=1):
        comp, _ = VehicleCompany.objects.get_or_create(name=name, defaults={'auto_id': i})
        if car_type:
            comp.vehicle_types.add(car_type)

    # 2. Bike companies
    bike_companies = [
        'Yamaha', 'Royal Enfield', 'Hero', 'Honda', 'Bajaj', 
        'TVS', 'Suzuki', 'Vespa', 'KTM'
    ]
    for i, name in enumerate(bike_companies, start=20):
        comp, _ = VehicleCompany.objects.get_or_create(name=name, defaults={'auto_id': i})
        if bike_type:
            comp.vehicle_types.add(bike_type)

    # 3. Rickshaw companies
    rickshaw_companies = [
        'Bajaj', 'Piaggio', 'Mahindra', 'TVS'
    ]
    for i, name in enumerate(rickshaw_companies, start=40):
        comp, _ = VehicleCompany.objects.get_or_create(name=name, defaults={'auto_id': i})
        if rickshaw_type:
            comp.vehicle_types.add(rickshaw_type)

    # 4. Bus/Lorry & Tempo companies
    bus_companies = [
        'Tata', 'Ashok Leyland', 'Volvo', 'Scania', 'Isuzu', 'Mahindra', 'BharatBenz', 'Eicher'
    ]
    for i, name in enumerate(bus_companies, start=60):
        comp, _ = VehicleCompany.objects.get_or_create(name=name, defaults={'auto_id': i})
        if bus_type:
            comp.vehicle_types.add(bus_type)
        if tempo_type:
            comp.vehicle_types.add(tempo_type)

    # 5. Heavy Duty Equipment companies
    heavy_companies = [
        'Caterpillar', 'JCB', 'Komatsu', 'Volvo', 'Hitachi'
    ]
    for i, name in enumerate(heavy_companies, start=80):
        comp, _ = VehicleCompany.objects.get_or_create(name=name, defaults={'auto_id': i})
        if heavy_type:
            comp.vehicle_types.add(heavy_type)

class Migration(migrations.Migration):

    dependencies = [
        ('master', '0011_vehiclecompany_vehicle_types'),
    ]

    operations = [
        migrations.RunPython(seed_types_and_companies),
    ]
