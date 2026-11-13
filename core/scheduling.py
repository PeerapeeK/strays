"""Deterministic interview slot generation.

Slots are anchored to the shelter opening time and repeat every
``INTERVIEW_SLOT_MINUTES`` minutes. A slot is only offered when the whole
appointment fits before closing time, it is in the future, and it does not
overlap another active booking.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import InterviewRequest, ShelterSettings


def slot_duration():
    minutes = int(getattr(settings, 'INTERVIEW_SLOT_MINUTES', 60) or 60)
    return timedelta(minutes=max(1, minutes))


def booking_horizon_days():
    days = int(getattr(settings, 'INTERVIEW_BOOKING_HORIZON_DAYS', 60) or 60)
    return max(1, days)


def _combine(day, value):
    naive = datetime.combine(day, value)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def slots_for_day(day, shelter=None, duration=None):
    shelter = shelter or ShelterSettings.load()
    duration = duration or slot_duration()
    cursor = _combine(day, shelter.opening_time)
    closing = _combine(day, shelter.closing_time)
    while cursor + duration <= closing:
        yield cursor
        cursor += duration


def is_slot_aligned(value, shelter=None, duration=None):
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    local = timezone.localtime(value)
    shelter = shelter or ShelterSettings.load()
    duration = duration or slot_duration()
    opening = _combine(local.date(), shelter.opening_time)
    closing = _combine(local.date(), shelter.closing_time)
    if local < opening or local + duration > closing:
        return False
    return (local - opening).total_seconds() % duration.total_seconds() == 0


def has_booking_conflict(value, duration=None, exclude_pk=None):
    duration = duration or slot_duration()
    end = value + duration
    queryset = InterviewRequest.objects.filter(
        status__in=InterviewRequest.ACTIVE_STATUSES,
        scheduled_at__lt=end,
        scheduled_at__gt=value - duration,
    )
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


def available_interview_slots(
    now=None, horizon_days=None, shelter=None, exclude_pk=None
):
    now = now or timezone.now()
    shelter = shelter or ShelterSettings.load()
    duration = slot_duration()
    horizon = (
        booking_horizon_days() if horizon_days is None else max(0, horizon_days)
    )
    today = timezone.localdate(now)
    last_day = today + timedelta(days=horizon)

    bookings = InterviewRequest.objects.filter(
        status__in=InterviewRequest.ACTIVE_STATUSES,
        scheduled_at__date__gte=today,
        scheduled_at__date__lte=last_day,
    ).values_list('scheduled_at', flat=True)
    if exclude_pk is not None:
        bookings = bookings.exclude(pk=exclude_pk)
    intervals = [
        (booking, booking + duration) for booking in bookings
    ]

    slots = []
    for offset in range((last_day - today).days + 1):
        day = today + timedelta(days=offset)
        for slot in slots_for_day(day, shelter=shelter, duration=duration):
            if slot <= now:
                continue
            end = slot + duration
            if any(
                start < end and slot < finish
                for start, finish in intervals
            ):
                continue
            slots.append(slot)
    return slots


def slot_choice_groups(now=None, horizon_days=None, shelter=None):
    """Return optgroup choices for a ``Select`` widget."""
    slots = available_interview_slots(
        now=now, horizon_days=horizon_days, shelter=shelter
    )
    groups = []
    current_day = None
    day_choices = None
    for slot in slots:
        local = timezone.localtime(slot)
        if local.date() != current_day:
            current_day = local.date()
            day_choices = []
            groups.append((current_day.strftime('%d/%m/%Y'), day_choices))
        day_choices.append(
            (local.strftime('%Y-%m-%dT%H:%M'), local.strftime('%H:%M'))
        )
    return [('', 'เลือกวันและเวลา')] + groups
