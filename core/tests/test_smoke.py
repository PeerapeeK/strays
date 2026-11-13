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
    InterviewResult,
)
from core.permissions import ADOPTER, ADMIN, STAFF

from . import login_via_view

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
        cls.dog = Dog.objects.create(name='SmokeDog', status=Dog.AVAILABLE)
        cls.interview = InterviewRequest.objects.create(
            adopter=cls.users[ADOPTER],
            dog=cls.dog,
            scheduled_at=timezone.now() + timedelta(days=3),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0800000000',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.CONFIRMED,
        )

        cls.approved_interview = InterviewRequest.objects.create(
            adopter=cls.users[ADOPTER],
            dog=cls.dog,
            scheduled_at=timezone.now() + timedelta(days=4),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0800000000',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.COMPLETED,
        )
        InterviewResult.objects.create(
            interview_request=cls.approved_interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่านการสัมภาษณ์',
        )

        cls.contract_interview = InterviewRequest.objects.create(
            adopter=cls.users[ADOPTER],
            dog=Dog.objects.create(name='ContractDog', status=Dog.ADOPTED),
            scheduled_at=timezone.now() + timedelta(days=5),
            full_name='ผู้ทดสอบ ระบบ',
            phone='0800000000',
            address='ที่อยู่ทดสอบ',
            status=InterviewRequest.COMPLETED,
        )
        InterviewResult.objects.create(
            interview_request=cls.contract_interview,
            outcome=InterviewResult.PASSED,
            notes='ผ่านการสัมภาษณ์',
        )
        cls.contract = AdoptionContract.objects.create(
            interview_request=cls.contract_interview,
            status=AdoptionContract.ACTIVE,
            start_date=date.today(),
        )
        cls.follow_up = FollowUp.objects.create(
            contract=cls.contract,
            day_offset=14,
            due_date=date.today() + timedelta(days=14),
            status=FollowUp.SUBMITTED,
            submitted_at=timezone.now(),
        )
        cls.home_visit = HomeVisit.objects.create(
            contract=cls.contract,
            scheduled_at=timezone.now() + timedelta(days=7),
        )

    def test_public_urls(self):
        urls = (
            reverse('home'),
            reverse('login'),
            reverse('register'),
            reverse('public_dog_list'),
            reverse('public_dog_detail', args=[self.dog.pk]),
            reverse('privacy'),
            reverse('terms'),
            reverse('healthz'),
            reverse('password_reset'),
            reverse('password_reset_done'),
            reverse('password_reset_complete'),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_urls(self):
        self.assertTrue(login_via_view(self.client, 'smoke_admin', PASSWORD))
        expected = {
            reverse('home'): 200,
            reverse('my_profile'): 200,
            reverse('dashboard'): 302,
            reverse('admin_dashboard'): 200,
            reverse('staff_dashboard'): 403,
            reverse('user_list'): 200,
            reverse('staff_create'): 200,
            reverse('user_edit', args=[self.admin.pk]): 200,
            reverse('admin_user_delete', args=[self.users[ADOPTER].pk]): 302,
            reverse('admin_user_anonymize', args=[self.users[ADOPTER].pk]): 200,
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_list'): 200,
            reverse('dog_create'): 200,
            reverse('dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_edit', args=[self.dog.pk]): 200,
            reverse('staff_interview_list'): 403,
            reverse('staff_interview_result', args=[self.interview.pk]): 403,
            reverse('staff_contract_list'): 403,
            reverse('staff_contract_create', args=[self.approved_interview.pk]): 403,
            reverse('staff_contract_detail', args=[self.contract.pk]): 403,
            reverse('staff_contract_edit', args=[self.contract.pk]): 403,
            reverse('homevisit_create', args=[self.contract.pk]): 403,
            reverse('homevisit_edit', args=[self.home_visit.pk]): 403,
            reverse('staff_home_visit_list'): 403,
            reverse('staff_followup_list'): 403,
            reverse('staff_followup_detail', args=[self.follow_up.pk]): 403,
            reverse('staff_followup_evaluate', args=[self.follow_up.pk]): 403,
            reverse('adoption_stats'): 200,
            reverse('followup_stats'): 200,
            reverse('adoption_stats_csv'): 200,
            reverse('followup_stats_csv'): 200,
            reverse('audit_log'): 200,
            reverse('notification_list'): 200,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_staff_urls(self):
        self.assertTrue(login_via_view(self.client, 'smoke_staff', PASSWORD))
        expected = {
            reverse('home'): 200,
            reverse('my_profile'): 200,
            reverse('dashboard'): 302,
            reverse('staff_dashboard'): 200,
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_list'): 200,
            reverse('dog_create'): 200,
            reverse('dog_detail', args=[self.dog.pk]): 200,
            reverse('dog_edit', args=[self.dog.pk]): 200,
            reverse('staff_interview_list'): 200,
            reverse('staff_interview_result', args=[self.interview.pk]): 200,
            reverse('staff_contract_list'): 200,
            reverse('staff_contract_create', args=[self.approved_interview.pk]): 200,
            reverse('staff_contract_detail', args=[self.contract.pk]): 200,
            reverse('staff_contract_edit', args=[self.contract.pk]): 200,
            reverse('homevisit_create', args=[self.contract.pk]): 200,
            reverse('homevisit_edit', args=[self.home_visit.pk]): 200,
            reverse('staff_home_visit_list'): 200,
            reverse('notification_list'): 200,
            reverse('staff_followup_list'): 200,
            reverse('staff_followup_detail', args=[self.follow_up.pk]): 200,
            reverse('staff_followup_evaluate', args=[self.follow_up.pk]): 200,
            reverse('adoption_stats'): 200,
            reverse('followup_stats'): 200,
            reverse('adoption_stats_csv'): 200,
            reverse('followup_stats_csv'): 200,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_adopter_urls(self):
        self.assertTrue(login_via_view(self.client, 'smoke_adopter', PASSWORD))
        expected = {
            reverse('home'): 200,
            reverse('my_profile'): 200,
            reverse('dashboard'): 302,
            reverse('adopter_dashboard'): 200,
            reverse('public_dog_list'): 200,
            reverse('public_dog_detail', args=[self.dog.pk]): 200,
            reverse('interview_book', args=[self.dog.pk]): 200,
            reverse('interview_list'): 200,
            reverse('interview_detail', args=[self.interview.pk]): 200,
            reverse('contract_list'): 200,
            reverse('contract_detail', args=[self.contract.pk]): 200,
            reverse('followup_list'): 200,
            reverse('followup_detail', args=[self.follow_up.pk]): 200,
            reverse('notification_list'): 200,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_report_and_audit_permissions(self):
        self.assertTrue(
            login_via_view(self.client, 'smoke_adopter', PASSWORD)
        )
        for url in (
            reverse('adoption_stats'),
            reverse('followup_stats'),
            reverse('adoption_stats_csv'),
            reverse('followup_stats_csv'),
            reverse('audit_log'),
            reverse('staff_dashboard'),
            reverse('dog_list'),
            reverse('staff_interview_list'),
        ):
            with self.subTest(role='adopter', url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        self.assertTrue(login_via_view(self.client, 'smoke_staff', PASSWORD))
        self.assertEqual(
            self.client.get(reverse('audit_log')).status_code, 403
        )


class StaffWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username='workspace_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.dog = Dog.objects.create(name='WorkspaceDog', status=Dog.AVAILABLE)

    def setUp(self):
        self.client.force_login(self.staff)

    def test_dashboard_has_heading_welcome_and_tabs(self):
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ระบบจัดการศูนย์พักพิง')
        self.assertContains(response, 'ยินดีต้อนรับ,')
        self.assertContains(response, 'staff-tabbar')
        self.assertContains(response, reverse('dog_list'))
        self.assertContains(response, reverse('staff_interview_list'))
        self.assertContains(response, reverse('staff_home_visit_list'))
        self.assertContains(response, 'ตรวจเยี่ยมบ้าน')
        self.assertContains(response, 'ติดตามผล')
        self.assertContains(response, 'รายงาน')

    def test_dog_list_uses_staff_components_and_active_tab(self):
        response = self.client.get(reverse('dog_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ข้อมูลสุนัขในระบบ')
        self.assertContains(response, 'รายชื่อสุนัขจรจัดที่รอการพิจารณาหรือกำลังหาบ้าน')
        self.assertContains(response, 'เพิ่มข้อมูลสุนัข')
        self.assertContains(response, 'แก้ไขข้อมูล')
        self.assertContains(response, 'staff-tab is-active')

    def test_interview_list_uses_staff_components_and_active_tab(self):
        response = self.client.get(reverse('staff_interview_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'คำขอรับเลี้ยง')
        self.assertContains(response, 'ตรวจสอบและดำเนินการกับคำขอรับเลี้ยงล่าสุด')
        self.assertContains(response, 'staff-tab is-active')

    def test_dog_form_is_a_full_page_with_photo_upload(self):
        response = self.client.get(reverse('dog_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'เพิ่มข้อมูลสุนัข')
        self.assertContains(response, 'name="photo"')
        self.assertNotContains(response, 'name="emoji"')


class HomePageTests(TestCase):
    def test_home_without_dogs_shows_emoji_fallback(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'หาบ้านที่ใช่ ให้เพื่อนสี่ขา')
        self.assertContains(response, 'home-strip')
        self.assertContains(response, '🐶')
        self.assertContains(response, reverse('public_dog_list'))

    def test_home_with_dogs_links_to_each_dog(self):
        dogs = [
            Dog.objects.create(name=f'HomeDog{i}', status=Dog.AVAILABLE)
            for i in range(5)
        ]
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'home-strip')
        for dog in dogs:
            self.assertContains(response, reverse('public_dog_detail', args=[dog.pk]))
        self.assertContains(response, reverse('register'))

    def test_home_with_fewer_than_five_dogs_shows_emoji_fallback(self):
        Dog.objects.create(name='HomeDogOne', status=Dog.AVAILABLE)
        Dog.objects.create(name='HomeDogTwo', status=Dog.AVAILABLE)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'home-strip')
        self.assertContains(response, '🐩')


class PublicPageTests(TestCase):
    def test_anonymous_navbar_has_no_staff_link(self):
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'สำหรับเจ้าหน้าที่')
        self.assertContains(response, 'หน้าหลัก')
        self.assertContains(response, 'ค้นหาน้องหมา')
        self.assertContains(response, 'เข้าสู่ระบบ')
        self.assertContains(response, 'สมัครสมาชิก')

    def test_footer_shows_current_year(self):
        from datetime import date

        response = self.client.get(reverse('home'))
        self.assertContains(
            response, f'© {date.today().year} StrayMatch Platform'
        )

    def test_public_pages_use_straymatch_brand(self):
        for url_name in ('home', 'login', 'privacy'):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'StrayMatch')
            self.assertNotContains(response, 'StayMatch')

    def test_privacy_and_terms_pages(self):
        privacy = self.client.get(reverse('privacy'))
        self.assertEqual(privacy.status_code, 200)
        self.assertContains(privacy, 'PDPA')

        terms = self.client.get(reverse('terms'))
        self.assertEqual(terms.status_code, 200)
        self.assertContains(terms, 'Terms of Service')

    def test_success_message_renders_in_modal(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'modaltest',
                'password1': 'Str0ngPass!234',
                'password2': 'Str0ngPass!234',
                'full_name': 'ผู้ทดสอบ โมดัล',
                'phone': '0812345678',
                'address': '123',
                'pdpa_consent': 'on',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="systemMessageBody"')
        self.assertContains(response, 'สมัครสมาชิกสำเร็จ')


class HomePageNoDogsTests(TestCase):
    def test_home_returns_200_without_dogs(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

