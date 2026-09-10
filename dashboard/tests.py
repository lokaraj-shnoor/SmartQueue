"""End-to-end coverage for the pieces built in this phase:
the landing page, sign-up / sign-in / sign-out, role routing, and the
administrator's control over services, counters and queue status.
"""
import base64
import json
import os
import time
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.forms import StaffAccountForm
from accounts.models import Role, User
from queues import reports, services as queue_ops
from queues.models import (
    Counter,
    CounterSession,
    CounterStatus,
    EntryStatus,
    EventType,
    QueueEntry,
    Service,
    SystemSettings,
    Token,
)


class LandingTests(TestCase):
    def test_landing_is_public(self):
        Service.objects.create(name="Fee payment", code="FEE")
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fee payment")

    def test_landing_shows_the_next_token_number(self):
        Service.objects.create(name="Fee payment", code="FEE")
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "FEE-001")


class AuthTests(TestCase):
    def test_signup_creates_a_visitor_and_signs_them_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Ansari",
                "username": "ansari",
                "email": "ansari@example.edu",
                "phone": "",
                "password1": "counter-queue-42",
                "password2": "counter-queue-42",
            },
        )
        self.assertRedirects(response, reverse("dashboard:home"), target_status_code=302)
        user = User.objects.get(username="ansari")
        self.assertEqual(user.role, Role.VISITOR)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_signup_rejects_a_duplicate_email(self):
        User.objects.create_user("first", email="nadia@example.edu", password="x")
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Nadia",
                "username": "ansari",
                "email": "nadia@example.edu",
                "password1": "counter-queue-42",
                "password2": "counter-queue-42",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account already uses this email.")

    def test_login_then_logout(self):
        User.objects.create_user("ansari", password="counter-queue-42")
        signed_in = self.client.post(
            reverse("accounts:login"), {"username": "ansari", "password": "counter-queue-42"}
        )
        self.assertRedirects(signed_in, reverse("dashboard:home"), target_status_code=302)

        signed_out = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(signed_out, reverse("core:landing"))

    def test_dashboard_requires_a_session(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)


class RoleRoutingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("rhea", password="pw", role=Role.ADMIN)
        self.staff = User.objects.create_user("dev", password="pw", role=Role.STAFF)
        self.visitor = User.objects.create_user("nadia", password="pw", role=Role.VISITOR)

    def test_each_role_lands_on_its_own_dashboard(self):
        for user, target in [
            (self.admin, "dashboard:admin_home"),
            (self.staff, "dashboard:staff_home"),
            (self.visitor, "dashboard:visitor_home"),
        ]:
            self.client.force_login(user)
            response = self.client.get(reverse("dashboard:home"))
            self.assertRedirects(response, reverse(target))

    def test_visitor_cannot_open_the_admin_dashboard(self):
        self.client.force_login(self.visitor)
        response = self.client.get(reverse("dashboard:admin_home"))
        self.assertRedirects(response, reverse("dashboard:home"), target_status_code=302)

    def test_staff_cannot_open_the_admin_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:counter_list"))
        self.assertRedirects(response, reverse("dashboard:home"), target_status_code=302)

    def test_admin_role_gets_django_admin_access(self):
        self.assertTrue(self.admin.is_staff)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("rhea", password="pw", role=Role.ADMIN)
        self.client.force_login(self.admin)

    def test_overview_renders(self):
        response = self.client.get(reverse("dashboard:admin_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today at the counters")

    def test_create_a_service(self):
        response = self.client.post(
            reverse("dashboard:service_list"),
            {
                "name": "Fee payment",
                "code": "fee",
                "description": "Pay semester fees.",
                "avg_service_minutes": 6,
                "daily_token_limit": 0,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:service_list"))
        service = Service.objects.get(name="Fee payment")
        self.assertEqual(service.code, "FEE")
        self.assertEqual(service.slug, "fee-payment")

    def test_pause_and_resume_a_service(self):
        service = Service.objects.create(name="Fee payment", code="FEE")
        self.client.post(reverse("dashboard:service_toggle", args=[service.pk]))
        service.refresh_from_db()
        self.assertFalse(service.is_active)

        self.client.post(reverse("dashboard:service_toggle", args=[service.pk]))
        service.refresh_from_db()
        self.assertTrue(service.is_active)

    def test_a_service_with_tokens_is_not_deleted(self):
        service = Service.objects.create(name="Fee payment", code="FEE")
        Token.objects.create(service=service, number=1)
        self.client.post(reverse("dashboard:service_delete", args=[service.pk]))
        self.assertTrue(Service.objects.filter(pk=service.pk).exists())

    def test_create_a_counter_and_change_its_status(self):
        service = Service.objects.create(name="Fee payment", code="FEE")
        response = self.client.post(
            reverse("dashboard:counter_list"),
            {
                "name": "Accounts",
                "code": "c1",
                "location": "Ground floor",
                "services": [service.pk],
                "assigned_staff": "",
                "status": CounterStatus.CLOSED,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:counter_list"))
        counter = Counter.objects.get(code="C1")
        self.assertEqual(list(counter.services.all()), [service])

        self.client.post(
            reverse("dashboard:counter_status", args=[counter.pk]),
            {"status": CounterStatus.OPEN},
        )
        counter.refresh_from_db()
        self.assertEqual(counter.status, CounterStatus.OPEN)

    def test_counter_status_rejects_an_unknown_value(self):
        counter = Counter.objects.create(name="Desk", code="C1")
        self.client.post(
            reverse("dashboard:counter_status", args=[counter.pk]), {"status": "napping"}
        )
        counter.refresh_from_db()
        self.assertEqual(counter.status, CounterStatus.CLOSED)

    def test_pause_token_issuing_site_wide(self):
        response = self.client.post(
            reverse("dashboard:queue_settings"),
            {"announcement": "Counters close at 4:30 pm today."},
        )
        self.assertEqual(response.status_code, 302)
        row = SystemSettings.load()
        self.assertFalse(row.accepting_tokens)
        self.assertEqual(row.updated_by, self.admin)

    def test_create_a_staff_account(self):
        response = self.client.post(
            reverse("dashboard:team_list"),
            {
                "first_name": "Dev",
                "username": "dpatel",
                "email": "dev@example.edu",
                "phone": "",
                "department": "Accounts office",
                "role": Role.STAFF,
                "password1": "counter-queue-42",
            },
        )
        self.assertRedirects(response, reverse("dashboard:team_list"))
        staff = User.objects.get(username="dpatel")
        self.assertEqual(staff.role, Role.STAFF)
        self.assertTrue(staff.check_password("counter-queue-42"))

    def test_cannot_deactivate_your_own_account(self):
        self.client.post(reverse("dashboard:team_toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class TokenNumberingTests(TestCase):
    def test_numbers_restart_per_service_each_day(self):
        fee = Service.objects.create(name="Fee payment", code="FEE")
        lab = Service.objects.create(name="Lab sample", code="LAB")

        self.assertEqual(fee.next_token_number(), 1)
        Token.objects.create(service=fee, number=fee.next_token_number())
        self.assertEqual(fee.next_token_number(), 2)
        self.assertEqual(lab.next_token_number(), 1)

        token = Token.objects.create(service=lab, number=1)
        self.assertEqual(token.code, "LAB-001")


class VisitorTokenTests(TestCase):
    """Taking a token, seeing the place in line, and giving it up again."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )
        self.client.force_login(self.visitor)

    def _take(self, service=None):
        return self.client.post(
            reverse("dashboard:token_take", args=[(service or self.service).pk]), follow=True
        )

    def test_taking_a_token_issues_the_next_number_and_queues_it(self):
        response = self._take()
        self.assertContains(response, "FEE-001")
        entry = QueueEntry.objects.get()
        self.assertEqual(entry.status, EntryStatus.WAITING)
        self.assertEqual(entry.token.issued_to, self.visitor)
        self.assertEqual(entry.events.get().event, EventType.ISSUED)

    def test_one_open_token_per_service(self):
        self._take()
        self._take()
        self.assertEqual(Token.objects.count(), 1)

    def test_paused_system_refuses_new_tokens(self):
        settings_row = SystemSettings.load()
        settings_row.accepting_tokens = False
        settings_row.save()
        self._take()
        self.assertEqual(Token.objects.count(), 0)

    def test_daily_limit_stops_issuing(self):
        self.service.daily_token_limit = 1
        self.service.save()
        self._take()
        other = User.objects.create_user(
            username="sam", password="counter-queue-42", role=Role.VISITOR
        )
        self.client.force_login(other)
        self._take()
        self.assertEqual(Token.objects.count(), 1)

    def test_place_in_line_counts_only_the_people_ahead(self):
        first = queue_ops.issue_token(self.service, user=self.visitor)
        behind = User.objects.create_user(
            username="dev", password="counter-queue-42", role=Role.VISITOR
        )
        second = queue_ops.issue_token(self.service, user=behind)
        self.assertEqual(queue_ops.people_ahead(first), 0)
        self.assertEqual(queue_ops.people_ahead(second), 1)

    def test_cancelling_frees_the_visitor_to_take_another(self):
        self._take()
        entry = QueueEntry.objects.get()
        self.client.post(reverse("dashboard:token_cancel", args=[entry.pk]), follow=True)
        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.CANCELLED)
        self._take()
        self.assertEqual(Token.objects.count(), 2)

    def test_a_token_is_not_readable_by_another_visitor(self):
        entry = queue_ops.issue_token(self.service, user=self.visitor)
        intruder = User.objects.create_user(
            username="nosy", password="counter-queue-42", role=Role.VISITOR
        )
        self.client.force_login(intruder)
        response = self.client.get(reverse("dashboard:token_detail", args=[entry.pk]))
        self.assertRedirects(response, reverse("dashboard:visitor_home"))


class StaffCallingTests(TestCase):
    """Calling people forward, serving them, and skipping no-shows."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.staff = User.objects.create_user(
            username="meera", password="counter-queue-42", role=Role.STAFF
        )
        self.counter = Counter.objects.create(
            name="Front desk", code="C1", status=CounterStatus.OPEN, assigned_staff=self.staff
        )
        self.counter.services.add(self.service)
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )
        self.entry = queue_ops.issue_token(self.service, user=self.visitor)
        self.client.force_login(self.staff)

    def _post(self, name, pk):
        return self.client.post(reverse(name, args=[pk]), follow=True)

    def test_call_next_puts_the_first_token_on_the_counter(self):
        self._post("dashboard:call_next", self.counter.pk)
        self.entry.refresh_from_db()
        self.counter.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.CALLED)
        self.assertEqual(self.entry.counter, self.counter)
        self.assertEqual(self.counter.now_serving, self.entry)
        self.assertIsNotNone(self.entry.wait_seconds)

    def test_priority_is_called_before_an_earlier_token(self):
        other = User.objects.create_user(
            username="sam", password="counter-queue-42", role=Role.VISITOR
        )
        urgent = queue_ops.issue_token(self.service, user=other, priority=5)
        self._post("dashboard:call_next", self.counter.pk)
        urgent.refresh_from_db()
        self.assertEqual(urgent.status, EntryStatus.CALLED)

    def test_a_closed_counter_cannot_call(self):
        self.counter.status = CounterStatus.CLOSED
        self.counter.save()
        self._post("dashboard:call_next", self.counter.pk)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.WAITING)

    def test_cannot_call_while_someone_is_still_at_the_desk(self):
        other = User.objects.create_user(
            username="sam", password="counter-queue-42", role=Role.VISITOR
        )
        queue_ops.issue_token(self.service, user=other)
        self._post("dashboard:call_next", self.counter.pk)
        self._post("dashboard:call_next", self.counter.pk)
        self.assertEqual(QueueEntry.objects.filter(status=EntryStatus.CALLED).count(), 1)

    def test_serving_then_finishing_frees_the_counter_and_times_it(self):
        queue_ops.call_next(self.counter, self.staff)
        self._post("dashboard:entry_start", self.entry.pk)
        self._post("dashboard:entry_finish", self.entry.pk)
        self.entry.refresh_from_db()
        self.counter.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.SERVED)
        self.assertEqual(self.entry.served_by, self.staff)
        self.assertIsNotNone(self.entry.service_seconds)
        self.assertIsNone(self.counter.now_serving)

    def test_finishing_counts_towards_the_open_shift(self):
        queue_ops.set_counter_status(self.counter, CounterStatus.OPEN, self.staff)
        self.counter.status = CounterStatus.OPEN
        self.counter.save()
        queue_ops.call_next(self.counter, self.staff)
        self.entry.refresh_from_db()
        queue_ops.finish_serving(self.entry, self.staff)
        session = CounterSession.objects.get(counter=self.counter, staff=self.staff)
        self.assertEqual(session.tokens_served, 1)

    def test_a_no_show_is_skipped_and_can_go_back_in_line(self):
        queue_ops.call_next(self.counter, self.staff)
        self._post("dashboard:entry_skip", self.entry.pk)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.SKIPPED)

        self._post("dashboard:entry_requeue", self.entry.pk)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.WAITING)
        self.assertEqual(self.entry.priority, 1)

    def test_the_trail_records_every_step(self):
        queue_ops.call_next(self.counter, self.staff)
        self.entry.refresh_from_db()
        queue_ops.start_serving(self.entry, self.staff)
        queue_ops.finish_serving(self.entry, self.staff)
        events = list(self.entry.events.order_by("at").values_list("event", flat=True))
        self.assertEqual(
            events,
            [EventType.ISSUED, EventType.CALLED, EventType.STARTED, EventType.SERVED],
        )

    def test_staff_cannot_touch_another_counters_token(self):
        queue_ops.call_next(self.counter, self.staff)
        intruder = User.objects.create_user(
            username="raj", password="counter-queue-42", role=Role.STAFF
        )
        self.client.force_login(intruder)
        response = self.client.post(reverse("dashboard:entry_finish", args=[self.entry.pk]))
        self.assertEqual(response.status_code, 404)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.CALLED)

    def test_a_visitor_cannot_reach_the_call_desk(self):
        self.client.force_login(self.visitor)
        response = self.client.post(reverse("dashboard:call_next", args=[self.counter.pk]))
        self.assertEqual(response.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.WAITING)

    def test_console_shows_the_line_and_the_called_number(self):
        queue_ops.call_next(self.counter, self.staff)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:staff_home"))
        self.assertContains(response, "FEE-001")
        self.assertContains(response, "Front desk")


