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
    DEFAULT_CONTRACT_TERMS,
    FOLLOW_UP_DAYS,
    AdoptionContract,
    Dog,
    FollowUp,
    FollowUpEvaluation,
    FollowUpEvaluationPhoto,
    FollowUpPhoto,
    HomeVisit,
    InterviewRequest,
    InterviewResult,
    Notification,
)
from core.permissions import ADOPTER, ADMIN, STAFF
from core.services import activate_contract, create_follow_ups

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


class ContractTestBase(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='contract_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.other_adopter = User.objects.create_user(
            username='contract_other', password=PASSWORD
        )
        cls.other_adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(
            username='contract_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.admin = User.objects.create_user(
            username='contract_admin', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))
        cls.dog = Dog.objects.create(name='ContractTestDog', status=Dog.AVAILABLE)

    def create_interview(self, outcome=InterviewResult.PASSED, adopter=None,
                         status=InterviewRequest.COMPLETED, with_result=True):
        interview = InterviewRequest.objects.create(
            adopter=adopter or self.adopter,
            dog=self.dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ สัญญา',
            phone='0812345678',
            address='123 ถนนทดสอบ',
            status=status,
        )
        if with_result and outcome is not None:
            InterviewResult.objects.create(
                interview_request=interview,
                outcome=outcome,
                notes='ผลการสัมภาษณ์',
            )
        return interview

    def create_contract(self, status=AdoptionContract.ACTIVE, interview=None,
                        start_date=None):
        interview = interview or self.create_interview()
        return AdoptionContract.objects.create(
            interview_request=interview,
            status=status,
            start_date=start_date or date.today(),
        )

    def future_slot(self, days=5, hour=10):
        now = timezone.localtime(timezone.now())
        return (now + timedelta(days=days)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )


class ContractModelAndServiceTests(ContractTestBase):
    def test_contract_no_generated_and_terms_defaulted(self):
        contract = self.create_contract()
        self.assertRegex(contract.contract_no, r'^CON-[A-F0-9]{8}$')
        self.assertEqual(contract.terms, DEFAULT_CONTRACT_TERMS)

    def test_follow_up_service_creates_14_30_90_180_idempotently(self):
        start = date.today()
        contract = self.create_contract(start_date=start)

        created = create_follow_ups(contract)
        self.assertEqual(len(created), 4)
        self.assertEqual(
            set(contract.follow_ups.values_list('day_offset', flat=True)),
            set(FOLLOW_UP_DAYS),
        )
        for follow_up in contract.follow_ups.all():
            self.assertEqual(
                follow_up.due_date,
                start + timedelta(days=follow_up.day_offset),
            )
            self.assertEqual(follow_up.status, FollowUp.PENDING)

        create_follow_ups(contract)
        self.assertEqual(contract.follow_ups.count(), 4)

    def test_activate_contract_marks_dog_adopted_and_notifies(self):
        contract = self.create_contract(status=AdoptionContract.DRAFT)

        self.assertTrue(activate_contract(contract))
        contract.refresh_from_db()
        self.dog.refresh_from_db()
        self.assertEqual(contract.status, AdoptionContract.ACTIVE)
        self.assertEqual(self.dog.status, Dog.ADOPTED)
        self.assertEqual(contract.follow_ups.count(), 4)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='สัญญา'
            ).exists()
        )

        self.assertFalse(activate_contract(contract))
        self.assertEqual(contract.follow_ups.count(), 4)
        self.assertEqual(
            Notification.objects.filter(
                dedupe_key=f'contract-activated-{contract.pk}'
            ).count(),
            1,
        )


