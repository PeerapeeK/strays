from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Dog, InterviewRequest
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
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_list'): 200,
            reverse('dog_create'): 200,
            reverse('dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_edit', args=[self.dog.pk]): 200,
            reverse('staff_interview_list'): 200,
            reverse('staff_interview_result', args=[self.interview.pk]): 200,
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
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)
