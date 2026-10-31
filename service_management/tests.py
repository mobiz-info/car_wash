from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from service_management.models import JobCardCategory, JobCardService


class JobCardServicesByCategoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='jobcard-admin', email='jobcard@example.com', password='test-password'
        )
        self.client.force_login(self.user)
        self.category = JobCardCategory.objects.create(name='Oils', auto_id=1, creator=self.user)
        self.other_category = JobCardCategory.objects.create(name='Tyre', auto_id=2, creator=self.user)
        self.service = JobCardService.objects.create(
            category=self.category, name='Engine Oil Service', auto_id=1, creator=self.user
        )
        JobCardService.objects.create(
            category=self.other_category, name='Tyre Inspection', auto_id=2, creator=self.user
        )

    def test_returns_only_active_services_for_selected_category(self):
        response = self.client.get(reverse(
            'jobcard_services_by_category', kwargs={'category_id': self.category.id}
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['services'], [{'id': str(self.service.id), 'name': 'Engine Oil Service'}])

    def test_requires_superadmin(self):
        regular_user = get_user_model().objects.create_user(username='staff', password='test-password')
        self.client.force_login(regular_user)

        response = self.client.get(reverse(
            'jobcard_services_by_category', kwargs={'category_id': self.category.id}
        ))

        self.assertEqual(response.status_code, 403)
