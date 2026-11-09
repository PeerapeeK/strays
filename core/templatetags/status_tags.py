from django import template

register = template.Library()

STATUS_CLASSES = {
    'available': 'status-available',
    'confirmed': 'status-available',
    'active': 'status-available',
    'approved': 'status-available',
    'sent': 'status-available',
    'passed': 'status-available',
    'pending': 'status-pending',
    'draft': 'status-pending',
    'scheduled': 'status-pending',
    'reschedule_requested': 'status-pending',
    'submitted': 'status-adopted',
    'completed': 'status-adopted',
    'adopted': 'status-adopted',
    'overdue': 'status-rejected',
    'rejected': 'status-rejected',
    'cancelled': 'status-rejected',
    'failed': 'status-rejected',
    'denied': 'status-rejected',
    'unavailable': 'status-rejected',
}


@register.filter
def status_class(value):
    return STATUS_CLASSES.get(str(value).lower(), 'status-pending')


@register.filter
def alert_class(value):
    tag = {'error': 'danger', 'debug': 'secondary'}.get(value, value or 'info')
    return f'alert-{tag} bg-{tag}-subtle'
