"""Push notification dispatcher.

The actual delivery is delegated to an external push provider over HTTP.
When ``settings.PUSH_PROVIDER_URL`` is empty the dispatcher runs in
development mode and simply marks the notification as sent.
"""

import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

SAVE_FIELDS = ('status', 'attempts', 'last_error', 'next_attempt_at', 'updated_at')


def send_push(notification):
    """Try to deliver a single notification.

    Returns ``True`` when the notification was delivered (or handled in
    development mode) and ``False`` when the attempt failed. The notification
    is always saved with its updated attempt counter and next retry time.
    """
    provider_url = getattr(settings, 'PUSH_PROVIDER_URL', '') or ''
    timeout = getattr(settings, 'PUSH_TIMEOUT', 10)
    max_attempts = getattr(settings, 'PUSH_MAX_ATTEMPTS', 4)
    retry_delay = getattr(settings, 'PUSH_RETRY_DELAY', 60)

    now = timezone.now()
    notification.attempts += 1

    if not provider_url:
        logger.info(
            'PUSH_PROVIDER_URL is empty: marking notification %s as sent (dev mode)',
            notification.pk,
        )
        notification.status = Notification.SENT
        notification.last_error = ''
        notification.next_attempt_at = now
        notification.save(update_fields=SAVE_FIELDS)
        return True

    payload = {
        'notification_id': notification.pk,
        'user_id': notification.user_id,
        'username': notification.user.get_username(),
        'title': notification.title,
        'message': notification.message,
    }

    try:
        response = requests.post(provider_url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        notification.last_error = str(exc)[:1000]
        if notification.attempts >= max_attempts:
            notification.status = Notification.FAILED
            logger.warning(
                'Notification %s failed permanently after %s attempts',
                notification.pk,
                notification.attempts,
            )
        else:
            notification.status = Notification.PENDING
            delay = retry_delay * (2 ** (notification.attempts - 1))
            notification.next_attempt_at = now + timedelta(seconds=delay)
            logger.info(
                'Notification %s failed (attempt %s), retrying in %ss',
                notification.pk,
                notification.attempts,
                delay,
            )
        notification.save(update_fields=SAVE_FIELDS)
        return False

    notification.status = Notification.SENT
    notification.last_error = ''
    notification.next_attempt_at = now
    notification.save(update_fields=SAVE_FIELDS)
    return True
