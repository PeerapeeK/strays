from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AuditEvent, Dog, InterviewRequest
from core.permissions import ADOPTER, ADMIN, STAFF
from core.services import is_last_active_admin

PASSWORD = 'Str0ngPass!234'


class UserAdminTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='admin_actor', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))
        cls.staff = User.objects.create_user(
            username='staff_user', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.adopter = User.objects.create_user(
            username='adopter_user', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.plain = User.objects.create_user(
            username='plain_user', password=PASSWORD
        )

    def edit_data(self, username, **overrides):
        data = {
            'username': username,
            'email': '',
            'full_name': '',
            'phone': '',
            'address': '',
        }
        data.update(overrides)
        return data

    def create_interview(self, adopter=None):
        dog = Dog.objects.create(name='UserAdminDog', status=Dog.AVAILABLE)
        return InterviewRequest.objects.create(
            adopter=adopter or self.adopter,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0812345678',
            address='123 ถนนทดสอบ',
        )


class UsernameChangeTests(UserAdminTestBase):
    def test_duplicate_username_rejected_case_insensitively(self):
        User.objects.create_user(username='TakenName', password=PASSWORD)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('user_edit', args=[self.plain.pk]),
            self.edit_data('takenname'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ชื่อผู้ใช้นี้ถูกใช้งานแล้ว')
        self.plain.refresh_from_db()
        self.assertEqual(self.plain.username, 'plain_user')

    def test_invalid_username_characters_rejected(self):
        self.client.force_login(self.admin)
        for username in ('bad user!', 'ผู้ใช้ไทย', 'bad/name'):
            with self.subTest(username=username):
                response = self.client.post(
                    reverse('user_edit', args=[self.plain.pk]),
                    self.edit_data(username),
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response, 'ชื่อผู้ใช้ใช้ได้เฉพาะตัวอักษรภาษาอังกฤษ'
                )

    def test_blank_username_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('user_edit', args=[self.plain.pk]),
            self.edit_data(''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'กรุณากรอกชื่อผู้ใช้')

    def test_admin_changes_username_and_target_stays_logged_in(self):
        target_client = Client()
        self.assertTrue(
            target_client.login(username='adopter_user', password=PASSWORD)
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('user_edit', args=[self.adopter.pk]),
            self.edit_data('adopter_new'),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ชื่อผู้ใช้ใหม่คือ adopter_new')
        self.adopter.refresh_from_db()
        self.assertEqual(self.adopter.username, 'adopter_new')

        self.assertEqual(
            target_client.get(reverse('adopter_dashboard')).status_code, 200
        )
        self.assertEqual(
            target_client.session['_auth_user_id'], str(self.adopter.pk)
        )

        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.USERNAME_CHANGE,
                target_id=self.adopter.pk,
                target_username='adopter_new',
            ).exists()
        )

    def test_edit_form_has_only_one_name_field(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('user_edit', args=[self.plain.pk])
        )
        self.assertEqual(response.status_code, 200)

        form = response.context['form']
        self.assertIn('username', form.fields)
        self.assertIn('email', form.fields)
        self.assertIn('full_name', form.fields)
        self.assertNotIn('first_name', form.fields)
        self.assertNotIn('last_name', form.fields)

        self.assertNotContains(response, 'name="first_name"')
        self.assertNotContains(response, 'name="last_name"')
        self.assertContains(response, 'name="full_name"', count=1)

    def test_staff_create_form_has_only_one_name_field(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('staff_create'))
        self.assertEqual(response.status_code, 200)

        form = response.context['form']
        self.assertIn('full_name', form.fields)
        self.assertNotIn('first_name', form.fields)
        self.assertNotIn('last_name', form.fields)

        self.assertNotContains(response, 'name="first_name"')
        self.assertNotContains(response, 'name="last_name"')
        self.assertContains(response, 'name="full_name"', count=1)

    def test_editing_does_not_touch_legacy_name_fields(self):
        self.plain.first_name = 'Legacy'
        self.plain.last_name = 'Name'
        self.plain.save(update_fields=['first_name', 'last_name'])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('user_edit', args=[self.plain.pk]),
            self.edit_data('plain_user', full_name='ชื่อใหม่ ทดสอบ'),
        )
        self.assertEqual(response.status_code, 302)

        self.plain.refresh_from_db()
        self.assertEqual(self.plain.first_name, 'Legacy')
        self.assertEqual(self.plain.last_name, 'Name')
        self.assertEqual(self.plain.profile.full_name, 'ชื่อใหม่ ทดสอบ')

    def test_same_username_with_different_case_is_allowed(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('user_edit', args=[self.plain.pk]),
            self.edit_data('Plain_User'),
        )
        self.assertEqual(response.status_code, 302)
        self.plain.refresh_from_db()
        self.assertEqual(self.plain.username, 'Plain_User')


class UserDeleteAnonymizeTests(UserAdminTestBase):
    def test_delete_user_without_records(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('admin_user_delete', args=[self.plain.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.plain.pk).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.DELETE, target_username='plain_user'
            ).exists()
        )

    def test_delete_blocked_for_user_with_interview_and_anonymize_keeps_records(self):
        interview = self.create_interview()
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('admin_user_delete', args=[self.adopter.pk])
        )
        self.assertEqual(response.status_code, 302)

        self.client.post(reverse('admin_user_delete', args=[self.adopter.pk]))
        self.assertTrue(User.objects.filter(pk=self.adopter.pk).exists())

        response = self.client.post(
            reverse('admin_user_anonymize', args=[self.adopter.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.adopter.refresh_from_db()
        self.assertEqual(
            self.adopter.username, f'deleted-{self.adopter.pk}'
        )
        self.assertFalse(self.adopter.is_active)
        self.assertFalse(self.adopter.has_usable_password())
        self.assertEqual(self.adopter.email, '')

        profile = self.adopter.profile
        self.assertEqual(profile.full_name, '')
        self.assertEqual(profile.phone, '')
        self.assertEqual(profile.address, '')
        self.assertIsNone(profile.pdpa_consent_at)

        interview.refresh_from_db()
        self.assertEqual(interview.adopter_id, self.adopter.pk)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.ANONYMIZE,
                target_id=self.adopter.pk,
                target_username='adopter_user',
            ).exists()
        )

    def test_cannot_delete_or_anonymize_self(self):
        self.client.force_login(self.admin)
        for url in (
            reverse('admin_user_delete', args=[self.admin.pk]),
            reverse('admin_user_anonymize', args=[self.admin.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.post(url)
                self.assertTrue(
                    User.objects.filter(pk=self.admin.pk).exists()
                )

    def test_admin_can_delete_another_admin_when_not_last(self):
        other_admin = User.objects.create_user(
            username='admin_other', password=PASSWORD
        )
        other_admin.groups.add(Group.objects.get(name=ADMIN))
        self.client.force_login(self.admin)

        self.client.post(
            reverse('admin_user_delete', args=[other_admin.pk])
        )
        self.assertFalse(User.objects.filter(pk=other_admin.pk).exists())

    def test_is_last_active_admin_helper(self):
        self.assertTrue(is_last_active_admin(self.admin))
        other_admin = User.objects.create_user(
            username='admin_two', password=PASSWORD
        )
        other_admin.groups.add(Group.objects.get(name=ADMIN))
        self.assertFalse(is_last_active_admin(self.admin))

    def test_non_admin_cannot_access_user_actions(self):
        for user in (self.staff, self.adopter):
            self.client.force_login(user)
            for url in (
                reverse('admin_user_delete', args=[self.plain.pk]),
                reverse('admin_user_anonymize', args=[self.plain.pk]),
            ):
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        for url in (
            reverse('admin_user_delete', args=[self.plain.pk]),
            reverse('admin_user_anonymize', args=[self.plain.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('login'), response.url)

    def test_delete_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(
            reverse('admin_user_delete', args=[self.plain.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.plain.pk).exists())


class UserAdminTemplateTests(UserAdminTestBase):
    def test_actions_hidden_for_self_and_delete_hidden_with_links(self):
        self.create_interview()
        self.client.force_login(self.admin)

        response = self.client.get(reverse('user_list'))
        self.assertNotContains(
            response, reverse('admin_user_delete', args=[self.admin.pk])
        )
        self.assertNotContains(
            response, reverse('admin_user_anonymize', args=[self.admin.pk])
        )
        self.assertNotContains(
            response, reverse('admin_user_delete', args=[self.adopter.pk])
        )
        self.assertContains(
            response, reverse('admin_user_anonymize', args=[self.adopter.pk])
        )
        self.assertContains(
            response, reverse('admin_user_delete', args=[self.plain.pk])
        )

    def test_edit_page_explains_linked_records(self):
        self.create_interview()
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('user_edit', args=[self.adopter.pk])
        )
        self.assertContains(response, 'มีประวัติการใช้งาน')
        self.assertNotContains(
            response, reverse('admin_user_delete', args=[self.adopter.pk])
        )
        self.assertContains(
            response, reverse('admin_user_anonymize', args=[self.adopter.pk])
        )

    def test_audit_log_shows_account_events(self):
        AuditEvent.objects.create(
            actor=self.admin,
            actor_username=self.admin.username,
            action=AuditEvent.USERNAME_CHANGE,
            target_id=999,
            target_username='changed_user',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_log'))
        self.assertContains(response, 'ประวัติการจัดการบัญชีผู้ใช้')
        self.assertContains(response, 'เปลี่ยนชื่อผู้ใช้')
        self.assertContains(response, 'changed_user')
