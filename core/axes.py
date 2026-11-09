def client_ip(request):
    """Return the real client IP forwarded by nginx as X-Real-IP."""
    return (
        request.META.get('HTTP_X_REAL_IP')
        or request.META.get('REMOTE_ADDR')
    )
