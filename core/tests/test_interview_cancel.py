from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Dog, InterviewRequest
from core.permissions import ADOPTER

PASSWORD = 'Str0ngPass!234'


class InterviewCancellationBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='cancel_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.dog = Dog.objects.create(name='CancelDog', status=Dog.AVAILABLE)

    def create_interview(self, scheduled_at, status=InterviewRequest.PENDING):
        return InterviewRequest.objects.create(
            adopter=self.adopter,
            dog=self.dog,
            scheduled_at=scheduled_at,
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
            status=status,
        )

    def test_model_property_requires_more_than_24_hours(self):
        now = timezone.make_aware(datetime(2026, 1, 1, 12, 0))
        interview = self.create_interview(now + timedelta(hours=24))
        with patch('django.utils.timezone.now', return_value=now):
            self.assertFalse(interview.can_cancel)

        interview.scheduled_at = now + timedelta(hours=24, seconds=1)
        with patch('django.utils.timezone.now', return_value=now):
            self.assertTrue(interview.can_cancel)

        interview.scheduled_at = now + timedelta(hours=23, minutes=59)
        with patch('django.utils.timezone.now', return_value=now):
            self.assertFalse(interview.can_cancel)

    def test_view_rejects_exactly_24_hours(self):
        now = timezone.now().replace(microsecond=0)
        interview = self.create_interview(now + timedelta(hours=24))
        self.client.force_login(self.adopter)
        with patch('django.utils.timezone.now', return_value=now):
            response = self.client.post(
                reverse('interview_cancel', args=[interview.pk]),
                follow=True,
            )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.PENDING)
        self.assertContains(response, 'มากกว่า 24 ชั่วโมง')

    def test_view_allows_more_than_24_hours(self):
        now = timezone.now().replace(microsecond=0)
        interview = self.create_interview(
            now + timedelta(hours=24, seconds=1)
        )
        self.client.force_login(self.adopter)
        with patch('django.utils.timezone.now', return_value=now):
            self.client.post(
                reverse('interview_cancel', args=[interview.pk])
            )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.CANCELLED)

    def test_view_rejects_past_appointment(self):
        now = timezone.now()
        interview = self.create_interview(now - timedelta(hours=1))
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_cancel', args=[interview.pk]), follow=True
        )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.PENDING)
        self.assertContains(response, 'มากกว่า 24 ชั่วโมง')

    def test_view_rejects_already_cancelled(self):
        interview = self.create_interview(
            timezone.now() + timedelta(days=3),
            status=InterviewRequest.CANCELLED,
        )
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_cancel', args=[interview.pk]), follow=True
        )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.CANCELLED)
        self.assertContains(response, 'ไม่สามารถยกเลิกนัดหมายนี้ได้')

    def test_other_adopter_cannot_cancel(self):
        other = User.objects.create_user(
            username='cancel_other', password=PASSWORD
        )
        other.groups.add(Group.objects.get(name=ADOPTER))
        interview = self.create_interview(
            timezone.now() + timedelta(days=3)
        )
        self.client.force_login(other)
        response = self.client.post(
            reverse('interview_cancel', args=[interview.pk])
        )
        self.assertEqual(response.status_code, 404)
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.PENDING)
