from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance_management', '0015_invoiceservicedetail_insurance_expiry_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoiceservicedetail',
            name='service_category',
            field=models.CharField(
                choices=[
                    ('washing', 'Washing'),
                    ('oil_change', 'Oil Change'),
                    ('tyre_change', 'Tyre Change'),
                    ('wheel_alignment', 'Wheel Alignment'),
                    ('smoke_test', 'Smoke Test'),
                    ('car_detailing', 'Car Detailing'),
                    ('auto_insurance', 'Auto Insurance'),
                ],
                max_length=30,
            ),
        ),
    ]
