# Generated manually for additional vehicle customisation fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance_management', '0020_branchinvoicecustomisation'),
    ]

    operations = [
        migrations.AddField(
            model_name='branchinvoicecustomisation',
            name='show_vehicle_segment',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='branchinvoicecustomisation',
            name='show_vehicle_fuel_type',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='branchinvoicecustomisation',
            name='show_vehicle_wheel_type',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='branchinvoicecustomisation',
            name='show_vehicle_emission_std',
            field=models.BooleanField(default=True),
        ),
    ]
