from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import Dog
from core.permissions import ADOPTER, ADMIN, STAFF
from core.validators import MAX_IMAGE_SIZE, validate_image

PASSWORD = 'Str0ngPass!234'


class DogPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dog = Dog.objects.create(name='ทดสอบ', status=Dog.AVAILABLE)
        cls.adopter = User.objects.create_user(username='dog_adopter', password=PASSWORD)
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(username='dog_staff', password=PASSWORD)
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.admin = User.objects.create_user(username='dog_admin', password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name=ADMIN))

    def staff_urls(self):
        return [
            reverse('dog_list'),
            reverse('dog_create'),
            reverse('dog_detail', args=[self.dog.pk]),
            reverse('dog_edit', args=[self.dog.pk]),
        ]

    def test_adopter_gets_403_on_staff_dog_pages(self):
        self.client.force_login(self.adopter)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_is_redirected_from_staff_dog_pages(self):
        for url in self.staff_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('login'), response.url)

    def test_staff_can_access_staff_dog_pages(self):
        self.client.force_login(self.staff)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_can_access_staff_dog_pages(self):
        self.client.force_login(self.admin)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class PublicDogListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.available = Dog.objects.create(name='AvailableDog', status=Dog.AVAILABLE)
        cls.pending = Dog.objects.create(name='PendingDog', status=Dog.PENDING)
        cls.adopted = Dog.objects.create(name='AdoptedDog', status=Dog.ADOPTED)
        cls.unavailable = Dog.objects.create(name='UnavailableDog', status=Dog.UNAVAILABLE)

    def test_public_list_shows_only_available_dogs(self):
        response = self.client.get(reverse('public_dog_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AvailableDog')
        self.assertNotContains(response, 'PendingDog')
        self.assertNotContains(response, 'AdoptedDog')
        self.assertNotContains(response, 'UnavailableDog')

    def test_public_list_search_and_filters(self):
        Dog.objects.create(name='SearchMe', breed='UniqueBreed', sex=Dog.FEMALE,
                           size=Dog.LARGE, status=Dog.AVAILABLE)
        response = self.client.get(
            reverse('public_dog_list'),
            {'q': 'UniqueBreed', 'sex': Dog.FEMALE, 'size': Dog.LARGE},
        )
        self.assertContains(response, 'SearchMe')

    def test_public_detail_has_interview_book_link(self):
        response = self.client.get(reverse('public_dog_detail', args=[self.available.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('interview_book', args=[self.available.pk]))


class ValidateImageTests(TestCase):
    def test_rejects_exe_extension(self):
        upload = SimpleUploadedFile(
            'malware.exe',
            b'MZ executable content',
            content_type='application/octet-stream',
        )
        with self.assertRaises(ValidationError):
            validate_image(upload)

    def test_rejects_files_over_five_megabytes(self):
        upload = SimpleUploadedFile(
            'large.jpg',
            b'x' * (MAX_IMAGE_SIZE + 1),
            content_type='image/jpeg',
        )
        with self.assertRaises(ValidationError):
            validate_image(upload)
