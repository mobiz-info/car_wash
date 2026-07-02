from django.db import migrations

def seed_data(apps, schema_editor):
    VehicleColor = apps.get_model('master', 'VehicleColor')
    VehicleCompany = apps.get_model('master', 'VehicleCompany')
    
    # 8 famous colors
    colors = [
        'White',
        'Black',
        'Silver',
        'Grey',
        'Red',
        'Blue',
        'Green',
        'Gold'
    ]
    for i, c in enumerate(colors, start=1):
        VehicleColor.objects.get_or_create(name=c, defaults={'auto_id': i})
        
    # Famous vehicle companies
    companies = [
        'Toyota',
        'Hyundai',
        'Honda',
        'Ford',
        'Chevrolet',
        'Nissan',
        'Volkswagen',
        'BMW',
        'Mercedes-Benz',
        'Tesla'
    ]
    for i, comp in enumerate(companies, start=1):
        VehicleCompany.objects.get_or_create(name=comp, defaults={'auto_id': i})

class Migration(migrations.Migration):

    dependencies = [
        ('master', '0009_vehiclecompany_vehiclecolor'),
    ]

    operations = [
        migrations.RunPython(seed_data),
    ]
