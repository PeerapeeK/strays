from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Dog, ShelterSettings
from core.permissions import ADOPTER, ADMIN, ROLE_NAMES, STAFF

PASSWORD = 'demo1234'
DOGS = [
    ('บราวนี่', 'ไทยหลังอาน', Dog.FEMALE, 18, Dog.MEDIUM, 'น้ำตาล', Dog.AVAILABLE, True, True, 30),
    ('เจ้าโชค', 'พันธุ์ผสม', Dog.MALE, 24, Dog.MEDIUM, 'ดำ', Dog.AVAILABLE, True, False, 25),
    ('มะลิ', 'ไซบีเรียน', Dog.FEMALE, 12, Dog.LARGE, 'ขาว', Dog.AVAILABLE, True, True, 20),
    ('ท็อป', 'ชิวาวา', Dog.MALE, 36, Dog.SMALL, 'น้ำตาลอ่อน', Dog.AVAILABLE, False, True, 18),
    ('ปังปัง', 'โกลเด้นรีทรีฟเวอร์', Dog.MALE, 48, Dog.LARGE, 'ทอง', Dog.AVAILABLE, True, True, 15),
    ('ส้มจี๊ด', 'พันธุ์ผสม', Dog.FEMALE, 8, Dog.SMALL, 'ส้ม', Dog.AVAILABLE, False, False, 12),
    ('ดำดี', 'ไทยหลังอาน', Dog.MALE, 60, Dog.MEDIUM, 'ดำ', Dog.PENDING, True, True, 10),
    ('ช็อคโก้', 'ลาบราดอร์', Dog.MALE, 30, Dog.LARGE, 'น้ำตาล', Dog.ADOPTED, True, True, 40),
    ('ข้าวเหนียว', 'พันธุ์ผสม', Dog.FEMALE, 6, Dog.SMALL, 'ขาวดำ', Dog.UNAVAILABLE, False, False, 5),
    ('เจ้าดำ', 'พันธุ์ผสม', Dog.MALE, 42, Dog.MEDIUM, 'ดำ', Dog.AVAILABLE, True, True, 3),
]


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

        for data in DOGS:
            self._upsert_dog(*data)

        self.stdout.write(self.style.SUCCESS(
            'Seed complete: admin, staff1, staff2, adopter1-3, 10 dogs (password: demo1234)'
        ))

    def _upsert_dog(self, name, breed, sex, age_months, size, color, status,
                    vaccinated, sterilized, days_ago):
        dog, created = Dog.objects.update_or_create(
            name=name,
            defaults={
                'breed': breed,
                'sex': sex,
                'age_months': age_months,
                'size': size,
                'color': color,
                'description': f'{name} เป็นสุนัขที่อยู่ในความดูแลของศูนย์รับเลี้ยง',
                'status': status,
                'vaccinated': vaccinated,
                'sterilized': sterilized,
                'intake_date': date.today() - timedelta(days=days_ago),
            },
        )
        action = 'created' if created else 'updated'
        self.stdout.write(f'  dog #{dog.pk}: {action}')

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
