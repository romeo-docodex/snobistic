# accounts/utils.py

from __future__ import annotations

from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from django.conf import settings
from django.http import HttpRequest
from django.utils.functional import Promise
from django.utils.http import url_has_allowed_host_and_scheme

TRUST_COOKIE_NAME = "sn_2fa_trust"


def safe_next(request: HttpRequest | None, fallback=None) -> str | None:
    """
    Returnează un next sigur (doar host-uri permise), altfel fallback.
    """
    if request is None:
        return str(fallback) if isinstance(fallback, Promise) else fallback

    nxt = request.POST.get("next") or request.GET.get("next")

    if nxt:
        allowed_hosts = {request.get_host()}
        extra_hosts = getattr(settings, "SAFE_NEXT_ALLOWED_HOSTS", None)
        if extra_hosts:
            allowed_hosts |= set(extra_hosts)

        require_https = request.is_secure()

        if url_has_allowed_host_and_scheme(
            url=nxt,
            allowed_hosts=allowed_hosts,
            require_https=require_https,
        ):
            return nxt

    if isinstance(fallback, Promise):
        return str(fallback)
    return fallback


def add_next_param(url: str, next_url: str | None, *, overwrite: bool = True) -> str:
    """
    Adaugă ?next=... în mod safe (url-encoded) fără să strice query-ul existent.
    """
    if not next_url:
        return url

    parts = list(urlsplit(url))
    query = dict(parse_qsl(parts[3], keep_blank_values=True))

    if "next" in query and not overwrite:
        return url

    query["next"] = next_url
    parts[3] = urlencode(query, doseq=True)
    return urlunsplit(parts)


def client_ip(request: HttpRequest | None) -> str | None:
    """
    Determină IP-ul clientului.
    """
    if request is None:
        return None

    remote_addr = request.META.get("REMOTE_ADDR")
    if not remote_addr:
        return None

    trust_xff = bool(getattr(settings, "TRUST_X_FORWARDED_FOR", False))
    if not trust_xff:
        return remote_addr

    trusted_proxies = set(getattr(settings, "TRUSTED_PROXY_IPS", []) or [])
    if trusted_proxies and remote_addr not in trusted_proxies:
        return remote_addr

    x_real = request.META.get("HTTP_X_REAL_IP")
    if x_real:
        return x_real.strip()

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()

    return remote_addr


def set_trusted_cookie(
    response,
    token: str,
    *,
    max_age_days: int = 30,
    domain: str | None = None,
    samesite: str = "Lax",
) -> None:
    secure_flag = getattr(settings, "SESSION_COOKIE_SECURE", None)
    if secure_flag is None:
        secure_flag = not settings.DEBUG

    response.set_cookie(
        TRUST_COOKIE_NAME,
        token,
        max_age=int(max_age_days) * 24 * 3600,
        httponly=True,
        secure=bool(secure_flag),
        samesite=samesite,
        path="/",
        domain=domain,
    )


def get_trusted_cookie(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    return request.COOKIES.get(TRUST_COOKIE_NAME)


def clear_trusted_cookie(response, *, domain: str | None = None) -> None:
    response.delete_cookie(TRUST_COOKIE_NAME, path="/", domain=domain)
