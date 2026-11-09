import secrets
from datetime import date, time, timedelta

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from simple_history.models import HistoricalRecords

from .validators import validate_image


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='ผู้ใช้',
    )
    full_name = models.CharField('ชื่อ-นามสกุล', max_length=150, blank=True)
    phone = models.CharField('เบอร์โทรศัพท์', max_length=20, blank=True)
    address = models.TextField('ที่อยู่', blank=True)
    pdpa_consent_at = models.DateTimeField('เวลายินยอม PDPA', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'โปรไฟล์'
        verbose_name_plural = 'โปรไฟล์'

    def __str__(self):
        return self.full_name or self.user.get_username()


class ShelterSettings(models.Model):
    opening_time = models.TimeField('เวลาเปิด', default=time(9, 0))
    closing_time = models.TimeField('เวลาปิด', default=time(18, 0))
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ตั้งค่าศูนย์รับเลี้ยง'
        verbose_name_plural = 'ตั้งค่าศูนย์รับเลี้ยง'

    def __str__(self):
        return f'ศูนย์รับเลี้ยง ({self.opening_time:%H:%M}-{self.closing_time:%H:%M})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


class Dog(models.Model):
    MALE = 'male'
    FEMALE = 'female'
    SEX_CHOICES = [
        (MALE, 'ผู้'),
        (FEMALE, 'เมีย'),
    ]

    SMALL = 'small'
    MEDIUM = 'medium'
    LARGE = 'large'
    SIZE_CHOICES = [
        (SMALL, 'เล็ก'),
        (MEDIUM, 'กลาง'),
        (LARGE, 'ใหญ่'),
    ]

    AVAILABLE = 'available'
    PENDING = 'pending'
    ADOPTED = 'adopted'
    UNAVAILABLE = 'unavailable'
    STATUS_CHOICES = [
        (AVAILABLE, 'พร้อมรับอุปการะ'),
        (PENDING, 'อยู่ระหว่างดำเนินการ'),
        (ADOPTED, 'ถูกรับอุปการะแล้ว'),
        (UNAVAILABLE, 'ไม่พร้อมรับอุปการะ'),
    ]

    name = models.CharField('ชื่อ', max_length=100)
    breed = models.CharField('พันธุ์', max_length=100, blank=True)
    sex = models.CharField('เพศ', max_length=10, choices=SEX_CHOICES, default=MALE)
    age_months = models.PositiveIntegerField('อายุ (เดือน)', default=0)
    size = models.CharField('ขนาด', max_length=10, choices=SIZE_CHOICES, default=MEDIUM)
    color = models.CharField('สี', max_length=100, blank=True)
    description = models.TextField('รายละเอียด', blank=True)
    vaccinated = models.BooleanField('ฉีดวัคซีนแล้ว', default=False)
    sterilized = models.BooleanField('ทำหมันแล้ว', default=False)
    status = models.CharField('สถานะ', max_length=20, choices=STATUS_CHOICES, default=AVAILABLE)
    photo = models.ImageField(
        'รูปภาพ',
        upload_to='dogs/',
        blank=True,
        null=True,
        validators=[validate_image],
    )
    intake_date = models.DateField('วันที่รับเข้า', default=date.today)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'สุนัข'
        verbose_name_plural = 'สุนัข'
        ordering = ('-intake_date', 'name')

    def __str__(self):
        return self.name


class DogHealthRecord(models.Model):
    dog = models.ForeignKey(
        Dog,
        on_delete=models.CASCADE,
        related_name='health_records',
        verbose_name='สุนัข',
    )
    record_date = models.DateField('วันที่บันทึก', default=date.today)
    title = models.CharField('หัวข้อ', max_length=200)
    description = models.TextField('รายละเอียด')
    veterinarian = models.CharField('สัตวแพทย์', max_length=150, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'บันทึกสุขภาพ'
        verbose_name_plural = 'บันทึกสุขภาพ'
        ordering = ('-record_date', '-pk')

    def __str__(self):
        return f'{self.dog.name}: {self.title}'


class InterviewRequest(models.Model):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'
    STATUS_CHOICES = [
        (PENDING, 'รอการยืนยัน'),
        (CONFIRMED, 'ยืนยันแล้ว'),
        (REJECTED, 'ถูกปฏิเสธ'),
        (CANCELLED, 'ยกเลิกแล้ว'),
        (COMPLETED, 'เสร็จสิ้น'),
    ]
    ACTIVE_STATUSES = (PENDING, CONFIRMED)

    code = models.CharField('รหัสการนัดหมาย', max_length=12, unique=True, editable=False)
    adopter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interview_requests',
        verbose_name='ผู้รับอุปการะ',
    )
    dog = models.ForeignKey(
        Dog,
        on_delete=models.PROTECT,
        related_name='interview_requests',
        verbose_name='สุนัข',
    )
    status = models.CharField(
        'สถานะ', max_length=20, choices=STATUS_CHOICES, default=PENDING
    )
    scheduled_at = models.DateTimeField('วันและเวลาสัมภาษณ์')
    full_name = models.CharField('ชื่อ-นามสกุล', max_length=150)
    phone = models.CharField('เบอร์โทรศัพท์', max_length=20)
    address = models.TextField('ที่อยู่')
    reject_reason = models.TextField('เหตุผลการปฏิเสธ', blank=True)
    attendance_confirmed_at = models.DateTimeField(
        'เวลายืนยันการเข้าร่วม', null=True, blank=True
    )
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)
    updated_at = models.DateTimeField('แก้ไขเมื่อ', auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'คำขอนัดสัมภาษณ์'
        verbose_name_plural = 'คำขอนัดสัมภาษณ์'
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.code} - {self.dog.name}'

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                code = f'INT-{secrets.token_hex(4).upper()}'
                if not InterviewRequest.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)

    @property
    def can_cancel(self):
        if self.status not in self.ACTIVE_STATUSES:
            return False
        return self.scheduled_at - timezone.now() >= timedelta(hours=24)

    @property
    def can_confirm_attendance(self):
        return self.status == self.CONFIRMED and self.attendance_confirmed_at is None


