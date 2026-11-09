from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction

from .models import (
    FOLLOW_UP_DAYS,
    AdoptionContract,
    Dog,
    FollowUp,
    notify,
)
from .permissions import STAFF


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
