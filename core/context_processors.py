from .permissions import user_role


def current_role(request):
    return {'current_role': user_role(request.user)}
