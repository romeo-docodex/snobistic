# accounts/utils.py
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings
from django.utils.functional import Promise

TRUST_COOKIE_NAME = "sn_2fa_trust"

def safe_next(request, fallback=None):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt

    # dacă fallback e lazy (reverse_lazy, gettext_lazy etc), îl forțăm în string
    if isinstance(fallback, Promise):
        return str(fallback)

    return fallback

def client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def set_trusted_cookie(response, token, max_age_days=30):
    response.set_cookie(
        TRUST_COOKIE_NAME,
        token,
        max_age=max_age_days * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="Lax",
    )

def get_trusted_cookie(request):
    return request.COOKIES.get(TRUST_COOKIE_NAME)

def clear_trusted_cookie(response):
    response.delete_cookie(TRUST_COOKIE_NAME)
