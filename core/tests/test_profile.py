import io
import re
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.models import Dog
from core.permissions import ADOPTER, ADMIN, STAFF
from core.validators import MAX_SIZE

from . import login_via_view

PASSWORD = 'Str0ngPass!234'


def make_image(name='photo.jpg', size=(800, 600), color='white'):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class MediaTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)


class ProfileTests(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='profile_user', password=PASSWORD
        )
        cls.other = User.objects.create_user(
            username='other_user', password=PASSWORD
        )
        cls.admin = User.objects.create_user(
            username='profile_admin', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))

    def profile_data(self, **overrides):
        data = {
            'full_name': 'ผู้ทดสอบ ระบบ',
            'phone': '0812345678',
            'address': '123 ถนนทดสอบ',
        }
        data.update(overrides)
        return data

    def upload_photo(self, user=None):
        client = Client()
        self.assertTrue(
            login_via_view(
                client, (user or self.user).username, PASSWORD
            )
        )
        response = client.post(
            reverse('my_profile'),
            self.profile_data(photo=make_image()),
        )
        self.assertEqual(response.status_code, 302)
        (user or self.user).profile.refresh_from_db()
        return (user or self.user).profile.photo

    def test_profile_requires_login(self):
        response = self.client.get(reverse('my_profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_valid_jpg_is_resized_and_shown_in_navbar(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('my_profile'),
            self.profile_data(photo=make_image(size=(800, 600))),
        )
        self.assertEqual(response.status_code, 302)

        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.photo)
        with Image.open(self.user.profile.photo.path) as image:
            self.assertEqual(image.size, (400, 400))
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.mode, 'RGB')

        response = self.client.get(reverse('home'))
        self.assertContains(
            response,
            reverse(
                'protected_file', args=['profile', self.user.profile.pk]
            ),
        )

    def test_exe_upload_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('my_profile'),
            self.profile_data(
                photo=SimpleUploadedFile(
                    'malware.exe',
                    b'MZ executable',
                    content_type='application/octet-stream',
                )
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'รับเฉพาะไฟล์ JPG')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.photo)

    def test_oversized_upload_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('my_profile'),
            self.profile_data(
                photo=SimpleUploadedFile(
                    'large.jpg',
                    b'x' * (MAX_SIZE + 1),
                    content_type='image/jpeg',
                )
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '5 MB')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.photo)

    def test_replacing_photo_deletes_the_old_file(self):
        old_photo = self.upload_photo()
        old_name = old_photo.name
        storage = old_photo.storage
        self.assertTrue(storage.exists(old_name))

        self.client.force_login(self.user)
        self.client.post(
            reverse('my_profile'),
            self.profile_data(photo=make_image('new.jpg')),
        )
        self.user.profile.refresh_from_db()

        self.assertNotEqual(self.user.profile.photo.name, old_name)
        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(self.user.profile.photo.name))

    def test_remove_photo_clears_and_deletes_the_file(self):
        old_photo = self.upload_photo()
        old_name = old_photo.name
        storage = old_photo.storage

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('my_profile'),
            self.profile_data(remove_photo='on'),
        )
        self.assertEqual(response.status_code, 302)

        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.photo)
        self.assertFalse(storage.exists(old_name))

    def test_initials_avatar_uses_thai_full_name(self):
        profile = self.user.profile
        profile.full_name = 'สมชาย'
        profile.save(update_fields=['full_name'])

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'avatar-initials')
        self.assertContains(response, '>ส<')

    def test_initials_avatar_falls_back_to_username(self):
        profile = self.other.profile
        profile.full_name = ''
        profile.save(update_fields=['full_name'])

        self.client.force_login(self.other)
        response = self.client.get(reverse('home'))
        self.assertContains(response, '>O<')

    def test_profile_url_only_updates_the_logged_in_user(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('my_profile'),
            self.profile_data(full_name='ชื่อใหม่ ทดสอบ'),
        )

        self.user.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'ชื่อใหม่ ทดสอบ')
        self.assertNotEqual(self.other.profile.full_name, 'ชื่อใหม่ ทดสอบ')

    def test_admin_can_remove_but_not_replace_another_users_photo(self):
        target = self.other
        target_photo = self.upload_photo(target)
        original_url = target_photo.url

        self.client.force_login(self.admin)
        self.client.post(
            reverse('user_edit', args=[target.pk]),
            {
                'username': target.username,
                'email': '',
                'full_name': target.profile.full_name,
                'phone': target.profile.phone,
                'address': target.profile.address,
                'photo': make_image('replacement.jpg'),
            },
        )
        target.profile.refresh_from_db()
        self.assertEqual(target.profile.photo.url, original_url)

        self.client.post(
            reverse('user_edit', args=[target.pk]),
            {
                'username': target.username,
                'email': '',
                'full_name': target.profile.full_name,
                'phone': target.profile.phone,
                'address': target.profile.address,
                'remove_photo': 'on',
            },
        )
        target.profile.refresh_from_db()
        self.assertFalse(target.profile.photo)

    def test_admin_cannot_remove_own_photo_from_edit_page(self):
        self.upload_photo(self.admin)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('user_edit', args=[self.admin.pk])
        )
        self.assertNotContains(response, 'name="remove_photo"')

        self.client.post(
            reverse('user_edit', args=[self.admin.pk]),
            {
                'username': self.admin.username,
                'email': '',
                'full_name': self.admin.profile.full_name,
                'phone': self.admin.profile.phone,
                'address': self.admin.profile.address,
                'remove_photo': 'on',
            },
        )
        self.admin.profile.refresh_from_db()
        self.assertTrue(self.admin.profile.photo)


class RequiredMarkerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username='marker_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.adopter = User.objects.create_user(
            username='marker_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.dog = Dog.objects.create(name='MarkerDog', status=Dog.AVAILABLE)

    def label_for(self, response, field_id):
        html = response.content.decode()
        match = re.search(
            r'<label[^>]*for="%s"[^>]*>(.*?)</label>'
            % re.escape(field_id),
            html,
            re.S,
        )
        return match.group(1) if match else ''

    def test_login_required_fields_have_asterisks(self):
        response = self.client.get(reverse('login'))
        self.assertIn('*', self.label_for(response, 'id_username'))
        self.assertIn('*', self.label_for(response, 'id_password'))

    def test_registration_marks_required_and_optional_fields(self):
        response = self.client.get(reverse('register'))
        for field_id in (
            'id_username',
            'id_password1',
            'id_password2',
            'id_full_name',
            'id_phone',
            'id_pdpa_consent',
        ):
            with self.subTest(field=field_id):
                self.assertIn('*', self.label_for(response, field_id))
        self.assertNotIn('*', self.label_for(response, 'id_address'))

        form = response.context['form']
        self.assertTrue(form.fields['username'].required)
        self.assertFalse(form.fields['address'].required)
        self.assertIn('required', form.fields['username'].widget.attrs)
        self.assertEqual(
            form.fields['username'].widget.attrs.get('aria-required'),
            'true',
        )

    def test_dog_form_marks_required_and_optional_fields(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('dog_create'))

        for field_id in (
            'id_name',
            'id_sex',
            'id_age_months',
            'id_size',
            'id_status',
            'id_intake_date',
        ):
            with self.subTest(field=field_id):
                self.assertIn('*', self.label_for(response, field_id))
        for field_id in (
            'id_breed',
            'id_color',
            'id_description',
            'id_photo',
        ):
            with self.subTest(field=field_id):
                self.assertNotIn('*', self.label_for(response, field_id))

    def test_checkbox_asterisk_only_on_pdpa(self):
        self.client.force_login(self.adopter)
        response = self.client.get(
            reverse('interview_book', args=[self.dog.pk])
        )
        self.assertIn('*', self.label_for(response, 'id_pdpa_consent'))
        self.assertNotIn(
            '*', self.label_for(response, 'id_agree_home_visit')
        )
