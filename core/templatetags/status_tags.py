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


@register.filter
def age_th(months):
    try:
        months = int(months)
    except (TypeError, ValueError):
        return ''
    if months <= 0:
        return 'ไม่ทราบอายุ'
    years, remainder = divmod(months, 12)
    if years and remainder:
        return f'{years} ปี {remainder} เดือน'
    if years:
        return f'{years} ปี'
    return f'{remainder} เดือน'


def _initials(full_name, username):
    name = (full_name or '').strip()
    if name:
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[0].upper()
    return (username or '?')[:1].upper()


@register.inclusion_tag('includes/avatar.html')
def avatar(user, size=32):
    profile = None
    if user and getattr(user, 'is_authenticated', False):
        try:
            profile = user.profile
        except Exception:
            profile = None

    full_name = profile.full_name if profile else ''
    username = user.get_username() if user else ''
    photo_url = ''
    if profile and profile.photo:
        try:
            photo_url = profile.photo.url
        except ValueError:
            photo_url = ''

    initials = _initials(full_name, username)
    size = int(size)
    ratio = 0.42 if len(initials) == 1 else 0.34
    return {
        'photo_url': photo_url,
        'initials': initials,
        'size': size,
        'font_size': max(11, int(size * ratio)),
        'alt': full_name or username,
    }
