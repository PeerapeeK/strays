from .models import Notification
from .permissions import user_role


def current_role(request):
    unread_notifications = 0
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(
            user=request.user, read_at__isnull=True
        ).count()
    return {
        'current_role': user_role(request.user),
        'unread_notifications': unread_notifications,
    }
