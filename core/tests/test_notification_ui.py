from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Dog, InterviewRequest, Notification
from core.permissions import ADOPTER

from . import login_via_view

PASSWORD = 'Str0ngPass!234'


class NotificationListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='notify_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.other = User.objects.create_user(
            username='notify_other', password=PASSWORD
        )
        cls.other.groups.add(Group.objects.get(name=ADOPTER))

    def make_notification(self, user=None, **kwargs):
        defaults = {
            'user': user or self.adopter,
            'title': 'หัวข้อแจ้งเตือน',
            'message': 'ข้อความแจ้งเตือน',
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    def test_anonymous_cannot_view_notifications(self):
        response = self.client.get(reverse('notification_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_adopter_sees_only_own_notifications(self):
        mine = self.make_notification(title='ของฉัน')
        hidden = self.make_notification(
            user=self.other, title='ของคนอื่น'
        )
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('notification_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, mine.title)
        self.assertNotContains(response, hidden.title)

    def test_header_shows_unread_badge(self):
        self.make_notification()
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications'], 1)
        self.assertContains(response, 'notification-bell')

    def test_mark_read_is_scoped_to_owner(self):
        notification = self.make_notification()
        self.client.force_login(self.other)
        response = self.client.post(
            reverse('notification_mark_read', args=[notification.pk])
        )
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('notification_mark_read', args=[notification.pk])
        )
        self.assertEqual(response.status_code, 302)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_mark_all_read_only_affects_current_user(self):
        mine = self.make_notification()
        other = self.make_notification(user=self.other)
        self.client.force_login(self.adopter)
        self.client.post(reverse('notifications_mark_all_read'))
        mine.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(mine.read_at)
        self.assertIsNone(other.read_at)

    def test_staff_confirm_notification_is_visible_to_adopter(self):
        from core.permissions import STAFF

        staff = User.objects.create_user(
            username='notify_staff', password=PASSWORD
        )
        staff.groups.add(Group.objects.get(name=STAFF))
        dog = Dog.objects.create(name='NotifyDog', status=Dog.AVAILABLE)
        interview = InterviewRequest.objects.create(
            adopter=self.adopter,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
        )
        self.client.force_login(staff)
        self.client.post(
            reverse('staff_interview_confirm', args=[interview.pk])
        )

        self.client.force_login(self.adopter)
        response = self.client.get(reverse('notification_list'))
        self.assertContains(response, 'นัดหมายสัมภาษณ์ได้รับการยืนยันแล้ว')


class InterviewReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='reminder_interview_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.dog = Dog.objects.create(
            name='ReminderInterviewDog', status=Dog.AVAILABLE
        )

    def test_upcoming_interview_creates_adopter_notification_once(self):
        interview = InterviewRequest.objects.create(
            adopter=self.adopter,
            dog=self.dog,
            scheduled_at=timezone.now() + timedelta(days=1),
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
            status=InterviewRequest.CONFIRMED,
        )
        call_command('queue_reminders')
        call_command('queue_reminders')

        key = (
            f'interview-reminder-{interview.pk}-'
            f'{interview.scheduled_at.isoformat()}'
        )
        self.assertEqual(
            Notification.objects.filter(dedupe_key=key).count(), 1
        )
        notification = Notification.objects.get(dedupe_key=key)
        self.assertEqual(notification.user, self.adopter)
        self.assertIn('นัดสัมภาษณ์', notification.title)

    def test_reminder_is_visible_on_adopter_dashboard(self):
        InterviewRequest.objects.create(
            adopter=self.adopter,
            dog=self.dog,
            scheduled_at=timezone.now() + timedelta(days=1),
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
            status=InterviewRequest.CONFIRMED,
        )
        call_command('queue_reminders')
        self.assertTrue(
            login_via_view(
                self.client, 'reminder_interview_adopter', PASSWORD
            )
        )
        response = self.client.get(reverse('adopter_dashboard'))
        self.assertContains(response, 'แจ้งเตือนการนัดสัมภาษณ์')
