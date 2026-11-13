from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AdoptionContract,
    Dog,
    FollowUp,
    HomeVisit,
    InterviewRequest,
    InterviewResult,
)
from core.permissions import ADOPTER, ADMIN, STAFF

PASSWORD = 'Str0ngPass!234'


class AdminLeastPrivilegeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='privacy_admin', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))
        cls.staff = User.objects.create_user(
            username='privacy_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.adopter = User.objects.create_user(
            username='privacy_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        profile = cls.adopter.profile
        profile.full_name = 'ชื่อส่วนตัว ควรซ่อน'
        profile.phone = '0899999999'
        profile.address = 'ที่อยู่ส่วนตัว ควรซ่อน'
        profile.save()

        dog = Dog.objects.create(name='PrivacyDog', status=Dog.ADOPTED)
        interview = InterviewRequest.objects.create(
            adopter=cls.adopter,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ชื่อส่วนตัว ควรซ่อน',
            phone='0899999999',
            address='ที่อยู่ส่วนตัว ควรซ่อน',
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
        cls.follow_up = FollowUp.objects.create(
            contract=cls.contract,
            day_offset=14,
            due_date=date.today() + timedelta(days=14),
        )
        cls.home_visit = HomeVisit.objects.create(
            contract=cls.contract,
            scheduled_at=timezone.now() + timedelta(days=5),
        )

    def staff_urls(self):
        return (
            reverse('staff_dashboard'),
            reverse('staff_interview_list'),
            reverse('staff_contract_list'),
            reverse('staff_contract_detail', args=[self.contract.pk]),
            reverse('staff_contract_edit', args=[self.contract.pk]),
            reverse('staff_followup_list'),
            reverse('staff_followup_detail', args=[self.follow_up.pk]),
            reverse('staff_home_visit_list'),
            reverse('homevisit_edit', args=[self.home_visit.pk]),
        )

    def test_admin_cannot_reach_adoption_workflow_pages(self):
        self.client.force_login(self.admin)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_staff_can_reach_adoption_workflow_pages(self):
        self.client.force_login(self.staff)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_adopter_cannot_reach_staff_pages(self):
        self.client.force_login(self.adopter)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_keeps_account_and_report_access(self):
        self.client.force_login(self.admin)
        for url in (
            reverse('admin_dashboard'),
            reverse('user_list'),
            reverse('staff_create'),
            reverse('audit_log'),
            reverse('adoption_stats'),
            reverse('followup_stats'),
            reverse('notification_list'),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_user_list_does_not_expose_contact_details(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'ชื่อส่วนตัว ควรซ่อน')
        self.assertNotContains(response, '0899999999')
        self.assertNotContains(response, 'ที่อยู่ส่วนตัว ควรซ่อน')

    def test_admin_user_edit_does_not_expose_personal_fields(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('user_edit', args=[self.adopter.pk])
        )
        self.assertNotContains(response, 'name="full_name"')
        self.assertNotContains(response, 'name="phone"')
        self.assertNotContains(response, 'name="address"')
        self.assertNotContains(response, 'ชื่อส่วนตัว ควรซ่อน')

    def test_django_admin_does_not_expose_adoption_evidence_models(self):
        from django.contrib import admin

        from core.models import (
            AdoptionContract,
            FollowUp,
            HomeVisit,
            InterviewRequest,
            InterviewResult,
        )

        for model in (
            InterviewRequest,
            InterviewResult,
            AdoptionContract,
            FollowUp,
            HomeVisit,
        ):
            with self.subTest(model=model.__name__):
                self.assertNotIn(model, admin.site._registry)

    def test_adopter_cannot_open_another_adopters_records(self):
        other = User.objects.create_user(
            username='privacy_other', password=PASSWORD
        )
        other.groups.add(Group.objects.get(name=ADOPTER))
        self.client.force_login(other)
        expected = (
            (reverse('interview_detail', args=[
                self.contract.interview_request.pk
            ]), 404),
            (reverse('contract_detail', args=[self.contract.pk]), 404),
            (reverse('followup_detail', args=[self.follow_up.pk]), 404),
        )
        for url, status in expected:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)
