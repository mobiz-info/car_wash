from django.db import migrations


def make_sports_bikes_global(apps, schema_editor):
    VehicleTypeModel = apps.get_model('master', 'VehicleTypeModel')
    VehicleType = apps.get_model('master', 'VehicleType')

    bikes_type = VehicleType.objects.filter(name__icontains='Bikes', is_deleted=False).first()

    sports_bikes = VehicleTypeModel.objects.filter(name__iexact='Sports Bikes').first()
    if not sports_bikes:
        sports_bikes = VehicleTypeModel.objects.filter(name__icontains='sport').first()

    if sports_bikes:
        sports_bikes.company = None
        sports_bikes.is_deleted = False
        sports_bikes.is_active = True
        if bikes_type and not sports_bikes.vehicle_type:
            sports_bikes.vehicle_type = bikes_type
        sports_bikes.save()
    elif bikes_type:
        VehicleTypeModel.objects.create(
            name='Sports Bikes',
            vehicle_type=bikes_type,
            company=None,
            is_active=True,
            is_deleted=False
        )


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0035_add_country_phone_flag_locale_fields'),
    ]

    operations = [
        migrations.RunPython(make_sports_bikes_global, migrations.RunPython.noop),
    ]
