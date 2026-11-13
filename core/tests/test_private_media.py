import io
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import (
    AdoptionContract,
    Dog,
    FollowUp,
    FollowUpEvaluation,
    FollowUpEvaluationPhoto,
    FollowUpPhoto,
    HousingPhoto,
    InterviewPhoto,
    InterviewRequest,
    InterviewResult,
)
from core.permissions import ADOPTER, ADMIN, STAFF

PASSWORD = 'Str0ngPass!234'


def make_image(name='photo.jpg'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), 'white').save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class PrivateMediaTests(TestCase):
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

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username='media_owner', password=PASSWORD
        )
        cls.owner.groups.add(Group.objects.get(name=ADOPTER))
        cls.other_adopter = User.objects.create_user(
            username='media_other', password=PASSWORD
        )
        cls.other_adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(
            username='media_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.admin = User.objects.create_user(
            username='media_admin', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))

        profile = cls.owner.profile
        profile.photo = make_image('profile.jpg')
        profile.save()

        dog = Dog.objects.create(name='MediaDog', status=Dog.ADOPTED)
        interview = InterviewRequest.objects.create(
            adopter=cls.owner,
            dog=dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='เจ้าของ ไฟล์',
            phone='0812345678',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.COMPLETED,
        )
        cls.housing = HousingPhoto.objects.create(
            interview_request=interview, image=make_image('house.jpg')
        )
        result = InterviewResult.objects.create(
            interview_request=interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่าน',
        )
        cls.interview_photo = InterviewPhoto.objects.create(
            result=result, image=make_image('result.jpg')
        )
        contract = AdoptionContract.objects.create(
            interview_request=interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )
        follow_up = FollowUp.objects.create(
            contract=contract,
            day_offset=14,
            due_date=date.today() + timedelta(days=14),
            status=FollowUp.SUBMITTED,
            submitted_at=timezone.now(),
        )
        cls.followup_photo = FollowUpPhoto.objects.create(
            follow_up=follow_up, image=make_image('followup.jpg')
        )
        evaluation = FollowUpEvaluation.objects.create(
            follow_up=follow_up,
            housing_condition='ดี',
            dog_condition='ดี',
        )
        cls.evaluation_photo = FollowUpEvaluationPhoto.objects.create(
            evaluation=evaluation, image=make_image('evaluation.jpg')
        )

    def private_urls(self):
        return [
            reverse('protected_file', args=['profile', self.owner.profile.pk]),
            reverse('protected_file', args=['housing', self.housing.pk]),
            reverse(
                'protected_file', args=['interview', self.interview_photo.pk]
            ),
            reverse(
                'protected_file', args=['followup', self.followup_photo.pk]
            ),
            reverse(
                'protected_file',
                args=['evaluation', self.evaluation_photo.pk],
            ),
        ]

    def test_anonymous_is_redirected_to_login(self):
        for url in self.private_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('login'), response.url)

    def test_other_adopter_gets_403(self):
        self.client.force_login(self.other_adopter)
        for url in self.private_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_owner_can_open_every_private_file(self):
        self.client.force_login(self.owner)
        for url in self.private_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_open_every_private_file(self):
        self.client.force_login(self.staff)
        for url in self.private_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_can_open_profile_but_not_adoption_evidence(self):
        self.client.force_login(self.admin)
        profile_url = reverse(
            'protected_file', args=['profile', self.owner.profile.pk]
        )
        self.assertEqual(self.client.get(profile_url).status_code, 200)

        for url in self.private_urls():
            if url == profile_url:
                continue
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_unknown_kind_returns_404(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('protected_file', args=['dogs', self.housing.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_file_returns_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('protected_file', args=['housing', 999999])
        )
        self.assertEqual(response.status_code, 404)

    def test_private_uploads_get_uuid_filenames(self):
        self.assertRegex(
            self.housing.image.name, r'^interviews/housing/[0-9a-f]{32}\.jpg$'
        )
        self.assertRegex(
            self.interview_photo.image.name,
            r'^interviews/results/[0-9a-f]{32}\.jpg$',
        )
        self.assertRegex(
            self.followup_photo.image.name,
            r'^follow_ups/[0-9a-f]{32}\.jpg$',
        )
        self.assertRegex(
            self.evaluation_photo.image.name,
            r'^follow_up_evaluations/[0-9a-f]{32}\.jpg$',
        )
        self.assertRegex(
            self.owner.profile.photo.name, r'^profiles/[0-9a-f]{32}\.jpg$'
        )

    def test_private_media_is_not_reachable_by_media_url(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            '/media/' + self.owner.profile.photo.name
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_production_uses_x_accel_redirect(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('protected_file', args=['housing', self.housing.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['X-Accel-Redirect'],
            '/protected/' + self.housing.image.name,
        )
        self.assertFalse(response.streaming)
