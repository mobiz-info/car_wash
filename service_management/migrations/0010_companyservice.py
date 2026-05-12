from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('client_management', '0002_initial'),
        ('service_management', '0009_remove_service_duration'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyService',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('auto_id', models.PositiveIntegerField(db_index=True, unique=True)),
                ('is_enabled', models.BooleanField(default=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_services', to='client_management.client')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_service_entries', to='service_management.servicetype')),
                ('creator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_%(class)s_set', to='auth.user')),
                ('updater', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_%(class)s_set', to='auth.user')),
            ],
            options={
                'unique_together': {('company', 'service')},
            },
        ),
    ]
