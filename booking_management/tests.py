import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from service_management.models import JobCardCategory, JobCardService, JobCardIssue

from . import api_views


class JobCardIssueApiTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='job-issue-api-test')
        self.category = JobCardCategory.objects.create(name='Brakes', auto_id=1, creator=self.user)
        self.other_category = JobCardCategory.objects.create(name='Electrical', auto_id=2, creator=self.user)
        self.service = JobCardService.objects.create(category=self.category, name='Brake inspection', auto_id=1, creator=self.user)
        self.other_service = JobCardService.objects.create(category=self.other_category, name='Battery check', auto_id=2, creator=self.user)

    def _call_create(self, category, service, name):
        request = self.factory.post('/api/job-card-issues/create/', data=json.dumps({
            'category_id': str(category.id), 'service_id': str(service.id), 'name': name,
        }), content_type='application/json')
        with patch('booking_management.api_views.get_user_from_token', return_value=self.user), patch(
            'booking_management.api_views._job_pipeline_scope', return_value=(object(), None)
        ):
            return api_views.api_job_card_issue_create(request)

    def test_create_issue_under_service_and_reuse_case_insensitively(self):
        response = self._call_create(self.category, self.service, 'Brake noise')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload['created'])
        self.assertEqual(JobCardIssue.objects.filter(category=self.category, service=self.service).count(), 1)

        duplicate = self._call_create(self.category, self.service, 'brake NOISE')
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(json.loads(duplicate.content)['created'])
        self.assertEqual(JobCardIssue.objects.filter(category=self.category, service=self.service).count(), 1)

    def test_reject_service_from_another_category(self):
        response = self._call_create(self.category, self.other_service, 'Wrong pairing')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(JobCardIssue.objects.exists())
