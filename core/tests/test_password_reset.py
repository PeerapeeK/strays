import re

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.permissions import ADOPTER

from . import login_via_view

PASSWORD = 'Str0ngPass!234'
NEW_PASSWORD = 'N3wStr0ng!Pass'


class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='reset_user',
            email='reset@example.com',
            password=PASSWORD,
        )
        cls.user.groups.add(Group.objects.get(name=ADOPTER))

    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'ลืมรหัสผ่าน?')
        self.assertContains(response, reverse('password_reset'))

    def request_reset(self, email):
        return self.client.post(reverse('password_reset'), {'email': email})

    def test_known_email_sends_reset_link(self):
        response = self.request_reset(self.user.email)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ตั้งรหัสผ่านใหม่', mail.outbox[0].subject)
        self.assertIn('/reset/', mail.outbox[0].body)

    def test_unknown_email_does_not_reveal_account_and_sends_nothing(self):
        response = self.request_reset('missing@example.com')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)
        done = self.client.get(reverse('password_reset_done'))
        self.assertContains(done, 'ตรวจสอบอีเมลของคุณ')

    def extract_reset_path(self, body):
        match = re.search(r'(/reset/[^\s]+/)', body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_user_can_set_new_password_and_log_in(self):
        self.request_reset(self.user.email)
        reset_path = self.extract_reset_path(mail.outbox[0].body)

        first_get = self.client.get(reset_path)
        self.assertEqual(first_get.status_code, 302)
        set_password_path = first_get.url

        form_page = self.client.get(set_password_path)
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(form_page, 'ตั้งรหัสผ่านใหม่')

        response = self.client.post(
            set_password_path,
            {
                'new_password1': NEW_PASSWORD,
                'new_password2': NEW_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse('password_reset_complete')
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.password.startswith('argon2'))
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

        self.assertFalse(
            login_via_view(self.client, 'reset_user', PASSWORD)
        )
        self.assertTrue(
            login_via_view(self.client, 'reset_user', NEW_PASSWORD)
        )

    def test_invalid_or_used_token_is_rejected(self):
        response = self.client.get(
            reverse(
                'password_reset_confirm',
                kwargs={'uidb64': 'invalid', 'token': 'invalid-token'},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ลิงก์ไม่ถูกต้องหรือหมดอายุ')

    def test_reset_token_cannot_be_used_twice(self):
        self.request_reset(self.user.email)
        reset_path = self.extract_reset_path(mail.outbox[0].body)
        set_password_path = self.client.get(reset_path).url
        self.client.post(
            set_password_path,
            {
                'new_password1': NEW_PASSWORD,
                'new_password2': NEW_PASSWORD,
            },
        )
        response = self.client.get(set_password_path)
        self.assertContains(response, 'ลิงก์ไม่ถูกต้องหรือหมดอายุ')
