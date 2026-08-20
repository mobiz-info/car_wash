from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('client_management', '0049_merge_20260812_0102'),
    ]

    operations = [
        migrations.AddField(
            model_name='stock',
            name='brand',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
