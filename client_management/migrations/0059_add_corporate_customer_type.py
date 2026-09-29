from django.db import migrations
from django.db.models import Max


def create_corporate_customer_type(apps, schema_editor):
    CustomerType = apps.get_model('client_management', 'CustomerType')
    if not CustomerType.objects.filter(name__iexact='Corporate').exists():
        max_val = CustomerType.objects.all().aggregate(Max('auto_id'))['auto_id__max']
        auto_id = (max_val or 0) + 1
        CustomerType.objects.create(
            name='Corporate',
            auto_id=auto_id,
            is_deleted=False
        )


def remove_corporate_customer_type(apps, schema_editor):
    CustomerType = apps.get_model('client_management', 'CustomerType')
    CustomerType.objects.filter(name__iexact='Corporate').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('client_management', '0058_remove_lead_vehicle_details_lead_vehicle_brand_model_and_more'),
    ]

    operations = [
        migrations.RunPython(create_corporate_customer_type, remove_corporate_customer_type),
    ]
