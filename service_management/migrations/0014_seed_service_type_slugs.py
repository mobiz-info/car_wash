"""
Data migration: Seed slugs for the 4 service categories on ServiceType records.
Creates the 4 standard service types if they don't yet exist.
"""
from django.db import migrations


CATEGORIES = [
    ('Washing', 'washing'),
    ('Oil Change', 'oil_change'),
    ('Tyre Change', 'tyre_change'),
    ('Wheel Balancing & Alignment', 'wheel_alignment'),
]


def seed_service_type_slugs(apps, schema_editor):
    ServiceType = apps.get_model('service_management', 'ServiceType')
    import uuid

    for name, slug in CATEGORIES:
        # Try to match by slug first (idempotent), then by name
        obj = ServiceType.objects.filter(slug=slug).first()
        if not obj:
            obj = ServiceType.objects.filter(name__iexact=name).first()

        if obj:
            obj.slug = slug
            obj.save()
        else:
            # Create if missing — need auto_id
            max_id = ServiceType.objects.count()
            ServiceType.objects.create(
                id=uuid.uuid4(),
                auto_id=max_id + 1,
                name=name,
                slug=slug,
            )


def reverse_seed(apps, schema_editor):
    ServiceType = apps.get_model('service_management', 'ServiceType')
    for _, slug in CATEGORIES:
        ServiceType.objects.filter(slug=slug).update(slug=None)


class Migration(migrations.Migration):

    dependencies = [
        ('service_management', '0013_add_slug_branch_service_category'),
    ]

    operations = [
        migrations.RunPython(seed_service_type_slugs, reverse_code=reverse_seed),
    ]
