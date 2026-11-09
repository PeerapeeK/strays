import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Notification
from core.push import send_push


class Command(BaseCommand):
    help = (
        'Dispatch pending push notifications. Failed notifications are retried '
        'with an exponential backoff (1 initial attempt + 3 retries).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Keep running and process notifications every --interval seconds.',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=15,
            help='Seconds to wait between runs when --loop is used (default: 15).',
        )

    def handle(self, *args, **options):
        if options['loop']:
            self.stdout.write(
                f'Starting notification loop (interval: {options["interval"]}s). '
                'Press Ctrl+C to stop.'
            )
            try:
                while True:
                    self.process_due()
                    time.sleep(options['interval'])
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('Notification loop stopped.'))
                return
        self.process_due()

    def process_due(self):
        now = timezone.now()
        notifications = (
            Notification.objects.filter(
                status=Notification.PENDING,
                next_attempt_at__lte=now,
            )
            .select_related('user')
            .order_by('next_attempt_at', 'pk')
        )

        sent = 0
        retrying = 0
        failed = 0
        for notification in notifications:
            if send_push(notification):
                sent += 1
            elif notification.status == Notification.FAILED:
                failed += 1
            else:
                retrying += 1

        if sent or retrying or failed:
            self.stdout.write(
                f'Notifications processed: {sent} sent, {retrying} retrying, '
                f'{failed} failed.'
            )
        else:
            self.stdout.write('No notifications due.')
        return sent, retrying, failed