class StaffContractTests(ContractTestBase):
    def test_create_contract_only_for_approved_interview(self):
        self.client.force_login(self.staff)
        failed_interview = self.create_interview(outcome=InterviewResult.FAILED)

        response = self.client.post(
            reverse('staff_contract_create', args=[failed_interview.pk]),
            {'start_date': date.today().isoformat(), 'action': 'draft'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AdoptionContract.objects.exists())

    def test_create_contract_draft_and_activate(self):
        interview = self.create_interview()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('staff_contract_create', args=[interview.pk]),
            {
                'terms': 'ข้อสัญญาทดสอบ',
                'start_date': date.today().isoformat(),
                'action': 'draft',
            },
        )
        self.assertEqual(response.status_code, 302)
        contract = AdoptionContract.objects.get()
        self.assertEqual(contract.status, AdoptionContract.DRAFT)
        self.assertEqual(contract.terms, 'ข้อสัญญาทดสอบ')
        self.dog.refresh_from_db()
        self.assertEqual(self.dog.status, Dog.AVAILABLE)
        self.assertEqual(contract.follow_ups.count(), 0)

        response = self.client.post(
            reverse('staff_contract_activate', args=[contract.pk])
        )
        self.assertEqual(response.status_code, 302)
        contract.refresh_from_db()
        self.dog.refresh_from_db()
        self.assertEqual(contract.status, AdoptionContract.ACTIVE)
        self.assertEqual(self.dog.status, Dog.ADOPTED)
        self.assertEqual(contract.follow_ups.count(), 4)

    def test_create_and_activate_in_one_step(self):
        interview = self.create_interview()
        self.client.force_login(self.staff)
        self.client.post(
            reverse('staff_contract_create', args=[interview.pk]),
            {'action': 'activate'},
        )
        contract = AdoptionContract.objects.get()
        self.assertEqual(contract.status, AdoptionContract.ACTIVE)
        self.assertEqual(contract.terms, DEFAULT_CONTRACT_TERMS)
        self.assertEqual(contract.start_date, timezone.localdate())
        self.assertEqual(contract.follow_ups.count(), 4)

    def test_staff_edit_updates_contract(self):
        contract = self.create_contract()
        self.client.force_login(self.staff)
        self.client.post(
            reverse('staff_contract_edit', args=[contract.pk]),
            {'terms': 'ข้อสัญญาแก้ไข', 'start_date': date.today().isoformat()},
        )
        contract.refresh_from_db()
        self.assertEqual(contract.terms, 'ข้อสัญญาแก้ไข')

    def test_contract_list_filters(self):
        contract = self.create_contract()
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('staff_contract_list'), {'status': AdoptionContract.ACTIVE}
        )
        self.assertContains(response, contract.contract_no)
        response = self.client.get(
            reverse('staff_contract_list'), {'status': AdoptionContract.DRAFT}
        )
        self.assertNotContains(response, contract.contract_no)


