from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

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

    def test_public_urls(self):
        for url in (reverse('home'), reverse('login'), reverse('register')):
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
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)
