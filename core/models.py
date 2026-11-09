from datetime import time

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords


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
