from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.permissions import ADOPTER, ADMIN, STAFF


class RegistrationTests(TestCase):
    def registration_data(self, **overrides):
        data = {
            'username': 'newadopter',
            'password1': 'Str0ngPass!234',
            'password2': 'Str0ngPass!234',
            'full_name': 'ผู้สมัคร ทดสอบ',
            'phone': '0812345678',
            'address': '123 ถนนทดสอบ กรุงเทพฯ',
        }
        data.update(overrides)
        return data

    def test_registration_requires_pdpa_consent(self):
        response = self.client.post(reverse('register'), self.registration_data())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newadopter').exists())

    def test_registration_with_consent_creates_adopter(self):
        response = self.client.post(
            reverse('register'),
            self.registration_data(pdpa_consent='on'),
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newadopter')
        self.assertIsNotNone(user.profile.pdpa_consent_at)
        self.assertEqual(user.profile.full_name, 'ผู้สมัคร ทดสอบ')
        adopter_group = Group.objects.get(name=ADOPTER)
        self.assertTrue(user.groups.filter(pk=adopter_group.pk).exists())

    def test_password_hash_uses_argon2(self):
        self.client.post(
            reverse('register'),
            self.registration_data(pdpa_consent='on'),
        )
        user = User.objects.get(username='newadopter')
        self.assertTrue(user.password.startswith('argon2'))


class LoginTests(TestCase):
    def test_suspended_user_cannot_log_in(self):
        user = User.objects.create_user(username='suspended', password='Str0ngPass!234')
        user.is_active = False
        user.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('login'),
            {'username': 'suspended', 'password': 'Str0ngPass!234'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class RolePermissionTests(TestCase):
    def setUp(self):
        self.adopter = User.objects.create_user(username='adopter', password='Str0ngPass!234')
        self.adopter.groups.add(Group.objects.get(name=ADOPTER))

        self.staff = User.objects.create_user(username='staff', password='Str0ngPass!234')
        self.staff.groups.add(Group.objects.get(name=STAFF))

        self.admin = User.objects.create_user(username='admin', password='Str0ngPass!234')
        self.admin.groups.add(Group.objects.get(name=ADMIN))

    def test_adopter_gets_403_on_staff_and_admin_pages(self):
        self.client.force_login(self.adopter)
        for url in (
            reverse('staff_dashboard'),
            reverse('admin_dashboard'),
            reverse('user_list'),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_staff_gets_403_on_admin_pages(self):
        self.client.force_login(self.staff)
        for url in (reverse('admin_dashboard'), reverse('user_list'), reverse('staff_create')):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_can_access_admin_pages(self):
        self.client.force_login(self.admin)
        for url in (
            reverse('admin_dashboard'),
            reverse('user_list'),
            reverse('staff_create'),
            reverse('user_edit', args=[self.adopter.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('adopter_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class ProfileSignalTests(TestCase):
    def test_profile_is_created_with_user(self):
        user = User.objects.create_user(username='signaluser', password='Str0ngPass!234')
        self.assertTrue(hasattr(user, 'profile'))

    def test_shelter_settings_is_singleton(self):
        from core.models import ShelterSettings

        first = ShelterSettings.load()
        second = ShelterSettings.load()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ShelterSettings.objects.count(), 1)
