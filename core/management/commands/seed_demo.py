from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ShelterSettings
from core.permissions import ADOPTER, ADMIN, ROLE_NAMES, STAFF

PASSWORD = 'demo1234'


class Command(BaseCommand):
    help = 'Create demo users and roles (idempotent).'

    def handle(self, *args, **options):
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in ROLE_NAMES}

        self._upsert_user(
            'admin',
            groups[ADMIN],
            full_name='ผู้ดูแลระบบ',
            phone='0800000000',
            is_superuser=True,
            is_staff=True,
        )

        self._upsert_user(
            'staff1',
            groups[STAFF],
            full_name='เจ้าหน้าที่ศูนย์ หนึ่ง',
            phone='0811111111',
        )
        self._upsert_user(
            'staff2',
            groups[STAFF],
            full_name='เจ้าหน้าที่ศูนย์ สอง',
            phone='0822222222',
        )

        for index in range(1, 4):
            self._upsert_user(
                f'adopter{index}',
                groups[ADOPTER],
                full_name=f'ผู้รับอุปการะ {index}',
                phone=f'08999999{index:02d}',
                pdpa_consent=True,
            )

        ShelterSettings.load()

        self.stdout.write(self.style.SUCCESS(
            'Seed complete: admin, staff1, staff2, adopter1-3 (password: demo1234)'
        ))

    def _upsert_user(self, username, group, *, full_name, phone, address='',
                     pdpa_consent=False, is_superuser=False, is_staff=False):
        user, created = User.objects.get_or_create(username=username)
        user.is_superuser = is_superuser
        user.is_staff = is_staff
        user.is_active = True
        user.set_password(PASSWORD)
        user.save()

        user.groups.set([group])

        profile = user.profile
        profile.full_name = full_name
        profile.phone = phone
        profile.address = address
        if pdpa_consent and profile.pdpa_consent_at is None:
            profile.pdpa_consent_at = timezone.now()
        profile.save()

        action = 'created' if created else 'updated'
        self.stdout.write(f'  {username}: {action}')
