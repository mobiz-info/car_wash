from django.db import migrations

def seed_brand_models(apps, schema_editor):
    VehicleTypeModel = apps.get_model('master', 'VehicleTypeModel')
    VehicleBrandModel = apps.get_model('master', 'VehicleBrandModel')

    # Define segments and their corresponding models
    seed_dict = {
        'Hatchback': [
            'Maruti Swift', 'Hyundai i10', 'Maruti Baleno', 'Tata Altroz', 'Tata Tiago'
        ],
        'Premium Sedan': [
            'Honda City', 'Hyundai Verna', 'Maruti Ciaz', 'Volkswagen Virtus', 'Skoda Slavia'
        ],
        'Jeep': [
            'Mahindra Thar', 'Force Gurkha', 'Maruti Jimny'
        ],
        'Premium SUV': [
            'Maruti Brezza', 'Tata Nexon', 'Kia Sonet', 'Hyundai Venue', 'Toyota Fortuner', 
            'Tata Harrier', 'Mahindra XUV700', 'Hyundai Creta', 'Kia Seltos'
        ],
        'Premium Bikes': [
            'Royal Enfield Classic 350', 'KTM Duke 390', 'Yamaha R15', 'Honda Activa', 'TVS Jupiter'
        ],
        'Auto Riksha': [
            'Bajaj RE', 'Piaggio Ape'
        ]
    }

    start_id = 1
    for segment_name, models_list in seed_dict.items():
        segments = VehicleTypeModel.objects.filter(name__icontains=segment_name, is_deleted=False)
        for segment in segments:
            for name in models_list:
                VehicleBrandModel.objects.get_or_create(
                    vehicle_type_model=segment,
                    name=name,
                    defaults={'auto_id': start_id, 'is_active': True}
                )
                start_id += 1

class Migration(migrations.Migration):

    dependencies = [
        ('master', '0013_vehiclebrandmodel_delete_vehiclecompany'),
    ]

    operations = [
        migrations.RunPython(seed_brand_models),
    ]
