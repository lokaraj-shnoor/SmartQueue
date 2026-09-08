from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def role_required(*roles, redirect_to="dashboard:home"):
    """Allow the view only for the listed roles. Superusers always pass."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if user.is_superuser or user.role in roles:
                return view(request, *args, **kwargs)
            messages.error(request, "You do not have access to that page.")
            return redirect(redirect_to)

        return wrapper

    return decorator


def admin_required(view):
    from accounts.models import Role

    return role_required(Role.ADMIN)(view)


def staff_required(view):
    """Counter staff, plus administrators covering a desk."""
    from accounts.models import Role

    return role_required(Role.STAFF, Role.ADMIN)(view)
