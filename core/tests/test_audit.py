from django.contrib.auth.models import Group, User
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse

from core.models import Dog, Notification
from core.permissions import ADMIN, STAFF

PASSWORD = 'Str0ngPass!234'


class AuditLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='audit_admin', password=PASSWORD
        )
        cls.admin.groups.add(Group.objects.get(name=ADMIN))
        cls.staff = User.objects.create_user(
            username='audit_staff', password=PASSWORD
        )
        cls.staff.groups.add(Group.objects.get(name=STAFF))

    def dog_edit_data(self, dog, **overrides):
        data = model_to_dict(
            dog,
            fields=(
                'name', 'breed', 'sex', 'age_months', 'size', 'color',
                'description', 'vaccinated', 'sterilized', 'status',
                'intake_date',
            ),
        )
        data['intake_date'] = dog.intake_date.isoformat()
        data.pop('vaccinated', None)
        data.pop('sterilized', None)
        data.update(overrides)
        return data

    def test_notification_history_is_not_shown(self):
        Notification.objects.create(
            user=self.admin, title='แจ้งเตือนทดสอบ', message='ข้อความ'
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_log'))
        model_labels = [
            value for value, _label in response.context['model_choices']
        ]
        self.assertNotIn('core.notification', model_labels)
        self.assertFalse(
            any(
                entry['model_label'] == 'core.notification'
                for entry in response.context['entries']
            )
        )

    def test_business_history_is_still_shown(self):
        Dog.objects.create(name='AuditDog', status=Dog.AVAILABLE)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_log'))
        self.assertTrue(
            any(
                entry['model_label'] == 'core.dog'
                for entry in response.context['entries']
            )
        )

    def test_user_filter_limits_entries_to_that_user(self):
        dog = Dog.objects.create(name='FilterAuditDog', status=Dog.AVAILABLE)
        self.client.force_login(self.staff)
        self.client.post(
            reverse('dog_edit', args=[dog.pk]),
            self.dog_edit_data(dog, name='FilterAuditDogChanged'),
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('audit_log'), {'user': 'audit_staff'}
        )
        entries = response.context['entries']
        self.assertTrue(entries)
        self.assertTrue(all(entry['user'] == 'audit_staff' for entry in entries))

        response = self.client.get(
            reverse('audit_log'), {'user': 'does-not-exist'}
        )
        self.assertEqual(response.context['entries'], [])