class LiveBoardTests(TestCase):
    """The wall display: public, current, and honest about closed desks."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.staff = User.objects.create_user(
            username="meera", password="counter-queue-42", role=Role.STAFF
        )
        self.counter = Counter.objects.create(
            name="Front desk", code="C1", status=CounterStatus.OPEN, assigned_staff=self.staff
        )
        self.counter.services.add(self.service)
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )

    def test_board_is_public(self):
        response = self.client.get(reverse("core:board"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C1")

    def test_board_shows_the_number_a_counter_is_serving(self):
        queue_ops.issue_token(self.service, user=self.visitor)
        queue_ops.call_next(self.counter, self.staff)
        response = self.client.get(reverse("core:board"))
        self.assertContains(response, "FEE-001")
        self.assertContains(response, "Now serving")

    def test_closed_counters_stay_off_the_board(self):
        self.counter.status = CounterStatus.CLOSED
        self.counter.save()
        response = self.client.get(reverse("core:board"))
        self.assertNotContains(response, "Front desk")
        self.assertContains(response, "No counters are open.")

    def test_paused_counters_are_shown_as_paused(self):
        self.counter.status = CounterStatus.PAUSED
        self.counter.save()
        response = self.client.get(reverse("core:board"))
        self.assertContains(response, "Paused")

    def test_recently_called_lists_the_last_numbers(self):
        queue_ops.issue_token(self.service, user=self.visitor)
        entry = queue_ops.call_next(self.counter, self.staff)
        queue_ops.finish_serving(entry, self.staff)
        other = User.objects.create_user(
            username="sam", password="counter-queue-42", role=Role.VISITOR
        )
        queue_ops.issue_token(self.service, user=other)
        self.counter.refresh_from_db()
        queue_ops.call_next(self.counter, self.staff)

        codes = [
            item.token.code for item in queue_ops.recently_called()
        ]
        self.assertEqual(codes, ["FEE-002", "FEE-001"])

    def test_waiting_counts_appear_per_service(self):
        queue_ops.issue_token(self.service, user=self.visitor)
        response = self.client.get(reverse("core:board"))
        self.assertContains(response, "Fee payment")
        self.assertContains(response, "Waiting")

    def test_the_announcement_reaches_the_board(self):
        row = SystemSettings.load()
        row.announcement = "Counters close at 4:30 pm today"
        row.save()
        response = self.client.get(reverse("core:board"))
        self.assertContains(response, "Counters close at 4:30 pm today")


class StaleTokenTests(TestCase):
    """A number left on a counter overnight must not hold up today's queue."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.staff = User.objects.create_user(
            username="meera", password="counter-queue-42", role=Role.STAFF
        )
        self.counter = Counter.objects.create(
            name="Front desk", code="C1", status=CounterStatus.OPEN, assigned_staff=self.staff
        )
        self.counter.services.add(self.service)
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )

    def _leftover(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        token = Token.objects.create(
            service=self.service, number=99, issue_date=yesterday, issued_to=self.visitor
        )
        entry = QueueEntry.objects.create(token=token, counter=self.counter, status=EntryStatus.CALLED)
        self.counter.now_serving = entry
        self.counter.save()
        return entry

    def test_the_board_ignores_yesterdays_number(self):
        self._leftover()
        response = self.client.get(reverse("core:board"))
        self.assertNotContains(response, "FEE-099")
        self.assertContains(response, "Free")

    def test_calling_next_clears_the_leftover_and_moves_on(self):
        leftover = self._leftover()
        queue_ops.issue_token(self.service, user=self.visitor)
        called = queue_ops.call_next(self.counter, self.staff)
        leftover.refresh_from_db()
        self.assertEqual(leftover.status, EntryStatus.SKIPPED)
        self.assertEqual(called.token.code, "FEE-001")


class HistoryReportTests(TestCase):
    """Wait times, throughput and the trail, for one day at a time."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.admin = User.objects.create_user(
            username="asha", password="counter-queue-42", role=Role.ADMIN
        )
        self.staff = User.objects.create_user(
            username="meera", password="counter-queue-42", role=Role.STAFF
        )
        self.counter = Counter.objects.create(
            name="Front desk", code="C1", status=CounterStatus.OPEN, assigned_staff=self.staff
        )
        self.counter.services.add(self.service)
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )
        self.client.force_login(self.admin)

    def _served_entry(self, wait=300, service_time=120):
        entry = queue_ops.issue_token(self.service, user=self.visitor)
        queue_ops.call_next(self.counter, self.staff)
        entry.refresh_from_db()
        queue_ops.finish_serving(entry, self.staff)
        # The clocks in a test run are all inside one second, so the stored
        # figures are set directly to the durations under test.
        QueueEntry.objects.filter(pk=entry.pk).update(
            wait_seconds=wait, service_seconds=service_time
        )
        self.counter.refresh_from_db()
        return entry

    def test_summary_averages_the_stored_wait_and_service_times(self):
        self._served_entry(wait=300, service_time=120)
        self._served_entry(wait=900, service_time=240)
        summary = reports.day_summary(timezone.localdate())
        self.assertEqual(summary["issued"], 2)
        self.assertEqual(summary["served"], 2)
        self.assertEqual(summary["avg_wait_minutes"], 10)
        self.assertEqual(summary["avg_service_minutes"], 3)
        self.assertEqual(summary["longest_wait_minutes"], 15)

    def test_a_day_with_nothing_on_it_reports_blanks_not_zeroes(self):
        summary = reports.day_summary(timezone.localdate() - timedelta(days=3))
        self.assertEqual(summary["issued"], 0)
        self.assertIsNone(summary["avg_wait_minutes"])

    def test_service_and_counter_breakdowns_count_the_same_work(self):
        self._served_entry()
        services = reports.service_breakdown(timezone.localdate())
        counters = reports.counter_breakdown(timezone.localdate())
        self.assertEqual(services[0].served, 1)
        self.assertEqual(counters[0].served, 1)
        self.assertEqual(counters[0].code, "C1")

    def test_the_trend_covers_the_whole_week_including_empty_days(self):
        self._served_entry()
        trend = reports.daily_trend(days=7)
        self.assertEqual(len(trend), 7)
        self.assertEqual(trend[-1]["day"], timezone.localdate())
        self.assertEqual(trend[-1]["issued"], 1)
        self.assertEqual(trend[0]["issued"], 0)

    def test_the_page_renders_for_a_chosen_day(self):
        self._served_entry()
        response = self.client.get(reverse("dashboard:history"))
        self.assertContains(response, "Average wait")
        self.assertContains(response, "FEE-001")

        older = (timezone.localdate() - timedelta(days=2)).isoformat()
        response = self.client.get(reverse("dashboard:history"), {"day": older})
        self.assertContains(response, "No tokens were issued on this day.")

    def test_an_unreadable_day_falls_back_to_today(self):
        response = self.client.get(reverse("dashboard:history"), {"day": "not-a-date"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today")

    def test_only_administrators_can_read_the_report(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:history"))
        self.assertEqual(response.status_code, 302)


class PasswordResetTests(TestCase):
    """The forgotten-password door: a real email with a link that works once."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="riya",
            email="riya@example.edu",
            password="counter-queue-42",
            role=Role.VISITOR,
        )

    def test_asking_for_a_reset_sends_a_link(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "riya@example.edu"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["riya@example.edu"])
        self.assertIn("Smart Queue", sent.subject)
        self.assertIn("/accounts/password/reset/", sent.body)

    def test_an_unknown_address_says_the_same_thing_and_sends_nothing(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "nobody@example.edu"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_the_emailed_link_sets_a_new_password(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "riya@example.edu"})
        link = [
            line for line in mail.outbox[0].body.splitlines() if "/accounts/password/reset/" in line
        ][0].strip()
        path = link.split("://", 1)[1].split("/", 1)[1]

        # Django swaps the token for a session-held one on the first visit.
        response = self.client.get("/" + path, follow=True)
        self.assertContains(response, "Set a new password")

        response = self.client.post(
            response.request["PATH_INFO"],
            {"new_password1": "queue-counter-77", "new_password2": "queue-counter-77"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("queue-counter-77"))

    def test_the_sign_in_page_offers_the_reset(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:password_reset"))


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="test-client-id", GOOGLE_OAUTH_CLIENT_SECRET="test-secret"
)
class GoogleSignInTests(TestCase):
    """Sign in with Google, from the button to the account it lands on."""

    def _id_token(self, email="riya@example.edu", name="Riya Sharma", verified=True, aud=None):
        claims = {
            "aud": aud or "test-client-id",
            "iss": "https://accounts.google.com",
            "exp": int(time.time()) + 600,
            "email": email,
            "email_verified": verified,
            "name": name,
            "sub": "google-123",
        }
        body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        return "header." + body + ".signature"

    def _callback(self, id_token=None, tamper_state=False):
        """Walk the real flow: start it, then answer as Google would."""
        start = self.client.get(reverse("accounts:google_start"))
        state = self.client.session["google_oauth_state"]

        with mock.patch("accounts.oauth.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "id_token": id_token if id_token is not None else self._id_token()
            }
            return start, self.client.get(
                reverse("accounts:google_callback"),
                {"code": "auth-code", "state": "wrong" if tamper_state else state},
                follow=True,
            )

    def test_the_button_only_shows_when_google_is_configured(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "Continue with Google")

        with self.settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_OAUTH_CLIENT_SECRET=""):
            response = self.client.get(reverse("accounts:login"))
            self.assertNotContains(response, "Continue with Google")

    def test_starting_the_flow_sends_the_visitor_to_google(self):
        response = self.client.get(reverse("accounts:google_start"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://accounts.google.com/"))
        self.assertIn("code_challenge=", response["Location"])
        self.assertIn("google_oauth_state", self.client.session)

    def test_a_new_google_email_creates_a_visitor_and_signs_them_in(self):
        _, response = self._callback()
        user = User.objects.get(email="riya@example.edu")
        self.assertEqual(user.role, Role.VISITOR)
        self.assertEqual(user.first_name, "Riya Sharma")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        self.assertContains(response, "Account created from your Google email")

    def test_an_existing_account_keeps_its_role(self):
        staff = User.objects.create_user(
            username="meera", email="riya@example.edu", password="counter-queue-42", role=Role.STAFF
        )
        self._callback()
        staff.refresh_from_db()
        self.assertEqual(staff.role, Role.STAFF)
        self.assertEqual(User.objects.filter(email="riya@example.edu").count(), 1)
        self.assertEqual(self.client.session["_auth_user_id"], str(staff.pk))

    def test_a_mismatched_state_is_refused(self):
        _, response = self._callback(tamper_state=True)
        self.assertEqual(User.objects.count(), 0)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "did not come from this browser")

    def test_a_token_for_another_application_is_refused(self):
        _, response = self._callback(id_token=self._id_token(aud="someone-elses-client"))
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "issued for a different application")

    def test_an_unverified_google_email_is_refused(self):
        _, response = self._callback(id_token=self._id_token(verified=False))
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "has not verified the email")

    def test_a_deactivated_account_cannot_come_back_in_through_google(self):
        User.objects.create_user(
            username="riya", email="riya@example.edu", password="x", is_active=False
        )
        _, response = self._callback()
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "deactivated")

    def test_usernames_do_not_collide(self):
        User.objects.create_user(username="riya", email="someone.else@example.edu", password="x")
        self._callback()
        self.assertEqual(User.objects.get(email="riya@example.edu").username, "riya2")


