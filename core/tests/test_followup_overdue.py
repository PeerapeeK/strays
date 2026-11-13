from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AdoptionContract,
    Dog,
    FollowUp,
    FollowUpEvaluation,
    InterviewRequest,
)
from core.permissions import ADOPTER, STAFF

PASSWORD = 'Str0ngPass!234'


class FollowUpOverdueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='overdue_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(
            username='overdue_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))

        dog = Dog.objects.create(name='OverdueDog', status=Dog.ADOPTED)
        interview = InterviewRequest.objects.create(
            adopter=cls.adopter,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
            status=InterviewRequest.COMPLETED,
        )
        cls.contract = AdoptionContract.objects.create(
            interview_request=interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )

    def make_follow_up(self, day_offset, due_date, **overrides):
        values = {
            'contract': self.contract,
            'day_offset': day_offset,
            'due_date': due_date,
            'status': FollowUp.PENDING,
        }
        values.update(overrides)
        return FollowUp.objects.create(**values)

    def test_future_pending_is_not_overdue(self):
        follow_up = self.make_follow_up(
            14, date.today() + timedelta(days=2)
        )
        self.assertFalse(follow_up.is_overdue)

    def test_due_today_is_not_overdue(self):
        follow_up = self.make_follow_up(14, date.today())
        self.assertFalse(follow_up.is_overdue)

    def test_pending_past_due_is_overdue(self):
        follow_up = self.make_follow_up(
            14, date.today() - timedelta(days=1)
        )
        self.assertTrue(follow_up.is_overdue)

    def test_submitted_after_due_is_not_overdue(self):
        follow_up = self.make_follow_up(
            14,
            date.today() - timedelta(days=5),
            status=FollowUp.SUBMITTED,
            submitted_at=timezone.now(),
        )
        self.assertFalse(follow_up.is_overdue)

    def test_submitted_and_reviewed_is_not_overdue(self):
        follow_up = self.make_follow_up(
            14,
            date.today() - timedelta(days=5),
            status=FollowUp.SUBMITTED,
            submitted_at=timezone.now(),
        )
        FollowUpEvaluation.objects.create(
            follow_up=follow_up,
            housing_condition='ดี',
            dog_condition='ดี',
        )
        self.assertFalse(follow_up.is_overdue)

    def test_adopter_list_marks_pending_past_due_as_overdue(self):
        overdue = self.make_follow_up(
            14, date.today() - timedelta(days=1)
        )
        submitted = self.make_follow_up(
            30,
            date.today() - timedelta(days=1),
            status=FollowUp.SUBMITTED,
            submitted_at=timezone.now(),
        )
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('followup_list'))
        self.assertContains(response, 'เกินกำหนด')
        rows = list(response.context['follow_ups'])
        self.assertTrue(overdue.is_overdue)
        self.assertFalse(submitted.is_overdue)
        self.assertContains(response, f'{overdue.day_offset} วัน')

    def test_staff_list_marks_pending_past_due_as_overdue(self):
        self.make_follow_up(14, date.today() - timedelta(days=1))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('staff_followup_list'))
        self.assertContains(response, 'เกินกำหนด')
