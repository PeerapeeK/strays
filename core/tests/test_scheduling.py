from datetime import datetime, time, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Dog, InterviewRequest, ShelterSettings
from core.scheduling import (
    available_interview_slots,
    booking_horizon_days,
    is_slot_aligned,
    slot_duration,
)


class SlotGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        shelter = ShelterSettings.load()
        shelter.opening_time = time(10, 0)
        shelter.closing_time = time(18, 0)
        shelter.save()
        cls.dog = Dog.objects.create(name='SlotDog', status=Dog.AVAILABLE)

    def aware(self, *args):
        return timezone.make_aware(datetime(*args))

    def make_interview(self, scheduled_at, status=InterviewRequest.PENDING):
        from django.contrib.auth.models import User

        user, _ = User.objects.get_or_create(
            username='slot_adopter',
            defaults={'password': 'x'},
        )
        return InterviewRequest.objects.create(
            adopter=user,
            dog=self.dog,
            scheduled_at=scheduled_at,
            full_name='ผู้ทดสอบ',
            phone='0812345678',
            address='ที่อยู่',
            status=status,
        )

    def test_slots_are_hourly_and_never_end_after_closing(self):
        now = self.aware(2026, 5, 4, 9, 0)
        slots = available_interview_slots(now=now, horizon_days=0)
        self.assertEqual(
            [timezone.localtime(slot).time() for slot in slots],
            [time(hour, 0) for hour in range(10, 18)],
        )

    def test_slot_starting_at_closing_is_not_generated(self):
        now = self.aware(2026, 5, 4, 9, 0)
        slots = available_interview_slots(now=now, horizon_days=0)
        self.assertNotIn(
            time(18, 0), [timezone.localtime(slot).time() for slot in slots]
        )

    def test_past_slots_for_today_are_skipped(self):
        now = self.aware(2026, 5, 4, 12, 30)
        slots = available_interview_slots(now=now, horizon_days=0)
        self.assertEqual(
            [timezone.localtime(slot).time() for slot in slots],
            [time(hour, 0) for hour in range(13, 18)],
        )

    def test_existing_active_booking_removes_conflicting_slot(self):
        now = self.aware(2026, 5, 4, 9, 0)
        booked = self.aware(2026, 5, 4, 11, 0)
        self.make_interview(booked)
        slots = available_interview_slots(now=now, horizon_days=0)
        self.assertNotIn(
            time(11, 0), [timezone.localtime(slot).time() for slot in slots]
        )

    def test_cancelled_booking_does_not_block_slot(self):
        now = self.aware(2026, 5, 4, 9, 0)
        booked = self.aware(2026, 5, 4, 11, 0)
        self.make_interview(booked, status=InterviewRequest.CANCELLED)
        slots = available_interview_slots(now=now, horizon_days=0)
        self.assertIn(
            time(11, 0), [timezone.localtime(slot).time() for slot in slots]
        )

    def test_legacy_overlapping_booking_blocks_both_slots(self):
        now = self.aware(2026, 5, 4, 9, 0)
        self.make_interview(self.aware(2026, 5, 4, 11, 30))
        slots = available_interview_slots(now=now, horizon_days=0)
        times = [timezone.localtime(slot).time() for slot in slots]
        self.assertNotIn(time(11, 0), times)
        self.assertNotIn(time(12, 0), times)
        self.assertIn(time(13, 0), times)

    def test_slot_alignment_helper(self):
        self.assertTrue(is_slot_aligned(self.aware(2026, 5, 4, 10, 0)))
        self.assertTrue(is_slot_aligned(self.aware(2026, 5, 4, 17, 0)))
        self.assertFalse(is_slot_aligned(self.aware(2026, 5, 4, 10, 5)))
        self.assertFalse(is_slot_aligned(self.aware(2026, 5, 4, 17, 30)))
        self.assertFalse(is_slot_aligned(self.aware(2026, 5, 4, 18, 0)))

    def test_horizon_reaches_dates_farther_than_seven_days(self):
        now = self.aware(2026, 5, 4, 9, 0)
        slots = available_interview_slots(now=now, horizon_days=20)
        last_day = timezone.localtime(slots[-1]).date()
        self.assertEqual(last_day, timezone.localdate(now) + timedelta(days=20))

    @override_settings(INTERVIEW_BOOKING_HORIZON_DAYS=14)
    def test_horizon_setting_is_configurable(self):
        self.assertEqual(booking_horizon_days(), 14)

    @override_settings(INTERVIEW_SLOT_MINUTES=30)
    def test_slot_duration_setting_is_configurable(self):
        self.assertEqual(slot_duration().total_seconds(), 30 * 60)
        now = self.aware(2026, 5, 4, 9, 0)
        slots = available_interview_slots(now=now, horizon_days=0)
        self.assertEqual(
            timezone.localtime(slots[-1]).time(), time(17, 30)
        )
