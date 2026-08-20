from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('master', '0030_merge_20260812_0102'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='supplier_type',
            field=models.CharField(choices=[('cash', 'Cash'), ('credit', 'Credit'), ('bill_to_bill', 'Bill to Bill')], default='cash', max_length=20),
        ),
        migrations.AddField(
            model_name='supplier',
            name='credit_limit',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=12),
        ),
        migrations.AddField(
            model_name='supplier',
            name='no_of_invoices',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
