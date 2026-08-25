from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Counter, QueueEvent, Service, Token
from .services import call_next_token, create_token


User = get_user_model()


class QueueWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student", password="testpass123")
        self.staff = User.objects.create_user(username="staff", password="testpass123", role=User.Role.STAFF)
        self.service = Service.objects.create(name="Admissions")
        self.counter = Counter.objects.create(name="Counter 1", service=self.service, staff=self.staff)

    def test_user_can_create_token(self):
        token = create_token(self.user, self.service)

        self.assertEqual(token.status, Token.Status.WAITING)
        self.assertTrue(token.token_number.startswith("Q"))
        self.assertEqual(QueueEvent.objects.filter(token=token, action=QueueEvent.Action.CREATED).count(), 1)

    def test_staff_can_call_next_token(self):
        token = create_token(self.user, self.service)

        called = call_next_token(self.staff, self.counter)

        token.refresh_from_db()
        self.assertEqual(called, token)
        self.assertEqual(token.status, Token.Status.SERVING)
        self.assertEqual(token.counter, self.counter)
        self.assertIsNotNone(token.called_at)

    def test_staff_dashboard_requires_staff_role(self):
        self.client.login(username="student", password="testpass123")

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 302)

    def test_history_filter_requires_staff_role(self):
        self.client.login(username="student", password="testpass123")

        response = self.client.get(reverse("queue_history"))

        self.assertEqual(response.status_code, 302)
