from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from .models import (
    FOLLOW_UP_DAYS,
    AdoptionContract,
    AuditEvent,
    Dog,
    FollowUp,
    FollowUpEvaluation,
    HomeVisit,
    InterviewRequest,
    InterviewResult,
    Notification,
    notify,
)
from .permissions import ADMIN, STAFF, user_role


def create_follow_ups(contract):
    """Create the 14/30/90/180 day follow-ups for a contract, idempotently."""
    follow_ups = []
    for days in FOLLOW_UP_DAYS:
        follow_up, _ = FollowUp.objects.get_or_create(
            contract=contract,
            day_offset=days,
            defaults={'due_date': contract.start_date + timedelta(days=days)},
        )
        follow_ups.append(follow_up)
    return follow_ups


def activate_contract(contract):
    """Activate a contract, mark the dog adopted, and create follow-ups."""
    if contract.status == AdoptionContract.ACTIVE:
        create_follow_ups(contract)
        return False

    with transaction.atomic():
        contract.status = AdoptionContract.ACTIVE
        contract.save(update_fields=['status', 'updated_at'])

        dog = contract.interview_request.dog
        if dog.status != Dog.ADOPTED:
            dog.status = Dog.ADOPTED
            dog.save(update_fields=['status'])

        create_follow_ups(contract)

    notify(
        contract.adopter,
        'สัญญารับอุปการะมีผลบังคับใช้แล้ว',
        f'สัญญาเลขที่ {contract.contract_no} สำหรับสุนัข {contract.dog.name} '
        'มีผลบังคับใช้แล้ว กรุณาตรวจสอบและยอมรับสัญญา',
        dedupe_key=f'contract-activated-{contract.pk}',
    )
    return True


def notify_staff(title, message, dedupe_key):
    """Create a notification for every staff user."""
    for user in User.objects.filter(groups__name=STAFF).distinct():
        notify(
            user,
            title,
            message,
            dedupe_key=f'{dedupe_key}-{user.pk}',
        )


def user_linked_records(user):
    """Return the business records linked to ``user`` with Thai labels."""
    checks = (
        ('การนัดสัมภาษณ์', InterviewRequest.objects.filter(adopter=user)),
        (
            'สัญญารับอุปการะ',
            AdoptionContract.objects.filter(interview_request__adopter=user),
        ),
        (
            'การติดตามผล',
            FollowUp.objects.filter(contract__interview_request__adopter=user),
        ),
        (
            'ผลการสัมภาษณ์',
            InterviewResult.objects.filter(
                Q(recorded_by=user) | Q(interview_request__adopter=user)
            ).distinct(),
        ),
        (
            'ผลประเมินการติดตามผล',
            FollowUpEvaluation.objects.filter(
                Q(evaluator=user)
                | Q(follow_up__contract__interview_request__adopter=user)
            ).distinct(),
        ),
        (
            'การนัดตรวจบ้าน',
            HomeVisit.objects.filter(
                Q(created_by=user)
                | Q(contract__interview_request__adopter=user)
            ).distinct(),
        ),
        ('การแจ้งเตือน', Notification.objects.filter(user=user)),
    )

    records = []
    for label, queryset in checks:
        count = queryset.count()
        if count:
            records.append({'label': label, 'count': count})
    return records


def active_admin_queryset():
    return (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(groups__name=ADMIN))
        .distinct()
    )


def active_admin_count():
    return active_admin_queryset().count()


def is_last_active_admin(user):
    if not user.is_active or user_role(user) != ADMIN:
        return False
    return active_admin_count() <= 1


def record_audit_event(actor, action, target_id, target_username):
    return AuditEvent.objects.create(
        actor=actor,
        actor_username=actor.username if actor else '',
        action=action,
        target_id=target_id,
        target_username=target_username,
    )


def delete_user(target, actor):
    """Permanently delete ``target`` and record the action in the audit log."""
    target_id = target.pk
    target_username = target.username
    with transaction.atomic():
        target.delete()
        record_audit_event(
            actor, AuditEvent.DELETE, target_id, target_username
        )
    return target_username


def anonymize_user(target, actor):
    """Anonymize ``target`` while keeping every linked business record."""
    original_username = target.username
    with transaction.atomic():
        candidate = f'deleted-{target.pk}'
        suffix = 1
        while (
            User.objects.filter(username=candidate)
            .exclude(pk=target.pk)
            .exists()
        ):
            suffix += 1
            candidate = f'deleted-{target.pk}-{suffix}'

        target.username = candidate
        target.email = ''
        target.is_active = False
        target.set_unusable_password()
        target.save()

        profile = target.profile
        profile.full_name = ''
        profile.phone = ''
        profile.address = ''
        profile.pdpa_consent_at = None
        profile.save()

        record_audit_event(
            actor, AuditEvent.ANONYMIZE, target.pk, original_username
        )
    return original_username
