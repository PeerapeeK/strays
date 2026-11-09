from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import (
    AdoptionContract,
    Dog,
    FollowUp,
    HomeVisit,
    InterviewRequest,
    Notification,
)
from core.push import send_push

PASSWORD = 'Str0ngPass!234'
PUSH_URL = 'https://push.example.test/send'


class PushDispatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='push_user', password=PASSWORD)

    def make_notification(self, **kwargs):
        defaults = {
            'user': self.user,
            'title': 'ทดสอบการแจ้งเตือน',
            'message': 'ข้อความทดสอบ',
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    @override_settings(PUSH_PROVIDER_URL=PUSH_URL, PUSH_TIMEOUT=10)
    @patch('core.push.requests.post')
    def test_success_marks_sent_and_uses_ten_second_timeout(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        notification = self.make_notification()

        self.assertTrue(send_push(notification))

        notification.refresh_from_db()
        self.assertEqual(notification.status, Notification.SENT)
        self.assertEqual(notification.attempts, 1)
        self.assertEqual(notification.last_error, '')
        self.assertEqual(mock_post.call_args.kwargs['timeout'], 10)

    @override_settings(
        PUSH_PROVIDER_URL=PUSH_URL,
        PUSH_MAX_ATTEMPTS=4,
        PUSH_RETRY_DELAY=60,
    )
    @patch('core.push.requests.post', side_effect=requests.ConnectionError('boom'))
    def test_failure_schedules_retry_with_delay(self, mock_post):
        notification = self.make_notification()

        self.assertFalse(send_push(notification))

        notification.refresh_from_db()
        self.assertEqual(notification.status, Notification.PENDING)
        self.assertEqual(notification.attempts, 1)
        self.assertIn('boom', notification.last_error)
        self.assertGreater(notification.next_attempt_at, timezone.now())

    @override_settings(
        PUSH_PROVIDER_URL=PUSH_URL,
        PUSH_MAX_ATTEMPTS=4,
        PUSH_RETRY_DELAY=0,
    )
    @patch('core.push.requests.post', side_effect=requests.ConnectionError('boom'))
    def test_status_failed_after_one_try_plus_three_retries(self, mock_post):
        notification = self.make_notification()

        for _ in range(4):
            self.assertFalse(send_push(notification))

        notification.refresh_from_db()
        self.assertEqual(notification.attempts, 4)
        self.assertEqual(notification.status, Notification.FAILED)
        self.assertEqual(mock_post.call_count, 4)

    @override_settings(PUSH_PROVIDER_URL='')
    @patch('core.push.requests.post')
    def test_dev_mode_marks_sent_without_http_request(self, mock_post):
        notification = self.make_notification()

        self.assertTrue(send_push(notification))

        notification.refresh_from_db()
        self.assertEqual(notification.status, Notification.SENT)
        mock_post.assert_not_called()


class SendNotificationsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='command_user', password=PASSWORD)

    def make_notification(self, **kwargs):
        defaults = {
            'user': self.user,
            'title': 'ทดสอบคำสั่ง',
            'message': 'ข้อความทดสอบ',
            'next_attempt_at': timezone.now() - timedelta(seconds=1),
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    @override_settings(
        PUSH_PROVIDER_URL=PUSH_URL,
        PUSH_MAX_ATTEMPTS=4,
        PUSH_RETRY_DELAY=0,
    )
    @patch('core.push.requests.post', side_effect=requests.ConnectionError('down'))
    def test_command_retries_then_marks_failed(self, mock_post):
        notification = self.make_notification()

        for _ in range(4):
            notification.next_attempt_at = timezone.now() - timedelta(seconds=1)
            notification.save(update_fields=['next_attempt_at'])
            call_command('send_notifications')

        notification.refresh_from_db()
        self.assertEqual(notification.attempts, 4)
        self.assertEqual(notification.status, Notification.FAILED)

    @override_settings(PUSH_PROVIDER_URL=PUSH_URL)
    @patch('core.push.requests.post')
    def test_command_skips_notifications_not_yet_due(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        notification = self.make_notification(
            next_attempt_at=timezone.now() + timedelta(hours=1)
        )

        call_command('send_notifications')

        notification.refresh_from_db()
        self.assertEqual(notification.attempts, 0)
        self.assertEqual(notification.status, Notification.PENDING)
        mock_post.assert_not_called()


class QueueRemindersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='reminder_adopter', password=PASSWORD
        )
        dog = Dog.objects.create(name='ReminderDog', status=Dog.ADOPTED)
        interview = InterviewRequest.objects.create(
            adopter=cls.adopter,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ การเตือน',
            phone='0812345678',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.COMPLETED,
        )
        cls.contract = AdoptionContract.objects.create(
            interview_request=interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )

    def test_overdue_follow_up_marked_and_notification_deduped(self):
        follow_up = FollowUp.objects.create(
            contract=self.contract,
            day_offset=14,
            due_date=date.today() - timedelta(days=1),
        )

        call_command('queue_reminders')
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUp.OVERDUE)

        key = f'followup-overdue-{follow_up.pk}-{follow_up.due_date.isoformat()}'
        self.assertEqual(Notification.objects.filter(dedupe_key=key).count(), 1)

        call_command('queue_reminders')
        self.assertEqual(Notification.objects.filter(dedupe_key=key).count(), 1)

    def test_upcoming_follow_up_reminder_deduped(self):
        due_date = date.today() + timedelta(days=1)
        follow_up = FollowUp.objects.create(
            contract=self.contract,
            day_offset=30,
            due_date=due_date,
        )

        call_command('queue_reminders')
        call_command('queue_reminders')

        key = f'followup-reminder-{follow_up.pk}-{due_date.isoformat()}'
        self.assertEqual(Notification.objects.filter(dedupe_key=key).count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_home_visit_reminder_deduped(self):
        scheduled_at = timezone.now() + timedelta(days=1)
        home_visit = HomeVisit.objects.create(
            contract=self.contract,
            scheduled_at=scheduled_at,
        )

        call_command('queue_reminders')
        call_command('queue_reminders')

        key = f'homevisit-reminder-{home_visit.pk}-{scheduled_at.isoformat()}'
        self.assertEqual(Notification.objects.filter(dedupe_key=key).count(), 1)

    def test_follow_up_outside_reminder_window_is_not_queued(self):
        FollowUp.objects.create(
            contract=self.contract,
            day_offset=90,
            due_date=date.today() + timedelta(days=10),
        )

        call_command('queue_reminders')

        self.assertFalse(Notification.objects.exists())