class Assessment(models.Model):
    OWN = 'own'
    RENT = 'rent'
    WITH_FAMILY = 'family'
    OTHER = 'other'
    HOUSING_CHOICES = [
        (OWN, 'บ้านของตนเอง'),
        (RENT, 'บ้านเช่า'),
        (WITH_FAMILY, 'อาศัยอยู่กับครอบครัว'),
        (OTHER, 'อื่น ๆ'),
    ]

    interview_request = models.OneToOneField(
        InterviewRequest,
        on_delete=models.CASCADE,
        related_name='assessment',
        verbose_name='คำขอนัดสัมภาษณ์',
    )
    housing_type = models.CharField(
        'ประเภทที่อยู่อาศัย', max_length=20, choices=HOUSING_CHOICES
    )
    has_other_pets = models.BooleanField('มีสัตว์เลี้ยงอื่นอยู่แล้ว', default=False)
    household_members = models.PositiveIntegerField('จำนวนสมาชิกในบ้าน', default=1)
    experience = models.TextField('ประสบการณ์เลี้ยงสุนัข')
    motivation = models.TextField('เหตุผลที่ต้องการรับอุปการะ')
    agree_home_visit = models.BooleanField('ยินยอมให้เข้าตรวจบ้าน', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'แบบประเมินเบื้องต้น'
        verbose_name_plural = 'แบบประเมินเบื้องต้น'

    def __str__(self):
        return f'แบบประเมินของ {self.interview_request.code}'


class HousingPhoto(models.Model):
    interview_request = models.ForeignKey(
        InterviewRequest,
        on_delete=models.CASCADE,
        related_name='housing_photos',
        verbose_name='คำขอนัดสัมภาษณ์',
    )
    image = models.ImageField(
        'รูปถ่ายที่อยู่อาศัย',
        upload_to='interviews/housing/',
        validators=[validate_image],
    )
    uploaded_at = models.DateTimeField('อัปโหลดเมื่อ', auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'รูปถ่ายที่อยู่อาศัย'
        verbose_name_plural = 'รูปถ่ายที่อยู่อาศัย'
        ordering = ('pk',)

    def __str__(self):
        return f'รูปถ่ายของ {self.interview_request.code}'


class InterviewResult(models.Model):
    PASSED = 'passed'
    FAILED = 'failed'
    OUTCOME_CHOICES = [
        (PASSED, 'ผ่าน'),
        (FAILED, 'ไม่ผ่าน'),
    ]

    interview_request = models.OneToOneField(
        InterviewRequest,
        on_delete=models.CASCADE,
        related_name='result',
        verbose_name='คำขอนัดสัมภาษณ์',
    )
    outcome = models.CharField('ผลการสัมภาษณ์', max_length=20, choices=OUTCOME_CHOICES)
    notes = models.TextField('รายละเอียดผลการสัมภาษณ์')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_interview_results',
        verbose_name='บันทึกโดย',
    )
    recorded_at = models.DateTimeField('บันทึกเมื่อ', auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ผลการสัมภาษณ์'
        verbose_name_plural = 'ผลการสัมภาษณ์'

    def __str__(self):
        return f'ผลการสัมภาษณ์ {self.interview_request.code}'


class InterviewPhoto(models.Model):
    result = models.ForeignKey(
        InterviewResult,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name='ผลการสัมภาษณ์',
    )
    image = models.ImageField(
        'รูปภาพการสัมภาษณ์',
        upload_to='interviews/results/',
        validators=[validate_image],
    )
    uploaded_at = models.DateTimeField('อัปโหลดเมื่อ', auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'รูปภาพการสัมภาษณ์'
        verbose_name_plural = 'รูปภาพการสัมภาษณ์'
        ordering = ('pk',)

    def __str__(self):
        return f'รูปภาพผลการสัมภาษณ์ {self.result.interview_request.code}'


class Notification(models.Model):
    PENDING = 'pending'
    SENT = 'sent'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (PENDING, 'รอส่ง'),
        (SENT, 'ส่งแล้ว'),
        (FAILED, 'ส่งไม่สำเร็จ'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='ผู้รับ',
    )
    title = models.CharField('หัวข้อ', max_length=200)
    message = models.TextField('ข้อความ')
    status = models.CharField(
        'สถานะ', max_length=20, choices=STATUS_CHOICES, default=PENDING
    )
    attempts = models.PositiveIntegerField('จำนวนครั้งที่พยายาม', default=0)
    last_error = models.TextField('ข้อผิดพลาดล่าสุด', blank=True)
    next_attempt_at = models.DateTimeField('เวลาพยายามครั้งถัดไป', default=timezone.now)
    dedupe_key = models.CharField(
        'รหัสป้องกันการซ้ำ', max_length=200, unique=True, null=True, blank=True
    )
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)
    updated_at = models.DateTimeField('แก้ไขเมื่อ', auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'การแจ้งเตือน'
        verbose_name_plural = 'การแจ้งเตือน'
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.title} -> {self.user.get_username()}'


def notify(user, title, message, dedupe_key=None):
    """Create a pending notification row without dispatching it."""
    defaults = {'user': user, 'title': title, 'message': message}
    if dedupe_key:
        notification, _ = Notification.objects.get_or_create(
            dedupe_key=dedupe_key, defaults=defaults
        )
        return notification
    return Notification.objects.create(**defaults)
