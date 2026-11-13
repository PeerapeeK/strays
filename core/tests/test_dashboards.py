from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AdoptionContract,
    Dog,
    FollowUp,
    HomeVisit,
    InterviewRequest,
    Notification,
)
from core.permissions import ADOPTER, STAFF

PASSWORD = 'Str0ngPass!234'


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adopter = User.objects.create_user(
            username='dashboard_adopter', password=PASSWORD
        )
        cls.adopter.groups.add(Group.objects.get(name=ADOPTER))
        cls.other = User.objects.create_user(
            username='dashboard_other', password=PASSWORD
        )
        cls.other.groups.add(Group.objects.get(name=ADOPTER))
        cls.staff = User.objects.create_user(
            username='dashboard_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))

        cls.dog = Dog.objects.create(name='DashboardDog', status=Dog.ADOPTED)
        cls.interview = InterviewRequest.objects.create(
            adopter=cls.adopter,
            dog=cls.dog,
            scheduled_at=timezone.now() + timedelta(days=2),
            full_name='ผู้รับอุปการะ แดชบอร์ด',
            phone='0812345678',
            address='ที่อยู่',
            status=InterviewRequest.CONFIRMED,
        )
        cls.contract = AdoptionContract.objects.create(
            interview_request=cls.interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )
        cls.follow_up = FollowUp.objects.create(
            contract=cls.contract,
            day_offset=14,
            due_date=date.today() - timedelta(days=1),
            status=FollowUp.PENDING,
        )
        cls.home_visit = HomeVisit.objects.create(
            contract=cls.contract,
            scheduled_at=timezone.now() + timedelta(days=4),
        )
        cls.notification = Notification.objects.create(
            user=cls.adopter,
            title='แจ้งเตือนแดชบอร์ด',
            message='ข้อความ',
        )

        other_dog = Dog.objects.create(
            name='OtherPrivateDog', status=Dog.ADOPTED
        )
        cls.other_interview = InterviewRequest.objects.create(
            adopter=cls.other,
            dog=other_dog,
            scheduled_at=timezone.now() + timedelta(days=2),
            full_name='ข้อมูลส่วนตัวของผู้อื่น',
            phone='0899999999',
            address='ที่อยู่ของผู้อื่น',
            status=InterviewRequest.PENDING,
        )

    def test_adopter_dashboard_surfaces_own_status(self):
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('adopter_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DashboardDog')
        self.assertContains(response, self.contract.contract_no)
        self.assertContains(response, 'เกินกำหนด')
        self.assertContains(response, 'แจ้งเตือนแดชบอร์ด')
        self.assertContains(response, 'นัดตรวจบ้าน')

    def test_adopter_dashboard_does_not_leak_other_adopter(self):
        self.client.force_login(self.adopter)
        response = self.client.get(reverse('adopter_dashboard'))
        self.assertNotContains(response, 'OtherPrivateDog')
        self.assertNotContains(response, 'ข้อมูลส่วนตัวของผู้อื่น')
        self.assertNotContains(response, '0899999999')

    def test_staff_dashboard_surfaces_work_queue(self):
        self.follow_up.status = FollowUp.SUBMITTED
        self.follow_up.submitted_at = timezone.now()
        self.follow_up.save(update_fields=['status', 'submitted_at'])

        self.client.force_login(self.staff)
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ข้อมูลส่วนตัวของผู้อื่น')
        self.assertContains(response, 'DashboardDog')
        self.assertContains(
            response,
            timezone.localtime(self.home_visit.scheduled_at).strftime(
                '%d/%m/%Y'
            ),
        )
        self.assertContains(response, 'รอตรวจ')

    def test_admin_cannot_open_staff_dashboard(self):
        admin = User.objects.create_user(
            username='dashboard_admin', password=PASSWORD
        )
        admin.groups.add(Group.objects.get(name='Admin'))
        self.client.force_login(admin)
        self.assertEqual(
            self.client.get(reverse('staff_dashboard')).status_code, 403
        )
