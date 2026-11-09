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


class SmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for username, role in (
            ('smoke_admin', ADMIN),
            ('smoke_staff', STAFF),
            ('smoke_adopter', ADOPTER),
        ):
            user = User.objects.create_user(username=username, password=PASSWORD)
            user.groups.add(Group.objects.get(name=role))
            cls.users[role] = user

        cls.admin = cls.users[ADMIN]
        cls.dog = Dog.objects.create(name='SmokeDog', status=Dog.AVAILABLE)
        cls.interview = InterviewRequest.objects.create(
            adopter=cls.users[ADOPTER],
            dog=cls.dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0800000000',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.CONFIRMED,
        )

        cls.approved_interview = InterviewRequest.objects.create(
            adopter=cls.users[ADOPTER],
            dog=cls.dog,
            scheduled_at=timezone.now() + timedelta(days=4),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0800000000',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.COMPLETED,
        )
        InterviewResult.objects.create(
            interview_request=cls.approved_interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่านการสัมภาษณ์',
        )

        cls.contract_interview = InterviewRequest.objects.create(
            adopter=cls.users[ADOPTER],
            dog=Dog.objects.create(name='ContractDog', status=Dog.ADOPTED),
            scheduled_at=timezone.now() + timedelta(days=5),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0800000000',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.COMPLETED,
        )
        InterviewResult.objects.create(
            interview_request=cls.contract_interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่านการสัมภาษณ์',
        )
        cls.contract = AdoptionContract.objects.create(
            interview_request=cls.contract_interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )
        cls.follow_up = FollowUp.objects.create(
            contract=cls.contract,
            day_offset=14,
            due_date=date.today() + timedelta(days=14),
            status=FollowUp.SUBMITTED,
            submitted_at=timezone.now(),
        )
        cls.home_visit = HomeVisit.objects.create(
            contract=cls.contract,
            scheduled_at=timezone.now() + timedelta(days=7),
        )

    def test_public_urls(self):
        urls = (
            reverse('home'),
            reverse('login'),
            reverse('register'),
            reverse('public_dog_list'),
            reverse('public_dog_detail', args=[self.dog.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_urls(self):
        self.assertTrue(self.client.login(username='smoke_admin', password=PASSWORD))
        expected = {
            reverse('home'): 200,
            reverse('dashboard'): 302,
            reverse('admin_dashboard'): 200,
            reverse('staff_dashboard'): 200,
            reverse('user_list'): 200,
            reverse('staff_create'): 200,
            reverse('user_edit', args=[self.admin.pk]): 200,
            reverse('admin_user_delete', args=[self.users[ADOPTER].pk]): 302,
            reverse('admin_user_anonymize', args=[self.users[ADOPTER].pk]): 200,
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_list'): 200,
            reverse('dog_create'): 200,
            reverse('dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_edit', args=[self.dog.pk]): 200,
            reverse('staff_interview_list'): 200,
            reverse('staff_interview_result', args=[self.interview.pk]): 200,
            reverse('staff_contract_list'): 200,
            reverse('staff_contract_create', args=[self.approved_interview.pk]): 200,
            reverse('staff_contract_detail', args=[self.contract.pk]): 200,
            reverse('staff_contract_edit', args=[self.contract.pk]): 200,
            reverse('homevisit_create', args=[self.contract.pk]): 200,
            reverse('homevisit_edit', args=[self.home_visit.pk]): 200,
            reverse('staff_followup_list'): 200,
            reverse('staff_followup_detail', args=[self.follow_up.pk]): 200,
            reverse('staff_followup_evaluate', args=[self.follow_up.pk]): 200,
            reverse('adoption_stats'): 200,
            reverse('followup_stats'): 200,
            reverse('adoption_stats_csv'): 200,
            reverse('followup_stats_csv'): 200,
            reverse('audit_log'): 200,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_staff_urls(self):
        self.assertTrue(self.client.login(username='smoke_staff', password=PASSWORD))
        expected = {
            reverse('home'): 200,
            reverse('dashboard'): 302,
            reverse('staff_dashboard'): 200,
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_list'): 200,
            reverse('dog_create'): 200,
            reverse('dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_edit', args=[self.dog.pk]): 200,
            reverse('staff_interview_list'): 200,
            reverse('staff_interview_result', args=[self.interview.pk]): 200,
            reverse('staff_contract_list'): 200,
            reverse('staff_contract_create', args=[self.approved_interview.pk]): 200,
            reverse('staff_contract_detail', args=[self.contract.pk]): 200,
            reverse('staff_contract_edit', args=[self.contract.pk]): 200,
            reverse('homevisit_create', args=[self.contract.pk]): 200,
            reverse('homevisit_edit', args=[self.home_visit.pk]): 200,
            reverse('staff_followup_list'): 200,
            reverse('staff_followup_detail', args=[self.follow_up.pk]): 200,
            reverse('staff_followup_evaluate', args=[self.follow_up.pk]): 200,
            reverse('adoption_stats'): 200,
            reverse('followup_stats'): 200,
            reverse('adoption_stats_csv'): 200,
            reverse('followup_stats_csv'): 200,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_adopter_urls(self):
        self.assertTrue(self.client.login(username='smoke_adopter', password=PASSWORD))
        expected = {
            reverse('home'): 200,
            reverse('dashboard'): 302,
            reverse('adopter_dashboard'): 200,
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('interview_book', args=[self.dog.pk]): 200,
            reverse('interview_list'): 200,
            reverse('interview_detail', args=[self.interview.pk]): 200,
            reverse('contract_list'): 200,
            reverse('contract_detail', args=[self.contract.pk]): 200,
            reverse('followup_list'): 200,
            reverse('followup_detail', args=[self.follow_up.pk]): 200,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_report_and_audit_permissions(self):
        self.assertTrue(
            self.client.login(username='smoke_adopter', password=PASSWORD)
        )
        for url in (
            reverse('adoption_stats'),
            reverse('followup_stats'),
            reverse('adoption_stats_csv'),
            reverse('followup_stats_csv'),
            reverse('audit_log'),
        ):
            with self.subTest(role='adopter', url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        self.assertTrue(self.client.login(username='smoke_staff', password=PASSWORD))
        self.assertEqual(
            self.client.get(reverse('audit_log')).status_code, 403
        )


class HomePageTests(TestCase):
    def test_home_without_dogs(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ให้เขาได้กลับบ้านสักที')
        self.assertNotContains(response, 'home-strip')
        self.assertContains(response, reverse('public_dog_list'))

    def test_home_with_three_or_more_dogs_shows_strip(self):
        dogs = [
            Dog.objects.create(name=f'HomeDog{i}', status=Dog.AVAILABLE)
            for i in range(3)
        ]
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'home-strip')
        for dog in dogs:
            self.assertContains(response, reverse('public_dog_detail', args=[dog.pk]))
        self.assertContains(response, reverse('register'))

    def test_home_with_fewer_than_three_dogs_hides_strip(self):
        Dog.objects.create(name='HomeDogOne', status=Dog.AVAILABLE)
        Dog.objects.create(name='HomeDogTwo', status=Dog.AVAILABLE)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'home-strip')


class HomePageNoDogsTests(TestCase):
    def test_home_returns_200_without_dogs(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