class AdopterContractTests(ContractTestBase):
    def test_contract_list_and_detail_are_limited_to_owner(self):
        contract = self.create_contract()
        self.client.force_login(self.other_adopter)
        response = self.client.get(reverse('contract_list'))
        self.assertNotContains(response, contract.contract_no)
        self.assertEqual(
            self.client.get(reverse('contract_detail', args=[contract.pk])).status_code,
            404,
        )

        self.client.force_login(self.adopter)
        response = self.client.get(reverse('contract_list'))
        self.assertContains(response, contract.contract_no)
        response = self.client.get(reverse('contract_detail', args=[contract.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contract.contract_no)

    def test_adopter_acknowledges_active_contract(self):
        contract = self.create_contract()
        self.client.force_login(self.adopter)
        self.client.post(reverse('contract_acknowledge', args=[contract.pk]))
        contract.refresh_from_db()
        self.assertIsNotNone(contract.acknowledged_at)
        self.assertTrue(
            Notification.objects.filter(
                user=self.staff, title__contains='ยอมรับสัญญา'
            ).exists()
        )

    def test_adopter_cannot_acknowledge_draft_contract(self):
        contract = self.create_contract(status=AdoptionContract.DRAFT)
        self.client.force_login(self.adopter)
        self.client.post(reverse('contract_acknowledge', args=[contract.pk]))
        contract.refresh_from_db()
        self.assertIsNone(contract.acknowledged_at)

    def test_adopter_cannot_acknowledge_another_users_contract(self):
        contract = self.create_contract()
        self.client.force_login(self.other_adopter)
        response = self.client.post(
            reverse('contract_acknowledge', args=[contract.pk])
        )
        self.assertEqual(response.status_code, 404)
        contract.refresh_from_db()
        self.assertIsNone(contract.acknowledged_at)


class FollowUpTests(ContractTestBase):
    def test_adopter_submits_follow_up_with_photos(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        self.client.force_login(self.adopter)

        response = self.client.post(
            reverse('followup_submit', args=[follow_up.pk]),
            {
                'notes': 'ส่งรูปถ่ายบ้าน',
                'photos': [make_image('f1.jpg'), make_image('f2.png')],
            },
        )
        self.assertEqual(response.status_code, 302)
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUp.SUBMITTED)
        self.assertIsNotNone(follow_up.submitted_at)
        self.assertEqual(follow_up.notes, 'ส่งรูปถ่ายบ้าน')
        self.assertEqual(FollowUpPhoto.objects.filter(follow_up=follow_up).count(), 2)
        self.assertTrue(
            Notification.objects.filter(
                user=self.staff, title__contains='ติดตามผล'
            ).exists()
        )

    def test_follow_up_requires_photos(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        self.client.force_login(self.adopter)
        response = self.client.post(
            reverse('followup_submit', args=[follow_up.pk]), {'photos': []}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1-5 รูป')
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUp.PENDING)

    def test_follow_up_cannot_be_submitted_twice(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        self.client.force_login(self.adopter)
        self.client.post(
            reverse('followup_submit', args=[follow_up.pk]),
            {'photos': [make_image()]},
        )
        self.client.post(
            reverse('followup_submit', args=[follow_up.pk]),
            {'photos': [make_image()]},
        )
        self.assertEqual(FollowUpPhoto.objects.filter(follow_up=follow_up).count(), 1)

    def test_follow_up_is_limited_to_adopter(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        self.client.force_login(self.other_adopter)
        self.assertEqual(
            self.client.get(reverse('followup_detail', args=[follow_up.pk])).status_code,
            404,
        )
        response = self.client.post(
            reverse('followup_submit', args=[follow_up.pk]),
            {'photos': [make_image()]},
        )
        self.assertEqual(response.status_code, 404)

    def test_staff_records_evaluation_with_photos(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        follow_up.status = FollowUp.SUBMITTED
        follow_up.submitted_at = timezone.now()
        follow_up.save(update_fields=['status', 'submitted_at'])

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('staff_followup_evaluate', args=[follow_up.pk]),
            {
                'housing_condition': 'บ้านสะอาดและปลอดภัย',
                'dog_condition': 'สุนัขแข็งแรง',
                'notes': 'ผ่านการประเมิน',
                'photos': [make_image('e1.jpg'), make_image('e2.jpg')],
            },
        )
        self.assertEqual(response.status_code, 302)
        evaluation = FollowUpEvaluation.objects.get(follow_up=follow_up)
        self.assertEqual(evaluation.evaluator, self.staff)
        self.assertEqual(
            FollowUpEvaluationPhoto.objects.filter(evaluation=evaluation).count(), 2
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='ผลประเมิน'
            ).exists()
        )

    def test_evaluation_requires_submitted_follow_up_and_photos(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('staff_followup_evaluate', args=[follow_up.pk]),
            {'housing_condition': 'ดี', 'dog_condition': 'ดี', 'photos': [make_image()]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FollowUpEvaluation.objects.exists())

        follow_up.status = FollowUp.SUBMITTED
        follow_up.submitted_at = timezone.now()
        follow_up.save(update_fields=['status', 'submitted_at'])
        response = self.client.post(
            reverse('staff_followup_evaluate', args=[follow_up.pk]),
            {'housing_condition': 'ดี', 'dog_condition': 'ดี', 'photos': []},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1-5 รูป')
        self.assertFalse(FollowUpEvaluation.objects.exists())


class HomeVisitTests(ContractTestBase):
    def test_staff_creates_home_visit_and_notifies_adopter(self):
        contract = self.create_contract()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('homevisit_create', args=[contract.pk]),
            {
                'scheduled_at': self.future_slot().strftime('%Y-%m-%dT%H:%M'),
                'notes': 'ตรวจบ้านครั้งแรก',
            },
        )
        self.assertEqual(response.status_code, 302)
        home_visit = HomeVisit.objects.get(contract=contract)
        self.assertEqual(home_visit.status, HomeVisit.SCHEDULED)
        self.assertEqual(home_visit.created_by, self.staff)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='นัดตรวจบ้าน'
            ).exists()
        )

    def test_staff_modifies_home_visit_and_notifies_adopter(self):
        contract = self.create_contract()
        home_visit = HomeVisit.objects.create(
            contract=contract, scheduled_at=self.future_slot()
        )
        self.client.force_login(self.staff)
        new_time = self.future_slot(days=8)
        self.client.post(
            reverse('homevisit_edit', args=[home_visit.pk]),
            {'scheduled_at': new_time.strftime('%Y-%m-%dT%H:%M'), 'notes': 'เลื่อนเวลา'},
        )
        home_visit.refresh_from_db()
        self.assertEqual(home_visit.scheduled_at, new_time)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='แก้ไขนัดตรวจบ้าน'
            ).exists()
        )

    def test_adopter_requests_reschedule_and_staff_approves(self):
        contract = self.create_contract()
        home_visit = HomeVisit.objects.create(
            contract=contract, scheduled_at=self.future_slot()
        )
        requested = self.future_slot(days=9)

        self.client.force_login(self.adopter)
        self.client.post(
            reverse('homevisit_request_reschedule', args=[home_visit.pk]),
            {
                'requested_scheduled_at': requested.strftime('%Y-%m-%dT%H:%M'),
                'reason': 'ติดธุระ',
            },
        )
        home_visit.refresh_from_db()
        self.assertEqual(home_visit.status, HomeVisit.RESCHEDULE_REQUESTED)
        self.assertEqual(home_visit.requested_scheduled_at, requested)
        self.assertEqual(home_visit.reschedule_reason, 'ติดธุระ')
        self.assertTrue(
            Notification.objects.filter(
                user=self.staff, title__contains='ขอเลื่อนนัด'
            ).exists()
        )

        self.client.force_login(self.staff)
        self.client.post(reverse('homevisit_approve', args=[home_visit.pk]))
        home_visit.refresh_from_db()
        self.assertEqual(home_visit.status, HomeVisit.APPROVED)
        self.assertEqual(home_visit.scheduled_at, requested)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='อนุมัติ'
            ).exists()
        )

    def test_staff_denies_reschedule(self):
        contract = self.create_contract()
        home_visit = HomeVisit.objects.create(
            contract=contract,
            scheduled_at=self.future_slot(),
            status=HomeVisit.RESCHEDULE_REQUESTED,
            requested_scheduled_at=self.future_slot(days=9),
            reschedule_reason='ติดธุระ',
            reschedule_requested_at=timezone.now(),
        )
        self.client.force_login(self.staff)
        self.client.post(reverse('homevisit_deny', args=[home_visit.pk]))
        home_visit.refresh_from_db()
        self.assertEqual(home_visit.status, HomeVisit.DENIED)
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, title__contains='ปฏิเสธ'
            ).exists()
        )

    def test_adopter_cannot_reschedule_another_users_home_visit(self):
        contract = self.create_contract()
        home_visit = HomeVisit.objects.create(
            contract=contract, scheduled_at=self.future_slot()
        )
        self.client.force_login(self.other_adopter)
        response = self.client.post(
            reverse('homevisit_request_reschedule', args=[home_visit.pk]),
            {
                'requested_scheduled_at': self.future_slot(days=9).strftime(
                    '%Y-%m-%dT%H:%M'
                ),
                'reason': 'ทดสอบ',
            },
        )
        self.assertEqual(response.status_code, 404)
        home_visit.refresh_from_db()
        self.assertEqual(home_visit.status, HomeVisit.SCHEDULED)


class ContractPermissionTests(ContractTestBase):
    def test_adopter_cannot_access_staff_contract_pages(self):
        contract = self.create_contract()
        self.client.force_login(self.adopter)
        for url in (
            reverse('staff_contract_list'),
            reverse('staff_contract_detail', args=[contract.pk]),
            reverse('staff_contract_edit', args=[contract.pk]),
            reverse('staff_followup_list'),
            reverse('homevisit_create', args=[contract.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_staff_cannot_access_adopter_contract_pages(self):
        contract = self.create_contract()
        follow_up = create_follow_ups(contract)[0]
        self.client.force_login(self.staff)
        for url in (
            reverse('contract_list'),
            reverse('contract_detail', args=[contract.pk]),
            reverse('followup_list'),
            reverse('followup_detail', args=[follow_up.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
