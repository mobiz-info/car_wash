from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance_management', '0014_invoice_show_warranty_in_pdf_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceservicedetail',
            name='insurance_expiry_date',
            field=models.DateField(
                blank=True,
                help_text='Customer-selected insurance policy expiry date',
                null=True,
            ),
        ),
    ]