class OneAccountPerEmailTests(TestCase):
    """An address maps to one account, or resets and Google sign-in go astray."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="asha", email="asha@example.edu", password="counter-queue-42", role=Role.ADMIN
        )
        self.client.force_login(self.admin)

    def test_an_administrator_cannot_reuse_an_email(self):
        User.objects.create_user(
            username="riya", email="riya@example.edu", password="counter-queue-42"
        )
        response = self.client.post(
            reverse("dashboard:team_list"),
            {
                "first_name": "Riya Again",
                "username": "riya2",
                "email": "riya@example.edu",
                "phone": "",
                "department": "Accounts office",
                "role": Role.STAFF,
                "password1": "counter-queue-42",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Another account already uses this email")
        self.assertEqual(User.objects.filter(email__iexact="riya@example.edu").count(), 1)

    def test_the_check_ignores_case_and_spacing(self):
        User.objects.create_user(
            username="riya", email="riya@example.edu", password="counter-queue-42"
        )
        form = StaffAccountForm(
            {
                "first_name": "Riya",
                "username": "riya3",
                "email": "  RIYA@Example.edu ",
                "phone": "",
                "department": "",
                "role": Role.STAFF,
                "password1": "counter-queue-42",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class CreateAdminCommandTests(TestCase):
    """The shell-free way to make the first administrator on a host."""

    def _run(self, **env):
        out = StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            call_command("createadmin", stdout=out)
        return out.getvalue()

    def test_it_creates_an_administrator(self):
        self._run(
            DJANGO_ADMIN_USERNAME="asha",
            DJANGO_ADMIN_PASSWORD="counter-queue-42",
            DJANGO_ADMIN_EMAIL="asha@example.edu",
        )
        user = User.objects.get(username="asha")
        self.assertEqual(user.role, Role.ADMIN)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("counter-queue-42"))

    def test_running_it_again_leaves_the_account_alone(self):
        env = {
            "DJANGO_ADMIN_USERNAME": "asha",
            "DJANGO_ADMIN_PASSWORD": "counter-queue-42",
        }
        self._run(**env)
        # A deploy hook runs on every push, so a second run must not reset the
        # password of an account whose owner has since changed it.
        User.objects.filter(username="asha").update(first_name="Asha")
        user = User.objects.get(username="asha")
        user.set_password("something-they-chose-77")
        user.save()

        output = self._run(**env)
        user.refresh_from_db()
        self.assertIn("already exists", output)
        self.assertTrue(user.check_password("something-they-chose-77"))
        self.assertEqual(User.objects.filter(username="asha").count(), 1)

    def test_it_does_nothing_without_the_variables(self):
        output = self._run(DJANGO_ADMIN_USERNAME="", DJANGO_ADMIN_PASSWORD="")
        self.assertIn("skipping", output)
        self.assertEqual(User.objects.count(), 0)

    def test_a_weak_password_is_refused(self):
        with self.assertRaises(CommandError):
            self._run(DJANGO_ADMIN_USERNAME="asha", DJANGO_ADMIN_PASSWORD="12345")
        self.assertEqual(User.objects.count(), 0)

    def test_a_duplicate_email_is_refused(self):
        User.objects.create_user(username="riya", email="shared@example.edu", password="x")
        with self.assertRaises(CommandError):
            self._run(
                DJANGO_ADMIN_USERNAME="asha",
                DJANGO_ADMIN_PASSWORD="counter-queue-42",
                DJANGO_ADMIN_EMAIL="shared@example.edu",
            )
        self.assertFalse(User.objects.filter(username="asha").exists())


class TokenStatusEndpointTests(TestCase):
    """The endpoint the visitor's page polls, and the flag it notifies on."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.staff = User.objects.create_user(
            username="meera", password="counter-queue-42", role=Role.STAFF
        )
        self.counter = Counter.objects.create(
            name="Front desk", code="C1", status=CounterStatus.OPEN, assigned_staff=self.staff
        )
        self.counter.services.add(self.service)
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )
        self.client.force_login(self.visitor)

    def test_it_says_nothing_is_held_when_nothing_is(self):
        body = self.client.get(reverse("dashboard:token_status")).json()
        self.assertEqual(body, {"holding": False})

    def test_waiting_reports_the_place_in_line_and_does_not_call(self):
        queue_ops.issue_token(self.service, user=self.visitor)
        body = self.client.get(reverse("dashboard:token_status")).json()
        self.assertTrue(body["holding"])
        self.assertEqual(body["code"], "FEE-001")
        self.assertEqual(body["status"], EntryStatus.WAITING)
        self.assertFalse(body["is_up"])

    def test_being_called_raises_the_flag_with_the_counter(self):
        queue_ops.issue_token(self.service, user=self.visitor)
        queue_ops.call_next(self.counter, self.staff)

        body = self.client.get(reverse("dashboard:token_status")).json()
        self.assertTrue(body["is_up"])
        self.assertEqual(body["counter"], "C1")
        self.assertEqual(body["counter_name"], "Front desk")

    def test_the_flag_stays_up_while_being_served(self):
        entry = queue_ops.issue_token(self.service, user=self.visitor)
        queue_ops.call_next(self.counter, self.staff)
        entry.refresh_from_db()
        queue_ops.start_serving(entry, self.staff)

        self.assertTrue(self.client.get(reverse("dashboard:token_status")).json()["is_up"])

    def test_it_never_reports_somebody_elses_token(self):
        other = User.objects.create_user(
            username="sam", password="counter-queue-42", role=Role.VISITOR
        )
        queue_ops.issue_token(self.service, user=other)
        body = self.client.get(reverse("dashboard:token_status")).json()
        self.assertEqual(body, {"holding": False})

    def test_signed_out_visitors_are_sent_to_the_sign_in_page(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:token_status"))
        self.assertEqual(response.status_code, 302)


class WaitingCountsTests(TestCase):
    """Waiting figures count today's queue, not tokens stranded on old days."""

    def setUp(self):
        self.service = Service.objects.create(name="Fee payment", code="FEE")
        self.counter = Counter.objects.create(
            name="Front desk", code="C1", status=CounterStatus.OPEN
        )
        self.counter.services.add(self.service)
        self.visitor = User.objects.create_user(
            username="riya", password="counter-queue-42", role=Role.VISITOR
        )
        # Left waiting when the counters closed on an earlier day: the call
        # desk only pulls from today, so it can never be called again.
        stranded = Token.objects.create(
            service=self.service,
            number=99,
            issue_date=timezone.localdate() - timedelta(days=1),
        )
        QueueEntry.objects.create(token=stranded, status=EntryStatus.WAITING)

    def test_service_and_counter_counts_ignore_earlier_days(self):
        self.assertEqual(self.service.waiting_count, 0)
        self.assertEqual(self.counter.waiting_count, 0)

        queue_ops.issue_token(self.service, user=self.visitor)
        self.assertEqual(self.service.waiting_count, 1)
        self.assertEqual(self.counter.waiting_count, 1)

    def test_the_landing_page_does_not_advertise_a_queue_nobody_is_in(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.context["waiting_total"], 0)
        self.assertEqual(response.context["services"][0].waiting, 0)

    def test_the_admin_dashboard_agrees(self):
        admin = User.objects.create_user(
            username="asha", password="counter-queue-42", role=Role.ADMIN
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("dashboard:admin_home"))
        self.assertEqual(response.context["waiting_total"], 0)
