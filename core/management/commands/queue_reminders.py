from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    AdoptionContract,
    FollowUp,
    HomeVisit,
    InterviewRequest,
    Notification,
)


class Command(BaseCommand):
    help = (
        'Mark overdue follow-ups and queue reminder notifications for upcoming '
        'interviews, follow-ups and home visits. Dedupe keys prevent duplicate '
        'reminders.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=getattr(settings, 'REMINDER_DAYS', 3),
            help='How many days ahead to look for reminders (default: 3).',
        )

    def handle(self, *args, **options):
        days = options['days']
        today = timezone.localdate()
        window_end = today + timedelta(days=days)

        overdue_count = self.mark_overdue(today)
        interview_count = self.queue_interview_reminders(days)
        followup_count = self.queue_follow_up_reminders(today, window_end)
        home_visit_count = self.queue_home_visit_reminders(days)

        self.stdout.write(
            f'Reminders queued: {interview_count} interview, '
            f'{followup_count} follow-up, {home_visit_count} home visit; '
            f'{overdue_count} follow-up(s) marked overdue.'
        )

    def queue_interview_reminders(self, days):
        now = timezone.now()
        window_end = now + timedelta(days=days)
        interviews = InterviewRequest.objects.filter(
            status__in=InterviewRequest.ACTIVE_STATUSES,
            scheduled_at__gte=now,
            scheduled_at__lte=window_end,
        ).select_related('adopter', 'dog')

        count = 0
        for interview in interviews:
            scheduled = timezone.localtime(interview.scheduled_at)
            if self._queue(
                interview.adopter,
                'แจ้งเตือนการนัดสัมภาษณ์',
                f'นัดสัมภาษณ์รหัส {interview.code} สำหรับสุนัข '
                f'{interview.dog.name} ในวันที่ '
                f'{scheduled:%d/%m/%Y %H:%M} กรุณาเตรียมตัวและมาตรงเวลา',
                f'interview-reminder-{interview.pk}-'
                f'{interview.scheduled_at.isoformat()}',
            ):
                count += 1
        return count

    def mark_overdue(self, today):
        overdue = FollowUp.objects.filter(
            status=FollowUp.PENDING,
            due_date__lt=today,
        ).select_related('contract__interview_request__adopter')

        count = 0
        for follow_up in overdue:
            follow_up.status = FollowUp.OVERDUE
            follow_up.save(update_fields=['status'])
            count += 1

            self._queue(
                follow_up.contract.adopter,
                'การติดตามผลเกินกำหนด',
                f'การติดตามผล {follow_up.day_offset} วัน ของสัญญา '
                f'{follow_up.contract.contract_no} เกินกำหนดแล้ว '
                f'(กำหนด {follow_up.due_date:%d/%m/%Y}) กรุณาส่งข้อมูลโดยเร็ว',
                f'followup-overdue-{follow_up.pk}-{follow_up.due_date.isoformat()}',
            )
        return count

    def queue_follow_up_reminders(self, today, window_end):
        follow_ups = FollowUp.objects.filter(
            status=FollowUp.PENDING,
            due_date__gte=today,
            due_date__lte=window_end,
            contract__status=AdoptionContract.ACTIVE,
        ).select_related('contract__interview_request__adopter')

        count = 0
        for follow_up in follow_ups:
            if self._queue(
                follow_up.contract.adopter,
                'แจ้งเตือนการติดตามผล',
                f'การติดตามผล {follow_up.day_offset} วัน ของสัญญา '
                f'{follow_up.contract.contract_no} ครบกำหนดวันที่ '
                f'{follow_up.due_date:%d/%m/%Y} กรุณาแนบรูปถ่ายและส่งข้อมูล',
                f'followup-reminder-{follow_up.pk}-{follow_up.due_date.isoformat()}',
            ):
                count += 1
        return count

    def queue_home_visit_reminders(self, days):
        now = timezone.now()
        window_end = now + timedelta(days=days)
        home_visits = HomeVisit.objects.filter(
            status__in=(HomeVisit.SCHEDULED, HomeVisit.APPROVED),
            scheduled_at__gte=now,
            scheduled_at__lte=window_end,
            contract__status=AdoptionContract.ACTIVE,
        ).select_related('contract__interview_request__adopter')

        count = 0
        for home_visit in home_visits:
            scheduled = timezone.localtime(home_visit.scheduled_at)
            if self._queue(
                home_visit.contract.adopter,
                'แจ้งเตือนวันตรวจบ้าน',
                f'สัญญาเลขที่ {home_visit.contract.contract_no} มีนัดตรวจบ้าน '
                f'วันที่ {scheduled:%d/%m/%Y %H:%M} กรุณาเตรียมความพร้อม',
                f'homevisit-reminder-{home_visit.pk}-'
                f'{home_visit.scheduled_at.isoformat()}',
            ):
                count += 1
        return count

    @staticmethod
    def _queue(user, title, message, dedupe_key):
        _, created = Notification.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={'user': user, 'title': title, 'message': message},
        )
        return created
