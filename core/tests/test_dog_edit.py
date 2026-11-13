from datetime import date

from django.contrib.auth.models import Group, User
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse

from core.models import Dog
from core.permissions import STAFF

PASSWORD = 'Str0ngPass!234'


class DogEditDateRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username='dog_edit_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))
        cls.intake_date = date(2026, 11, 26)
        cls.dog = Dog.objects.create(
            name='กันสมาย',
            breed='พันธุ์ผสม',
            sex=Dog.FEMALE,
            age_months=24,
            size=Dog.SMALL,
            color='น้ำตาล',
            description='สุนัขทดสอบ',
            vaccinated=True,
            sterilized=True,
            status=Dog.AVAILABLE,
            intake_date=cls.intake_date,
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def edit_data(self, **overrides):
        data = model_to_dict(
            self.dog,
            fields=(
                'name', 'breed', 'sex', 'age_months', 'size', 'color',
                'description', 'vaccinated', 'sterilized', 'status',
                'intake_date',
            ),
        )
        data['intake_date'] = self.intake_date.isoformat()
        if data.get('vaccinated'):
            data['vaccinated'] = 'on'
        else:
            data.pop('vaccinated', None)
        if data.get('sterilized'):
            data['sterilized'] = 'on'
        else:
            data.pop('sterilized', None)
        data.update(overrides)
        return data

    def test_edit_form_prefills_intake_date_in_html5_format(self):
        response = self.client.get(reverse('dog_edit', args=[self.dog.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-11-26"')
        self.assertContains(response, 'name="intake_date"')

    def test_changing_only_name_succeeds_and_keeps_intake_date(self):
        response = self.client.post(
            reverse('dog_edit', args=[self.dog.pk]),
            self.edit_data(name='กันสมายใหม่'),
        )
        self.assertEqual(response.status_code, 302)
        self.dog.refresh_from_db()
        self.assertEqual(self.dog.name, 'กันสมายใหม่')
        self.assertEqual(self.dog.intake_date, self.intake_date)

    def test_intake_date_remains_required(self):
        data = self.edit_data(name='ต้องไม่บันทึก')
        data.pop('intake_date')
        response = self.client.post(
            reverse('dog_edit', args=[self.dog.pk]), data
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('intake_date', response.context['form'].errors)
        self.dog.refresh_from_db()
        self.assertEqual(self.dog.name, 'กันสมาย')
        self.assertEqual(self.dog.intake_date, self.intake_date)
