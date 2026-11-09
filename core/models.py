from datetime import date, time

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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
