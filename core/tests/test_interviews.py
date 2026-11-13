import io
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import (
    AdoptionContract,
    Assessment,
    Dog,
    HousingPhoto,
    InterviewPhoto,
    InterviewRequest,
    InterviewResult,
    Notification,
    ShelterSettings,
    notify,
)
from core.permissions import ADOPTER, ADMIN, STAFF

PASSWORD = 'Str0ngPass!234'


def make_image(name='photo.jpg'):
    buffer = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(buffer, format='JPEG')
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


class InterviewTestBase(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='interview_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.other_adopter = User.objects.create_user(
            username='other_adopter', password=PASSWORD
        )
        cls.other_adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(
            username='interview_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.admin = User.objects.create_user(
            username='interview_admin', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))

        for user in (cls.adopter, cls.other_adopter):
            profile = user.profile
            profile.full_name = 'ผู้ทดสอบ ระบบ'
            profile.phone = '0812345678'
            profile.address = '123 ถนนทดสอบ'
            profile.pdpa_consent_at = timezone.now()
            profile.save()

        ShelterSettings.load()
        cls.dog = Dog.objects.create(name='InterviewDog', status=Dog.AVAILABLE)
        cls.unavailable_dog = Dog.objects.create(
            name='UnavailableDog', status=Dog.UNAVAILABLE
        )

    def future_slot(self, days=3, hour=10, minute=0):
        now = timezone.localtime(timezone.now())
        return (now + timedelta(days=days)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

    def booking_data(self, **overrides):
        data = {
            'full_name': 'ผู้ทดสอบ ระบบ',
            'phone': '0812345678',
            'address_detail': '123 ถนนทดสอบ',
            'province': 'กรุงเทพมหานคร',
            'district': 'พระนคร',
            'subdistrict': 'พระบรมมหาราชวัง',
            'postal_code': '10200',
            'housing_type': Assessment.OWN,
            'household_members': '2',
            'experience': 'เคยเลี้ยงสุนัข 5 ปี',
            'motivation': 'ต้องการให้สุนัขมีบ้านที่อบอุ่น',
            'agree_home_visit': 'on',
            'scheduled_at': self.future_slot().strftime('%Y-%m-%dT%H:%M'),
            'housing_photos': [make_image()],
        }
        data.update(overrides)
        return data

    def create_interview(self, adopter=None, status=InterviewRequest.PENDING,
                         scheduled_at=None, **overrides):
        values = {
            'adopter': adopter or self.adopter,
            'dog': self.dog,
            'scheduled_at': scheduled_at or self.future_slot(),
            'full_name': 'ผู้ทดสอบ ระบบ',
            'phone': '0812345678',
            'address': '123 ถนนทดสอบ',
            'status': status,
        }
        values.update(overrides)
        return InterviewRequest.objects.create(**values)


class InterviewBookingTests(InterviewTestBase):
    def test_booking_creates_request_assessment_photos_and_notification(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(housing_photos=[make_image('a.jpg'), make_image('b.png')]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        interview = InterviewRequest.objects.get()
        self.assertRegex(interview.code, r'^INT-[A-F0-9]{8}$')
        self.assertEqual(interview.status, InterviewRequest.PENDING)
        self.assertEqual(interview.adopter, self.adopter)
        self.assertEqual(interview.dog, self.dog)
        self.assertTrue(Assessment.objects.filter(interview_request=interview).exists())
        self.assertEqual(HousingPhoto.objects.filter(interview_request=interview).count(), 2)
        self.assertTrue(Notification.objects.filter(user=self.adopter).exists())
        self.assertContains(response, interview.code)

    def test_booking_updates_profile_personal_data(self):
        self.client.force_login(self.adopter)
        self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(full_name='ชื่อใหม่ ทดสอบ', phone='0899999999'),
        )
        self.adopter.profile.refresh_from_db()
        self.assertEqual(self.adopter.profile.full_name, 'ชื่อใหม่ ทดสอบ')
        self.assertEqual(self.adopter.profile.phone, '0899999999')

    def test_booking_requires_pdpa_consent_when_not_given(self):
        profile = self.adopter.profile
        profile.pdpa_consent_at = None
        profile.save(update_fields=['pdpa_consent_at'])
        self.client.force_login(self.adopter)

        data = self.booking_data(full_name='ข้อมูลที่ต้องคงอยู่')
        response = self.client.post(reverse('interview_book', args=[self.dog.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ข้อมูลที่ต้องคงอยู่')
        self.assertContains(response, 'จำเป็นต้องยินยอม')
        self.assertFalse(InterviewRequest.objects.exists())

        data = self.booking_data(full_name='ข้อมูลที่ต้องคงอยู่', pdpa_consent='on')
        self.client.post(reverse('interview_book', args=[self.dog.pk]), data)
        self.assertEqual(InterviewRequest.objects.count(), 1)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.pdpa_consent_at)

    def test_booking_rejects_past_datetime(self):
        self.client.force_login(self.adopter)
        past = timezone.localtime(timezone.now()) - timedelta(days=1)
        data = self.booking_data(scheduled_at=past.strftime('%Y-%m-%dT%H:%M'))
        response = self.client.post(reverse('interview_book', args=[self.dog.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'อนาคต')
        self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_rejects_time_outside_opening_hours(self):
        self.client.force_login(self.adopter)
        for hour in (7, 19):
            with self.subTest(hour=hour):
                data = self.booking_data(
                    scheduled_at=self.future_slot(hour=hour).strftime('%Y-%m-%dT%H:%M')
                )
                response = self.client.post(
                    reverse('interview_book', args=[self.dog.pk]), data
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'ช่วงเปิดทำการ')
                self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_allows_slot_farther_than_seven_days(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(
                scheduled_at=self.future_slot(days=20).strftime(
                    '%Y-%m-%dT%H:%M'
                )
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InterviewRequest.objects.count(), 1)

    @override_settings(INTERVIEW_BOOKING_HORIZON_DAYS=30)
    def test_booking_rejects_beyond_configured_horizon(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(
                scheduled_at=self.future_slot(days=31).strftime(
                    '%Y-%m-%dT%H:%M'
                )
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ล่วงหน้าได้ไม่เกิน 30 วัน')
        self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_rejects_unaligned_minute(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(
                scheduled_at=self.future_slot(minute=5).strftime(
                    '%Y-%m-%dT%H:%M'
                )
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ตรงกับช่วงเวลานัดหมาย')
        self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_accepts_last_slot_before_closing(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(
                scheduled_at=self.future_slot(hour=17).strftime(
                    '%Y-%m-%dT%H:%M'
                )
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InterviewRequest.objects.count(), 1)

    def test_booking_rejects_taken_slot(self):
        slot = self.future_slot()
        self.create_interview(scheduled_at=slot)
        self.client.force_login(self.adopter)
        data = self.booking_data(scheduled_at=slot.strftime('%Y-%m-%dT%H:%M'))
        response = self.client.post(reverse('interview_book', args=[self.dog.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'มีผู้จองแล้ว')
        self.assertEqual(InterviewRequest.objects.count(), 1)

    def test_cancelled_slot_can_be_booked_again(self):
        slot = self.future_slot()
        self.create_interview(scheduled_at=slot, status=InterviewRequest.CANCELLED)
        self.client.force_login(self.adopter)
        data = self.booking_data(scheduled_at=slot.strftime('%Y-%m-%dT%H:%M'))
        self.client.post(reverse('interview_book', args=[self.dog.pk]), data)
        self.assertEqual(InterviewRequest.objects.count(), 2)

    def test_booking_requires_one_to_five_housing_photos(self):
        self.client.force_login(self.adopter)
        for count in (0, 6):
            with self.subTest(count=count):
                data = self.booking_data(
                    housing_photos=[make_image(f'{i}.jpg') for i in range(count)]
                )
                response = self.client.post(
                    reverse('interview_book', args=[self.dog.pk]), data
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '1-5 รูป')
                self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_rejects_non_image_file(self):
        self.client.force_login(self.adopter)
        bad_file = SimpleUploadedFile(
            'bad.exe', b'MZ executable', content_type='application/octet-stream'
        )
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(housing_photos=[bad_file]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_form_groups_fields_and_uses_structured_address(self):
        self.client.force_login(self.adopter)
        response = self.client.get(
            reverse('interview_book', args=[self.dog.pk])
        )
        self.assertEqual(response.status_code, 200)
        for text in (
            'ข้อมูลผู้สมัคร',
            'ข้อมูลติดต่อและที่อยู่อาศัย',
            'ข้อมูลที่พักอาศัย',
            'แบบประเมินความพร้อม',
            'รูปภาพที่อยู่อาศัย',
            'วันและเวลาสัมภาษณ์',
            'การยืนยันและ PDPA',
        ):
            with self.subTest(text=text):
                self.assertContains(response, text)
        for field_id in (
            'id_province',
            'id_district',
            'id_subdistrict',
            'id_postal_code',
            'id_address_detail',
        ):
            with self.subTest(field=field_id):
                self.assertContains(response, f'id="{field_id}"')

    def test_booking_stores_structured_address(self):
        self.client.force_login(self.adopter)
        self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(),
        )
        interview = InterviewRequest.objects.get()
        self.assertEqual(interview.province, 'กรุงเทพมหานคร')
        self.assertEqual(interview.district, 'พระนคร')
        self.assertEqual(interview.subdistrict, 'พระบรมมหาราชวัง')
        self.assertEqual(interview.postal_code, '10200')
        self.assertIn('123 ถนนทดสอบ', interview.address)
        self.assertIn('กรุงเทพมหานคร', interview.address)
        self.assertEqual(interview.full_address, interview.address)

    def test_booking_rejects_mismatched_postal_code(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(postal_code='99999'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ไม่สอดคล้องกัน')
        self.assertFalse(InterviewRequest.objects.exists())

    def test_booking_rejects_district_from_another_province(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.dog.pk]),
            self.booking_data(district='เมืองเชียงใหม่'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InterviewRequest.objects.exists())

    def test_legacy_address_without_structured_fields_still_displays(self):
        interview = self.create_interview(address='ที่อยู่เดิมแบบข้อความ')
        self.client.force_login(self.adopter)
        response = self.client.get(
            reverse('interview_detail', args=[interview.pk])
        )
        self.assertContains(response, 'ที่อยู่เดิมแบบข้อความ')
        self.assertEqual(interview.full_address, 'ที่อยู่เดิมแบบข้อความ')

    def test_cannot_book_unavailable_dog(self):
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_book', args=[self.unavailable_dog.pk]),
            self.booking_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(InterviewRequest.objects.exists())


class AdopterInterviewViewTests(InterviewTestBase):
    def test_list_shows_only_own_requests(self):
        own = self.create_interview()
        other = self.create_interview(adopter=self.other_adopter)
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('interview_list'))
        self.assertContains(response, own.code)
        self.assertNotContains(response, other.code)

    def test_detail_is_limited_to_owner(self):
        interview = self.create_interview()
        self.client.force_login(self.other_adopter)
        self.assertEqual(
            self.client.get(reverse('interview_detail', args=[interview.pk])).status_code,
            404,
        )
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('interview_detail', args=[interview.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, interview.code)

    def test_cancel_allowed_at_least_24_hours_before(self):
        interview = self.create_interview(
            scheduled_at=timezone.now() + timedelta(hours=48)
        )
        self.client.force_login(self.adopter)
        self.client.post(reverse('interview_cancel', args=[interview.pk]))
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.CANCELLED)

    def test_cancel_rejected_within_24_hours(self):
        interview = self.create_interview(
            scheduled_at=timezone.now() + timedelta(hours=2)
        )
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('interview_cancel', args=[interview.pk]), follow=True
        )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.PENDING)
        self.assertContains(response, '24 ชั่วโมง')

    def test_confirm_attendance_only_for_confirmed_request(self):
        pending = self.create_interview(status=InterviewRequest.PENDING)
        self.client.force_login(self.adopter)
        self.client.post(reverse('interview_confirm_attendance', args=[pending.pk]))
        pending.refresh_from_db()
        self.assertIsNone(pending.attendance_confirmed_at)

        confirmed = self.create_interview(status=InterviewRequest.CONFIRMED)
        self.client.post(reverse('interview_confirm_attendance', args=[confirmed.pk]))
        confirmed.refresh_from_db()
        self.assertIsNotNone(confirmed.attendance_confirmed_at)

    def test_adopter_cannot_use_staff_interview_pages(self):
        self.client.force_login(self.adopter)
        self.assertEqual(
            self.client.get(reverse('staff_interview_list')).status_code, 403
        )


class StaffInterviewViewTests(InterviewTestBase):
    def test_staff_list_filters_by_status_and_query(self):
        pending = self.create_interview()
        confirmed = self.create_interview(status=InterviewRequest.CONFIRMED)
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('staff_interview_list'), {'status': InterviewRequest.PENDING}
        )
        self.assertContains(response, pending.code)
        self.assertNotContains(response, confirmed.code)

        response = self.client.get(
            reverse('staff_interview_list'), {'q': pending.code}
        )
        self.assertContains(response, pending.code)
        self.assertNotContains(response, confirmed.code)

    def test_staff_confirm_changes_status_and_notifies(self):
        interview = self.create_interview()
        self.client.force_login(self.staff)
        self.client.post(reverse('staff_interview_confirm', args=[interview.pk]))
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.CONFIRMED)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='ยืนยัน'
            ).exists()
        )

    def test_staff_reject_requires_reason(self):
        interview = self.create_interview()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('staff_interview_reject', args=[interview.pk]),
            {'reason': ''},
            follow=True,
        )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.PENDING)
        self.assertContains(response, 'เหตุผลการปฏิเสธ')

        self.client.post(
            reverse('staff_interview_reject', args=[interview.pk]),
            {'reason': 'ข้อมูลไม่ครบถ้วน'},
        )
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.REJECTED)
        self.assertEqual(interview.reject_reason, 'ข้อมูลไม่ครบถ้วน')
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='ปฏิเสธ'
            ).exists()
        )

    def test_record_result_completes_request_and_notifies(self):
        interview = self.create_interview(status=InterviewRequest.CONFIRMED)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('staff_interview_result', args=[interview.pk]),
            {
                'outcome': InterviewResult.PASSED,
                'notes': 'ผู้สมัครผ่านการสัมภาษณ์',
                'photos': [make_image('r1.jpg'), make_image('r2.jpg')],
            },
        )
        self.assertEqual(response.status_code, 302)
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.COMPLETED)
        result = InterviewResult.objects.get(interview_request=interview)
        self.assertEqual(result.outcome, InterviewResult.PASSED)
        self.assertEqual(result.recorded_by, self.staff)
        self.assertEqual(InterviewPhoto.objects.filter(result=result).count(), 2)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title='ผลการสัมภาษณ์'
            ).exists()
        )

    def test_record_result_requires_photos(self):
        interview = self.create_interview(status=InterviewRequest.CONFIRMED)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('staff_interview_result', args=[interview.pk]),
            {
                'outcome': InterviewResult.PASSED,
                'notes': 'ผ่าน',
                'photos': [],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1-5 รูป')
        interview.refresh_from_db()
        self.assertEqual(interview.status, InterviewRequest.CONFIRMED)
        self.assertFalse(InterviewResult.objects.exists())

    def test_record_result_only_for_confirmed_request(self):
        interview = self.create_interview(status=InterviewRequest.PENDING)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('staff_interview_result', args=[interview.pk]),
            {
                'outcome': InterviewResult.PASSED,
                'notes': 'ผ่าน',
                'photos': [make_image()],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(InterviewResult.objects.exists())

    def test_non_staff_cannot_access_staff_interview_pages(self):
        interview = self.create_interview()
        self.client.force_login(self.adopter)
        for url in (
            reverse('staff_interview_list'),
            reverse('staff_interview_result', args=[interview.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_staff_cannot_access_adopter_interview_pages(self):
        interview = self.create_interview()
        self.client.force_login(self.staff)
        for url in (
            reverse('interview_list'),
            reverse('interview_detail', args=[interview.pk]),
            reverse('interview_book', args=[self.dog.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class StaffInterviewFilterTests(InterviewTestBase):
    def setUp(self):
        self.client.force_login(self.staff)

    def test_filters_by_date_range(self):
        near = self.create_interview(scheduled_at=self.future_slot(days=2))
        far = self.create_interview(scheduled_at=self.future_slot(days=12))
        response = self.client.get(
            reverse('staff_interview_list'),
            {
                'date_from': self.future_slot(days=1).date().isoformat(),
                'date_to': self.future_slot(days=5).date().isoformat(),
            },
        )
        self.assertContains(response, near.code)
        self.assertNotContains(response, far.code)

    def test_filters_by_dog_name(self):
        other_dog = Dog.objects.create(name='FilterOtherDog', status=Dog.AVAILABLE)
        matching = self.create_interview()
        hidden = self.create_interview(dog=other_dog)
        response = self.client.get(
            reverse('staff_interview_list'), {'dog': 'FilterOtherDog'}
        )
        self.assertContains(response, hidden.code)
        self.assertNotContains(response, matching.code)

    def test_filters_upcoming(self):
        upcoming = self.create_interview(
            status=InterviewRequest.CONFIRMED,
            scheduled_at=timezone.now() + timedelta(days=2),
        )
        past = self.create_interview(
            status=InterviewRequest.CONFIRMED,
            scheduled_at=timezone.now() - timedelta(days=2),
        )
        response = self.client.get(
            reverse('staff_interview_list'), {'upcoming': '1'}
        )
        self.assertContains(response, upcoming.code)
        self.assertNotContains(response, past.code)

    def test_filters_cancelled_status(self):
        cancelled = self.create_interview(
            status=InterviewRequest.CANCELLED
        )
        pending = self.create_interview(status=InterviewRequest.PENDING)
        response = self.client.get(
            reverse('staff_interview_list'),
            {'status': InterviewRequest.CANCELLED},
        )
        self.assertContains(response, cancelled.code)
        self.assertNotContains(response, pending.code)

    def test_adopter_cannot_use_filtered_staff_list(self):
        self.client.force_login(self.adopter)
        response = self.client.get(
            reverse('staff_interview_list'), {'status': 'pending'}
        )
        self.assertEqual(response.status_code, 403)


class StaffInterviewActionVisibilityTests(InterviewTestBase):
    def setUp(self):
        self.client.force_login(self.staff)

    def actions_response(self, interview):
        return self.client.get(
            reverse('staff_interview_list'), {'q': interview.code}
        )

    def test_pending_request_shows_review_confirm_and_reject_only(self):
        interview = self.create_interview(status=InterviewRequest.PENDING)
        response = self.actions_response(interview)

        self.assertContains(response, 'data-action="review"')
        self.assertContains(response, 'data-action="confirm"')
        self.assertContains(response, 'data-action="reject"')
        self.assertNotContains(response, 'data-action="result"')
        self.assertNotContains(response, 'data-action="contract"')

    def test_confirmed_request_shows_review_and_result_only(self):
        interview = self.create_interview(status=InterviewRequest.CONFIRMED)
        response = self.actions_response(interview)

        self.assertContains(response, 'data-action="review"')
        self.assertContains(response, 'data-action="result"')
        self.assertNotContains(response, 'data-action="confirm"')
        self.assertNotContains(response, 'data-action="reject"')
        self.assertNotContains(response, 'data-action="contract"')

    def test_rejected_and_cancelled_requests_show_review_only(self):
        for status in (InterviewRequest.REJECTED, InterviewRequest.CANCELLED):
            with self.subTest(status=status):
                interview = self.create_interview(status=status)
                response = self.actions_response(interview)
                self.assertContains(response, 'data-action="review"')
                for action in ('confirm', 'reject', 'result', 'contract'):
                    self.assertNotContains(
                        response, f'data-action="{action}"'
                    )

    def test_failed_result_shows_review_only(self):
        interview = self.create_interview(status=InterviewRequest.COMPLETED)
        InterviewResult.objects.create(
            interview_request=interview,
            outcome=InterviewResult.FAILED,
            notes='ไม่ผ่าน',
        )
        response = self.actions_response(interview)

        self.assertContains(response, 'data-action="review"')
        self.assertNotContains(response, 'data-action="result"')
        self.assertNotContains(response, 'data-action="contract"')

    def test_approved_result_without_contract_shows_contract_action(self):
        interview = self.create_interview(status=InterviewRequest.COMPLETED)
        InterviewResult.objects.create(
            interview_request=interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่าน',
        )
        response = self.actions_response(interview)

        self.assertContains(response, 'data-action="review"')
        self.assertContains(response, 'data-action="contract"')
        self.assertNotContains(response, 'data-action="result"')
        self.assertNotContains(response, 'data-action="confirm"')
        self.assertNotContains(response, 'data-action="reject"')

    def test_approved_result_with_contract_hides_contract_action(self):
        interview = self.create_interview(status=InterviewRequest.COMPLETED)
        InterviewResult.objects.create(
            interview_request=interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่าน',
        )
        AdoptionContract.objects.create(interview_request=interview)
        response = self.actions_response(interview)

        self.assertContains(response, 'data-action="review"')
        self.assertNotContains(response, 'data-action="contract"')

    def test_adopter_gets_403_on_staff_workspace_pages(self):
        self.client.force_login(self.adopter)
        for url in (
            reverse('staff_dashboard'),
            reverse('dog_list'),
            reverse('staff_interview_list'),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class NotificationHelperTests(InterviewTestBase):
    def test_notify_creates_pending_row_only(self):
        notification = notify(
            self.adopter, 'หัวข้อทดสอบ', 'ข้อความทดสอบ', dedupe_key='test-key'
        )
        self.assertEqual(notification.status, Notification.PENDING)
        self.assertEqual(notification.attempts, 0)
        self.assertIsNotNone(notification.next_attempt_at)
        self.assertEqual(Notification.objects.count(), 1)

        duplicate = notify(
            self.adopter, 'หัวข้อใหม่', 'ข้อความใหม่', dedupe_key='test-key'
        )
        self.assertEqual(duplicate.pk, notification.pk)
        self.assertEqual(Notification.objects.count(), 1)
