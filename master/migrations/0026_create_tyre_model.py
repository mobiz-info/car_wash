from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('client_management', '0042_stock_quantity'),
        ('master', '0023_oilproduct_for_diesel_oilproduct_for_petrol_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tyre',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('auto_id', models.PositiveIntegerField(db_index=True, unique=True)),
                ('date_added', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('date_updated', models.DateTimeField(auto_now_add=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('name', models.CharField(help_text='Tyre model / name e.g. ZLX, Earth-1, Turanza', max_length=150)),
                ('size', models.CharField(help_text='Tyre size e.g. 185/65 R15, 195/55 R16', max_length=100)),
                ('price', models.DecimalField(decimal_places=2, default=0.0, help_text='Price per tyre', max_digits=10)),
                ('stock_qty', models.IntegerField(default=0, help_text='Available stock quantity in units')),
                ('running_km', models.PositiveIntegerField(default=40000, help_text='Recommended running KM / Lifespan for this tyre e.g. 40000')),
                ('pattern_type', models.CharField(blank=True, help_text='Pattern type e.g. Tubeless, Radial, All-Terrain', max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('company', models.ForeignKey(blank=True, help_text='Leave blank for global master', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tyres', to='client_management.client')),
                ('creator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='creator_%(class)s_objects', to='auth.user')),
                ('tyre_brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tyres', to='master.tyrebrand')),
                ('updater', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='updater_%(class)s_objects', to='auth.user')),
            ],
            options={
                'ordering': ['tyre_brand__brand', 'name', 'size'],
            },
        ),
    ]
