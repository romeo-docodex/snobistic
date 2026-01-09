# accounts/decorators.py

from __future__ import annotations

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from .constants import GROUP_SHOP_MANAGER


def is_shop_manager(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    # Allow classic staff too
    if getattr(user, "is_staff", False):
        return True
    return user.groups.filter(name=GROUP_SHOP_MANAGER).exists()


def shop_manager_required(view_func):
    """
    Permite acces dacă:
      - superuser
      - is_staff
      - user e în group "Shop Manager"
    (Permisiunile efective sunt date de group perms via bootstrap_roles.)
    """

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_shop_manager(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


class ShopManagerRequiredMixin:
    """
    Pentru CBV-uri.
    """

    raise_exception = True

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_shop_manager(request.user):
            if self.raise_exception:
                raise PermissionDenied
            return redirect_to_login(request.get_full_path())
        return super().dispatch(request, *args, **kwargs)
