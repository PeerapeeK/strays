from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

ADMIN = 'Admin'
STAFF = 'Staff'
ADOPTER = 'Adopter'
ROLE_NAMES = (ADOPTER, STAFF, ADMIN)


def user_role(user):
    """Return the role name for a user, or None when no role is assigned."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser or user.groups.filter(name=ADMIN).exists():
        return ADMIN
    if user.groups.filter(name=STAFF).exists():
        return STAFF
    if user.groups.filter(name=ADOPTER).exists():
        return ADOPTER
    return None


def role_required(*roles):
    """Allow only users whose role is in ``roles``.

    Anonymous users are redirected to the login page; authenticated users
    with the wrong role receive a 403 response.
    """
    allowed = set(roles)

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if user_role(request.user) not in allowed:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class RoleRequiredMixin(LoginRequiredMixin):
    """Class-based view mixin counterpart of :func:`role_required`."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if user_role(request.user) not in set(self.allowed_roles):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ADMIN,)


class StaffRequiredMixin(RoleRequiredMixin):
    allowed_roles = (STAFF, ADMIN)


class AdopterRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ADOPTER,)
