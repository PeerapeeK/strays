from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AdoptionContract,
    Dog,
    HomeVisit,
    InterviewRequest,
    InterviewResult,
    Notification,
)
from core.permissions import ADOPTER, STAFF

PASSWORD = 'Str0ngPass!234'


class HomeVisitConfirmationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='visit_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.other = User.objects.create_user(
            username='visit_other', password=PASSWORD
        )
        cls.other.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(
            username='visit_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))

        dog = Dog.objects.create(name='VisitDog', status=Dog.ADOPTED)
        interview = InterviewRequest.objects.create(
            adopter=cls.adopter,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
            status=InterviewRequest.COMPLETED,
        )
        InterviewResult.objects.create(
            interview_request=interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่าน',
        )
        cls.contract = AdoptionContract.objects.create(
            interview_request=interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )

    def future(self, days=5):
        now = timezone.localtime(timezone.now())
        return (now + timedelta(days=days)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

    def make_visit(self, **overrides):
        values = {
            'contract': self.contract,
            'scheduled_at': self.future(),
            'status': HomeVisit.SCHEDULED,
        }
        values.update(overrides)
        return HomeVisit.objects.create(**values)

    def test_adopter_sees_visit_and_confirm_action(self):
        visit = self.make_visit()
        self.client.force_login(self.adopter)
        response = self.client.get(
            reverse('contract_detail', args=[self.contract.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ยืนยันรับนัดตรวจบ้าน')
        self.assertContains(response, visit.scheduled_at.strftime('%d/%m/%Y'))
        self.assertContains(response, 'รอการยืนยันจากคุณ')

    def test_adopter_confirms_and_staff_is_notified(self):
        visit = self.make_visit()
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('homevisit_confirm', args=[visit.pk])
        )
        self.assertEqual(response.status_code, 302)
        visit.refresh_from_db()
        self.assertIsNotNone(visit.adopter_confirmed_at)
        self.assertTrue(
            Notification.objects.filter(
                user=self.staff, title__contains='ยืนยันนัดตรวจบ้าน'
            ).exists()
        )

    def test_other_adopter_cannot_confirm(self):
        visit = self.make_visit()
        self.client.force_login(self.other)
        response = self.client.post(
            reverse('homevisit_confirm', args=[visit.pk])
        )
        self.assertEqual(response.status_code, 404)
        visit.refresh_from_db()
        self.assertIsNone(visit.adopter_confirmed_at)

    def test_cannot_confirm_when_reschedule_requested(self):
        visit = self.make_visit(
            status=HomeVisit.RESCHEDULE_REQUESTED,
            requested_scheduled_at=self.future(days=8),
            reschedule_reason='ติดธุระ',
            reschedule_requested_at=timezone.now(),
        )
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('homevisit_confirm', args=[visit.pk]), follow=True
        )
        visit.refresh_from_db()
        self.assertIsNone(visit.adopter_confirmed_at)
        self.assertContains(response, 'สถานะปัจจุบัน')

    def test_cannot_confirm_past_visit(self):
        visit = self.make_visit(
            scheduled_at=timezone.now() - timedelta(days=1)
        )
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('homevisit_confirm', args=[visit.pk]), follow=True
        )
        visit.refresh_from_db()
        self.assertIsNone(visit.adopter_confirmed_at)
        self.assertContains(response, 'ผ่านมาแล้ว')

    def test_confirm_is_idempotent(self):
        confirmed_at = timezone.now() - timedelta(hours=1)
        visit = self.make_visit(adopter_confirmed_at=confirmed_at)
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('homevisit_confirm', args=[visit.pk]), follow=True
        )
        visit.refresh_from_db()
        self.assertEqual(visit.adopter_confirmed_at, confirmed_at)
        self.assertContains(response, 'ยืนยันนัดตรวจบ้านนี้แล้ว')

    def test_staff_sees_confirmation_state(self):
        visit = self.make_visit(adopter_confirmed_at=timezone.now())
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('staff_contract_detail', args=[self.contract.pk])
        )
        self.assertContains(response, 'ยืนยันแล้วเมื่อ')

    def test_staff_edit_resets_confirmation(self):
        visit = self.make_visit(adopter_confirmed_at=timezone.now())
        self.client.force_login(self.staff)
        self.client.post(
            reverse('homevisit_edit', args=[visit.pk]),
            {
                'scheduled_at': self.future(days=6).strftime('%Y-%m-%dT%H:%M'),
                'notes': 'เลื่อนเวลา',
            },
        )
        visit.refresh_from_db()
        self.assertIsNone(visit.adopter_confirmed_at)

    def test_staff_approving_reschedule_resets_confirmation(self):
        visit = self.make_visit(
            status=HomeVisit.RESCHEDULE_REQUESTED,
            requested_scheduled_at=self.future(days=9),
            reschedule_reason='ติดธุระ',
            reschedule_requested_at=timezone.now(),
            adopter_confirmed_at=timezone.now() - timedelta(days=1),
        )
        self.client.force_login(self.staff)
        self.client.post(reverse('homevisit_approve', args=[visit.pk]))
        visit.refresh_from_db()
        self.assertEqual(visit.status, HomeVisit.APPROVED)
        self.assertIsNone(visit.adopter_confirmed_at)

    def test_staff_home_visit_list_shows_confirmation(self):
        self.make_visit(adopter_confirmed_at=timezone.now())
        self.client.force_login(self.staff)
        response = self.client.get(reverse('staff_home_visit_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ยืนยันแล้ว')
