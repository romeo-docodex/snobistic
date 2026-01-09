# accounts/views.py
from __future__ import annotations

from typing import Optional

try:
    from ratelimit.decorators import ratelimit
except Exception:  # pragma: no cover
    def ratelimit(*args, **kwargs):
        def _decorator(view_func):
            return view_func
        return _decorator

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.cache import cache
from django.db import IntegrityError, models, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.http import require_POST

from catalog.models import Favorite

from .decorators import shop_manager_required
from .forms import (
    AddressForm,
    DeleteAccountConfirmForm,
    KycDocumentForm,
    LoginForm,
    ProfileDimensionsForm,
    ProfilePersonalForm,
    ProfilePreferencesForm,
    RegisterForm,
    SellerLocationForm,
    SellerSettingsForm,
    TwoFactorForm,
)
from .models import (
    AccountEvent,
    Address,
    CustomUser,
    EmailChangeRequest,
    KycDocument,
    KycRequest,
    SellerLocation,
    SellerProfile,
    TrustedDevice,
)
from .notifications import (
    send_activation_email,
    send_delete_account_code,
    send_email_2fa_code,
    send_email_change_confirmation,
)
from .services.score import (
    sync_buyer_identity_bonuses,
    sync_seller_identity_bonuses,
)
from .tokens import account_activation_token
from .utils import (
    add_next_param,
    clear_trusted_cookie,
    client_ip,
    get_trusted_cookie,
    safe_next,
    set_trusted_cookie,
)

try:
    import pyotp
except Exception:  # pragma: no cover
    pyotp = None

# Optional (django-allauth). We only *use* it for social login urls + email syncing.
try:  # pragma: no cover
    from allauth.account.models import EmailAddress
except Exception:  # pragma: no cover
    EmailAddress = None


# =============================================================================
# Helpers
# =============================================================================

TRUSTED_DEVICE_TTL_DAYS_DEFAULT = 30


def make_backup_codes(n: int = 10, length: int = 8) -> list[str]:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    from django.utils.crypto import get_random_string as _grs
    return [_grs(length, allowed_chars=alphabet) for _ in range(n)]


def _auth_backend_path() -> Optional[str]:
    backends = getattr(settings, "AUTHENTICATION_BACKENDS", None) or []
    return backends[0] if backends else None


def _login_user(request: HttpRequest, user: CustomUser) -> None:
    backend = getattr(user, "backend", None) or _auth_backend_path()
    if backend:
        login(request, user, backend=backend)
    else:
        login(request, user)


def _is_seller(user) -> bool:
    """
    ✅ Source of truth (business): Profile.role_seller
    Fallback only if profile missing (legacy edge cases).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    prof = getattr(user, "profile", None)
    if prof is not None:
        return bool(getattr(prof, "role_seller", False))
    return bool(getattr(user, "is_seller", False))


def _ensure_session_key(request: HttpRequest) -> None:
    if not request.session.session_key:
        request.session.modified = True
        request.session.save()


def _trusted_device_match(user: CustomUser, raw_token: str) -> bool:
    if not raw_token:
        return False

    now = timezone.now()
    # housekeeping: delete expired
    user.trusted_devices.filter(expires_at__lte=now).delete()

    # NOTE: if TrustedDevice.matches() needs extra fields, remove .only() or include them.
    qs = user.trusted_devices.filter(expires_at__gt=now).only("id", "token_hash", "expires_at")
    for td in qs:
        if td.matches(raw_token):
            try:
                TrustedDevice.objects.filter(pk=td.pk).update(last_used_at=timezone.now())
            except Exception:
                pass
            return True
    return False


def _cleanup_trusted_devices(user: CustomUser, *, raw_cookie_token: str | None = None) -> None:
    if not user or not getattr(user, "is_authenticated", False):
        return

    now = timezone.now()
    try:
        user.trusted_devices.filter(expires_at__lte=now).delete()
    except Exception:
        pass

    if not raw_cookie_token:
        return

    try:
        qs = user.trusted_devices.filter(expires_at__gt=now).only("id", "token_hash")
        for td in qs:
            try:
                if td.matches(raw_cookie_token):
                    td.delete()
                    break
            except Exception:
                continue
    except Exception:
        pass


def _revoke_all_trusted_devices(user: CustomUser) -> None:
    """Best-effort: revoke all trusted devices in DB."""
    try:
        TrustedDevice.objects.filter(user=user).delete()
    except Exception:
        pass


def _reverse_social(provider: str) -> Optional[str]:
    try:
        return reverse("socialaccount_login", kwargs={"provider": provider})
    except NoReverseMatch:
        return None


def _social_login_url(request: HttpRequest, provider: str, *, next_url: str | None = None) -> Optional[str]:
    """
    ✅ PAS 5.1(1): Social login păstrează next.
    """
    base = _reverse_social(provider)
    if not base:
        return None
    nxt = next_url if next_url is not None else safe_next(request, fallback=None)
    return add_next_param(base, nxt)


# =============================================================================
# Roles
# =============================================================================

@login_required
def roles_center(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    return render(request, "accounts/profile/roles_center.html", {"profile": prof})


@login_required
@require_POST
@transaction.atomic
def upgrade_to_seller(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    if not prof.role_seller:
        prof.role_seller = True
        prof.save(update_fields=["role_seller"])  # ✅ models.py keeps user.is_seller in sync

    SellerProfile.objects.get_or_create(user=request.user)

    if not request.user.locations.exists():
        SellerLocation.objects.create(user=request.user, code="USR", is_default=True)

    messages.success(request, _("Contul a fost upgradat la vânzător."))
    return redirect("accounts:seller_settings")


@login_required
@require_POST
@transaction.atomic
def downgrade_roles(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    if prof.role_seller:
        prof.role_seller = False
        prof.role_buyer = True
        prof.save(update_fields=["role_seller", "role_buyer"])  # ✅ models.py keeps user.is_seller in sync

    messages.success(request, _("Rolurile au fost actualizate."))
    return redirect("accounts:roles_center")


@login_required
@require_POST
def toggle_seller_can_buy(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    if prof.role_seller:
        prof.seller_can_buy = not prof.seller_can_buy
        prof.save(update_fields=["seller_can_buy"])
        messages.success(request, _("Setarea a fost actualizată."))
    return redirect("accounts:roles_center")


# =============================================================================
# Auth: Login / Logout / Register / Activate
# =============================================================================

class LoginView(View):
    form_class = LoginForm
    template_name = "accounts/auth/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        form = self.form_class()
        next_url = safe_next(request, fallback=None)
        ctx = {
            "form": form,
            "next": next_url,
            # ✅ PAS 5.1(1): preserve next through allauth
            "social_google_url": _social_login_url(request, "google", next_url=next_url),
            "social_facebook_url": _social_login_url(request, "facebook", next_url=next_url),
            "social_apple_url": _social_login_url(request, "apple", next_url=next_url),
        }
        return render(request, self.template_name, ctx)

    @method_decorator(ratelimit(key="post:username", rate="5/m", block=False))
    def post(self, request: HttpRequest) -> HttpResponse:
        was_limited = getattr(request, "limited", False)
        next_url = safe_next(request, fallback=reverse("accounts:profile"))

        form = self.form_class(request, data=request.POST)

        def _ctx():
            return {
                "form": form,
                "next": next_url,
                "social_google_url": _social_login_url(request, "google", next_url=next_url),
                "social_facebook_url": _social_login_url(request, "facebook", next_url=next_url),
                "social_apple_url": _social_login_url(request, "apple", next_url=next_url),
            }

        if was_limited:
            messages.error(request, _("Prea multe încercări. Încearcă din nou în câteva minute."))
            return render(request, self.template_name, _ctx())

        if not form.is_valid():
            email = (request.POST.get("username") or "").strip()
            if email and CustomUser.objects.filter(email__iexact=email, is_active=False).exists():
                messages.warning(
                    request,
                    _("Contul nu este activ. Ți-am trimis emailul de activare sau poți cere re-trimitere.")
                )
            return render(request, self.template_name, _ctx())

        user = form.get_user()

        if not form.cleaned_data.get("remember_me"):
            request.session.set_expiry(0)

        _ensure_session_key(request)
        request.session["pre_login_session_key"] = request.session.session_key

        profile = getattr(user, "profile", None)

        # ---- Trusted-device bypass (only if 2FA enabled)
        td_token = get_trusted_cookie(request)
        if profile and profile.two_factor_enabled and td_token:
            if _trusted_device_match(user, td_token):
                _login_user(request, user)
                return redirect(next_url)

        # ---- 2FA gate
        if profile and profile.two_factor_enabled:
            request.session["pre_2fa_user_id"] = user.id
            request.session["2fa_next"] = next_url

            method = profile.two_factor_method

            if method == "EMAIL":
                send_limit_key = f"2fa_email_send_limit:{user.id}"
                if not cache.get(send_limit_key):
                    code = get_random_string(6, allowed_chars="0123456789")
                    cache.set(f"2fa_email_code:{user.id}", code, 600)
                    cache.set(send_limit_key, True, 30)
                    send_email_2fa_code(user, code)

            elif method == "SMS":
                if profile.phone:
                    send_limit_key = f"2fa_sms_send_limit:{user.id}"
                    daily_key = f"2fa_sms_daily:{user.id}"
                    daily_left = int(cache.get(daily_key, 10))

                    if not cache.get(send_limit_key) and daily_left > 0:
                        code = get_random_string(6, allowed_chars="0123456789")
                        cache.set(f"2fa_sms_code:{user.id}", code, 600)
                        cache.set(send_limit_key, True, 30)
                        cache.set(daily_key, daily_left - 1, 24 * 3600)
                        try:
                            from .notifications import send_sms_2fa_code
                            send_sms_2fa_code(user, code)
                        except Exception:
                            pass
                else:
                    messages.warning(
                        request,
                        _("2FA prin SMS este activat, dar nu există un număr de telefon valid în profil.")
                    )

            return redirect("accounts:two_factor")

        # ---- Normal login
        _login_user(request, user)
        return redirect(next_url)


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """
    ✅ Hardening:
    - POST-only
    - clears trusted-device cookie
    - revokes matching TrustedDevice row (best-effort)
    """
    raw_td = get_trusted_cookie(request)
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

    resp = redirect("accounts:login")

    if user and raw_td:
        _cleanup_trusted_devices(user, raw_cookie_token=raw_td)

    logout(request)
    clear_trusted_cookie(resp)
    return resp


class RegisterView(View):
    form_class = RegisterForm
    template_name = "accounts/auth/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        next_url = safe_next(request, fallback=None)
        return render(
            request,
            self.template_name,
            {
                "form": self.form_class(),
                "next": next_url,
                # ✅ PAS 5.1(1): preserve next through allauth
                "social_google_url": _social_login_url(request, "google", next_url=next_url),
                "social_facebook_url": _social_login_url(request, "facebook", next_url=next_url),
                "social_apple_url": _social_login_url(request, "apple", next_url=next_url),
            },
        )

    @method_decorator(ratelimit(key="post:email", rate="5/m", block=False))
    def post(self, request: HttpRequest) -> HttpResponse:
        was_limited = getattr(request, "limited", False)
        next_url = safe_next(request, fallback=None)

        def _ctx(form_obj):
            return {
                "form": form_obj,
                "next": next_url,
                "social_google_url": _social_login_url(request, "google", next_url=next_url),
                "social_facebook_url": _social_login_url(request, "facebook", next_url=next_url),
                "social_apple_url": _social_login_url(request, "apple", next_url=next_url),
            }

        if was_limited:
            messages.error(request, _("Prea multe încercări. Încearcă din nou în câteva minute."))
            return render(request, self.template_name, _ctx(self.form_class(request.POST)))

        form = self.form_class(request.POST)
        if form.is_valid():
            try:
                user = form.save(
                    ip=client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except (IntegrityError, forms.ValidationError):
                form.add_error("email", _("Există deja un cont cu acest email."))
                return render(request, self.template_name, _ctx(form))

            send_activation_email(user, request, next_url=next_url)
            messages.success(request, _("Verifică-ți email-ul pentru link-ul de activare."))
            return redirect("accounts:registration_email_sent")

        return render(request, self.template_name, _ctx(form))


def registration_email_sent(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/auth/registration_email_sent.html")


def activate_account(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    next_url = safe_next(request, fallback=reverse("accounts:login"))

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except Exception:
        user = None

    if user and account_activation_token.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        try:
            _login_user(request, user)
        except Exception:
            pass

        messages.success(request, _("Cont activat cu succes!"))
        return redirect(next_url or reverse("accounts:login"))

    messages.error(request, _("Link-ul de activare este invalid sau a expirat."))
    return redirect("accounts:registration_email_sent")


@require_POST
@ratelimit(key="post:email", rate="3/h", block=False)
def resend_activation(request: HttpRequest) -> HttpResponse:
    if getattr(request, "limited", False):
        messages.error(request, _("Prea multe cereri. Încearcă mai târziu."))
        return redirect("accounts:registration_email_sent")

    email = (request.POST.get("email") or "").strip().lower()
    user = CustomUser.objects.filter(email__iexact=email).first()

    # no user enumeration
    if not user:
        messages.info(request, _("Dacă adresa există la noi, vei primi un email."))
        return redirect("accounts:registration_email_sent")

    if user.is_active:
        messages.info(request, _("Contul este deja activat."))
        return redirect("accounts:login")

    if cache.get(f"act_resend:{user.pk}"):
        messages.error(request, _("Ai cerut recent re-trimiterea. Încearcă mai târziu."))
        return redirect("accounts:registration_email_sent")

    send_activation_email(user, request, next_url=safe_next(request))
    cache.set(f"act_resend:{user.pk}", True, 3600)
    messages.success(request, _("Am retrimis emailul de activare."))
    return redirect("accounts:registration_email_sent")


# =============================================================================
# 2FA
# =============================================================================

class TwoFactorView(View):
    form_class = TwoFactorForm
    template_name = "accounts/auth/two_factor.html"

    MAX_2FA_ATTEMPTS = 6
    LOCK_SECONDS = 10 * 60  # 10 minutes

    def get(self, request: HttpRequest) -> HttpResponse:
        if not request.session.get("pre_2fa_user_id"):
            return redirect("accounts:login")
        return render(
            request,
            self.template_name,
            {"form": self.form_class(), "next": request.session.get("2fa_next")},
        )

    @method_decorator(ratelimit(key="ip", rate="10/m", block=False))
    def post(self, request: HttpRequest) -> HttpResponse:
        user_id = request.session.get("pre_2fa_user_id")
        next_url = request.session.get("2fa_next") or reverse("accounts:profile")
        if not user_id:
            return redirect("accounts:login")

        lock_key = f"2fa_lock:{user_id}"
        if cache.get(lock_key):
            messages.error(request, _("Prea multe încercări greșite. Încearcă din nou mai târziu."))
            return render(request, self.template_name, {"form": self.form_class(request.POST or None)})

        user = CustomUser.objects.filter(id=user_id).first()
        prof = getattr(user, "profile", None)
        if not user or not prof or not prof.two_factor_enabled:
            return redirect("accounts:login")

        form = self.form_class(request.POST)
        if not form.is_valid():
            messages.error(request, _("Cod invalid."))
            return render(request, self.template_name, {"form": form})

        code = form.cleaned_data["code"].strip()
        ok = False
        method = prof.two_factor_method

        if method == "TOTP" and pyotp and prof.totp_secret:
            totp = pyotp.TOTP(prof.totp_secret)
            ok = totp.verify(code, valid_window=1)

        elif method == "EMAIL":
            real = cache.get(f"2fa_email_code:{user.id}")
            if real is not None and real == code:
                ok = True
                cache.delete(f"2fa_email_code:{user.id}")

        elif method == "SMS":
            real = cache.get(f"2fa_sms_code:{user.id}")
            if real is not None and real == code:
                ok = True
                cache.delete(f"2fa_sms_code:{user.id}")

        if not ok and prof.backup_codes:
            try:
                ok = prof.consume_backup_code(code, commit=True)
            except Exception:
                ok = False

        if ok:
            cache.delete(f"2fa_attempts:{user.id}")
            cache.delete(lock_key)

            try:
                AccountEvent.objects.create(
                    user=user,
                    event=AccountEvent.TWOFA_SUCCESS,
                    ip=client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
                prof.last_2fa_at = timezone.now()
                prof.save(update_fields=["last_2fa_at"])
            except Exception:
                pass

            _login_user(request, user)

            request.session.pop("pre_2fa_user_id", None)
            request.session.pop("2fa_next", None)

            if request.POST.get("remember_device") == "on":
                try:
                    td, raw = TrustedDevice.issue(
                        user,
                        user_agent=request.META.get("HTTP_USER_AGENT", ""),
                        ip=client_ip(request) or "",
                        ttl_days=TRUSTED_DEVICE_TTL_DAYS_DEFAULT,
                        label="Browser",
                    )
                    resp = redirect(next_url)
                    set_trusted_cookie(resp, raw, max_age_days=TRUSTED_DEVICE_TTL_DAYS_DEFAULT)
                    return resp
                except Exception:
                    pass

            return redirect(next_url)

        attempts_key = f"2fa_attempts:{user.id}"
        attempts = int(cache.get(attempts_key, 0)) + 1
        cache.set(attempts_key, attempts, self.LOCK_SECONDS)
        if attempts >= self.MAX_2FA_ATTEMPTS:
            cache.set(lock_key, True, self.LOCK_SECONDS)

        try:
            AccountEvent.objects.create(
                user=user,
                event=AccountEvent.TWOFA_FAIL,
                ip=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except Exception:
            pass

        messages.error(request, _("Cod invalid."))
        return render(request, self.template_name, {"form": form})


@login_required
def enable_2fa(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    if pyotp and not prof.totp_secret:
        prof.totp_secret = pyotp.random_base32()
    prof.two_factor_method = "TOTP"
    prof.save(update_fields=["totp_secret", "two_factor_method"])
    return redirect("accounts:two_factor_setup")


@login_required
def two_factor_setup(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    if not pyotp:
        messages.error(request, _("TOTP indisponibil pe server."))
        return redirect("accounts:profile_security")

    issuer = getattr(settings, "SITE_NAME", "Snobistic")
    totp = pyotp.TOTP(prof.totp_secret)
    otpauth = totp.provisioning_uri(name=request.user.email, issuer_name=issuer)
    return render(request, "accounts/auth/two_factor_setup.html", {"otpauth_uri": otpauth})


@login_required
def two_factor_setup_verify(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("accounts:two_factor_setup")

    prof = request.user.profile
    if not pyotp or not prof.totp_secret:
        return redirect("accounts:profile_security")

    was_enabled = prof.two_factor_enabled
    code = (request.POST.get("code") or "").strip()
    totp = pyotp.TOTP(prof.totp_secret)
    if not totp.verify(code, valid_window=1):
        messages.error(request, _("Cod invalid. Încercați din nou."))
        return redirect("accounts:two_factor_setup")

    prof.two_factor_enabled = True
    prof.two_factor_method = "TOTP"

    raw_codes: list[str] | None = None
    if not was_enabled:
        raw_codes = make_backup_codes()
        prof.set_backup_codes(raw_codes, commit=False)

    prof.save(update_fields=["two_factor_enabled", "two_factor_method", "backup_codes"])

    if raw_codes:
        request.session["backup_codes_once"] = raw_codes

    try:
        sync_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(request.user, "sellerprofile", None)
        if seller:
            sync_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("2FA activat."))
    return redirect("accounts:profile_security")


@login_required
def regenerate_backup_codes(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        prof = request.user.profile
        raw = make_backup_codes()
        prof.set_backup_codes(raw, commit=True)
        request.session["backup_codes_once"] = raw
        messages.success(request, _("Am generat noi coduri de rezervă. (Afișate o singură dată)"))
    return redirect("accounts:profile_security")


@login_required
@require_POST
def disable_2fa(request: HttpRequest) -> HttpResponse:
    """
    ✅ Hardening:
    - POST-only
    - deletes trusted devices (DB)
    - clears trusted cookie (browser)
    ✅ PAS 5.1(2): după disable, sync bonuses (buyer + seller) ca să scoată bonusul
    """
    prof = request.user.profile

    _revoke_all_trusted_devices(request.user)

    prof.two_factor_enabled = False
    prof.two_factor_method = "NONE"
    prof.totp_secret = ""
    prof.backup_codes = []
    prof.last_2fa_at = None

    prof.save(update_fields=["two_factor_enabled", "two_factor_method", "totp_secret", "backup_codes", "last_2fa_at"])

    # ✅ remove 2FA bonus immediately
    try:
        sync_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(request.user, "sellerprofile", None)
        if seller:
            sync_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("Autentificarea cu doi factori a fost dezactivată."))
    resp = redirect("accounts:profile_security")
    clear_trusted_cookie(resp)
    return resp


@login_required
def enable_2fa_email(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    prof.two_factor_method = "EMAIL"
    prof.two_factor_enabled = True
    prof.save(update_fields=["two_factor_method", "two_factor_enabled"])

    try:
        sync_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(request.user, "sellerprofile", None)
        if seller:
            sync_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("2FA prin e-mail a fost activat. Vei primi un cod la autentificare."))
    return redirect("accounts:profile_security")


@login_required
def enable_2fa_sms(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    if not prof.phone:
        messages.error(request, _("Pentru 2FA prin SMS trebuie să adaugi mai întâi un număr de telefon în profil."))
        return redirect("accounts:profile_personal")

    prof.two_factor_method = "SMS"
    prof.two_factor_enabled = True
    prof.save(update_fields=["two_factor_method", "two_factor_enabled"])

    try:
        sync_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(request.user, "sellerprofile", None)
        if seller:
            sync_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("2FA prin SMS a fost activat. Vei primi un cod pe telefon la autentificare."))
    return redirect("accounts:profile_security")


@login_required
@require_POST
def revoke_trusted_device(request: HttpRequest, pk: int) -> HttpResponse:
    td = get_object_or_404(TrustedDevice, pk=pk, user=request.user)
    current_cookie = get_trusted_cookie(request)
    is_current = bool(current_cookie and td.matches(current_cookie))

    td.delete()
    resp = redirect("accounts:profile_security")
    if is_current:
        clear_trusted_cookie(resp)

    messages.success(request, _("Dispozitivul a fost revocat."))
    return resp


# =============================================================================
# Password reset / change
# =============================================================================

class CustomPasswordResetView(PasswordResetView):
    template_name = "accounts/password/password_reset.html"
    email_template_name = "accounts/password/password_reset_email.html"
    subject_template_name = "accounts/password/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def get_email_options(self):
        opts = super().get_email_options()

        domain = (getattr(settings, "PUBLIC_DOMAIN", "") or "").strip() or self.request.get_host()
        opts["domain_override"] = domain

        force_https = bool(getattr(settings, "FORCE_HTTPS_LINKS", False))
        opts["use_https"] = self.request.is_secure() or force_https

        return opts


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        # ✅ Security: password reset should revoke trusted devices too
        try:
            _revoke_all_trusted_devices(self.user)
        except Exception:
            pass
        try:
            clear_trusted_cookie(response)
        except Exception:
            pass
        return response


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password/password_reset_complete.html"


class CustomPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)

        # ✅ Security: password change should revoke trusted devices (force 2FA again on other browsers)
        _revoke_all_trusted_devices(self.request.user)
        clear_trusted_cookie(response)

        try:
            AccountEvent.objects.create(
                user=self.request.user,
                event=AccountEvent.PASSWORD_CHANGE,
                ip=client_ip(self.request),
                user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
            )
        except Exception:
            pass

        return response


class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "accounts/password/password_change_done.html"


# =============================================================================
# Profile
# =============================================================================

@login_required
def profile(request: HttpRequest) -> HttpResponse:
    user = request.user
    prof = user.profile

    favorites_count = Favorite.objects.filter(user=user).count()
    addresses_count = Address.objects.filter(user=user).count()

    required_dimension_fields = ["height_cm", "shoulders", "bust", "waist", "hips", "length", "inseam"]
    dimension_values = [getattr(prof, f, None) for f in required_dimension_fields]
    dimensions_complete = all(bool(v) for v in dimension_values)

    seller = getattr(user, "sellerprofile", None)
    seller_level_label = seller.get_seller_level_display() if seller else None
    seller_commission_label = (
        f"{seller.seller_commission_rate}% comision"
        if (seller and seller.seller_commission_rate is not None)
        else None
    )
    seller_trust_score = seller.seller_trust_score if seller else None

    kyc_status_label = (
        prof.get_kyc_status_display()
        if hasattr(prof, "get_kyc_status_display")
        else str(getattr(prof, "kyc_status", "") or "")
    )

    context = {
        "favorites_count": favorites_count,
        "addresses_count": addresses_count,
        "dimensions_complete": dimensions_complete,
        "seller_level_label": seller_level_label,
        "seller_commission_label": seller_commission_label,
        "seller_trust_score": seller_trust_score,
        "seller_kyc_status_label": kyc_status_label,
    }
    return render(request, "accounts/profile/profile.html", context)


@login_required
def profile_personal(request: HttpRequest) -> HttpResponse:
    """
    ✅ Canonical personal/profile-data view.
    (We keep urls alias profile_data -> same view to stop 404s.)
    """
    prof = request.user.profile

    if request.method == "POST":
        if "save_prefs" in request.POST:
            prefs_form = ProfilePreferencesForm(request.POST, instance=prof)
            form = ProfilePersonalForm(instance=prof)
            if prefs_form.is_valid():
                prefs_form.save()
                messages.success(request, _("Preferințele au fost salvate."))
                return redirect("accounts:profile_personal")
        else:
            form = ProfilePersonalForm(request.POST, request.FILES, instance=prof)
            prefs_form = ProfilePreferencesForm(instance=prof)
            if form.is_valid():
                form.save()
                messages.success(request, _("Datele personale au fost actualizate."))
                return redirect("accounts:profile_personal")
    else:
        form = ProfilePersonalForm(instance=prof)
        prefs_form = ProfilePreferencesForm(instance=prof)

    return render(
        request,
        "accounts/profile/profile_data.html",
        {
            "form": form,
            "prefs_form": prefs_form,
        },
    )


@login_required
def profile_security(request: HttpRequest) -> HttpResponse:
    devices = TrustedDevice.objects.filter(user=request.user).order_by("-last_used_at")
    events = AccountEvent.objects.filter(user=request.user).order_by("-created_at")[:20]

    backup_codes_once = request.session.pop("backup_codes_once", None)

    return render(
        request,
        "accounts/profile/profile_security.html",
        {
            "devices": devices,
            "events": events,
            "backup_codes_once": backup_codes_once,
        },
    )


# =============================================================================
# KYC (user)
# =============================================================================

@login_required
def kyc_center(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile
    kyc_req, _ = KycRequest.objects.get_or_create(user=request.user)
    documents = KycDocument.objects.filter(user=request.user).order_by("-created_at")

    if request.method == "POST":
        form = KycDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.user = request.user
            doc.request = kyc_req

            if not doc.status:
                doc.status = KycDocument.STATUS_PENDING

            doc.save()
            messages.success(request, _("Documentul a fost încărcat. Echipa noastră îl va verifica în cel mai scurt timp."))
            return redirect("accounts:kyc_center")
    else:
        form = KycDocumentForm()

    return render(
        request,
        "accounts/profile/kyc_center.html",
        {
            "profile": prof,
            "kyc_request": kyc_req,
            "documents": documents,
            "form": form,
        },
    )


@login_required
def kyc_document_delete(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(KycDocument, pk=pk, user=request.user)

    if request.method == "POST":
        if doc.status in [KycDocument.STATUS_PENDING, KycDocument.STATUS_REJECTED, KycDocument.STATUS_NEEDS_MORE_INFO]:
            doc.delete()
            messages.success(request, _("Documentul KYC a fost șters."))
        else:
            messages.error(request, _("Nu poți șterge un document KYC care este deja aprobat sau în curs de verificare."))
        return redirect("accounts:kyc_center")

    return render(request, "accounts/profile/kyc_document_confirm_delete.html", {"document": doc})


# =============================================================================
# Addresses
# =============================================================================

@login_required
def address_list(request: HttpRequest) -> HttpResponse:
    addresses = Address.objects.filter(user=request.user).order_by(
        "-is_default_shipping",
        "-is_default_billing",
        "-updated_at",
    )
    return render(
        request,
        "accounts/profile/address_list.html",
        {"addresses": addresses, "user": request.user},
    )


@login_required
def address_form(request: HttpRequest, pk: Optional[int] = None) -> HttpResponse:
    address = get_object_or_404(Address, pk=pk, user=request.user) if pk else None

    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, _("Adresă salvată cu succes."))
            return redirect("accounts:address_list")
    else:
        form = AddressForm(instance=address)

    return render(request, "accounts/profile/address_form.html", {"form": form})


@login_required
@require_POST
def address_delete(request: HttpRequest, pk: int) -> HttpResponse:
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    addr.delete()
    messages.success(request, _("Adresa a fost ștearsă."))
    return redirect("accounts:address_list")


# =============================================================================
# Profile dimensions
# =============================================================================

@login_required
def profile_dimensions(request: HttpRequest) -> HttpResponse:
    prof = request.user.profile

    if request.method == "POST":
        form = ProfileDimensionsForm(request.POST, instance=prof)
        if form.is_valid():
            form.save()
            messages.success(request, _("Măsurătorile au fost salvate."))
            return redirect("accounts:profile_dimensions")
    else:
        form = ProfileDimensionsForm(instance=prof)

    required_dimension_fields = ["height_cm", "shoulders", "bust", "waist", "hips", "length", "inseam"]
    dimension_values = [getattr(prof, f, None) for f in required_dimension_fields]
    dimensions_complete = all(bool(v) for v in dimension_values)

    return render(
        request,
        "accounts/profile/profile_dimensions.html",
        {"form": form, "dimensions_complete": dimensions_complete},
    )


# =============================================================================
# Seller settings + locations
# =============================================================================

@login_required
def seller_settings(request: HttpRequest) -> HttpResponse:
    if not _is_seller(request.user):
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    seller, _ = SellerProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = SellerSettingsForm(request.POST, instance=seller)
        if form.is_valid():
            form.save()
            messages.success(request, _("Setările vânzătorului au fost actualizate."))
            return redirect("accounts:seller_settings")
    else:
        form = SellerSettingsForm(instance=seller)

    locations = request.user.locations.all().order_by("-is_default", "code")
    add_form = SellerLocationForm()

    return render(
        request,
        "accounts/profile/seller_settings.html",
        {"form": form, "locations": locations, "add_form": add_form},
    )


@login_required
@require_POST
def seller_location_add(request: HttpRequest) -> HttpResponse:
    if not _is_seller(request.user):
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    form = SellerLocationForm(request.POST)
    if form.is_valid():
        loc = form.save(commit=False)
        loc.user = request.user
        loc.save()
        messages.success(request, _("Locația a fost adăugată."))
    else:
        messages.error(request, _("Verifică datele locației."))
    return redirect("accounts:seller_settings")


@login_required
@require_POST
def seller_location_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _is_seller(request.user):
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    loc = get_object_or_404(SellerLocation, pk=pk, user=request.user)
    loc.delete()
    messages.success(request, _("Locația a fost ștearsă."))
    return redirect("accounts:seller_settings")


@login_required
@require_POST
def seller_location_make_default(request: HttpRequest, pk: int) -> HttpResponse:
    if not _is_seller(request.user):
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    loc = get_object_or_404(SellerLocation, pk=pk, user=request.user)
    SellerLocation.objects.filter(user=request.user, is_default=True).update(is_default=False)
    loc.is_default = True
    loc.save(update_fields=["is_default"])
    messages.success(request, _("Locația implicită a fost actualizată."))
    return redirect("accounts:seller_settings")


# =============================================================================
# Delete account (email code confirmation)
# =============================================================================

@login_required
@require_POST
@ratelimit(key="user", rate="3/h", block=False)
def delete_account_request(request: HttpRequest) -> HttpResponse:
    if getattr(request, "limited", False):
        messages.error(request, _("Prea multe cereri. Încearcă din nou mai târziu."))
        return redirect("accounts:profile_security")

    code = get_random_string(6, allowed_chars="0123456789")
    cache.set(f"delete_account_code:{request.user.id}", code, 600)

    send_limit_key = f"delete_account_send_limit:{request.user.id}"
    if not cache.get(send_limit_key):
        send_delete_account_code(request.user, code)
        cache.set(send_limit_key, True, 30)

    messages.info(request, _("Ți-am trimis un cod pe email. Introdu-l pentru a confirma ștergerea contului."))
    return redirect("accounts:delete_account_confirm")


@login_required
def delete_account_confirm(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DeleteAccountConfirmForm(request.POST)
        if form.is_valid():
            input_code = form.cleaned_data["code"].strip()
            real_code = cache.get(f"delete_account_code:{request.user.id}")

            if not real_code:
                messages.error(request, _("Codul a expirat. Trimite din nou cererea de ștergere."))
                return redirect("accounts:profile_security")

            if input_code != real_code:
                messages.error(request, _("Cod invalid. Verifică emailul și încearcă din nou."))
                return render(request, "accounts/profile/delete_account_confirm.html", {"form": form})

            user = request.user
            cache.delete(f"delete_account_code:{user.id}")

            resp = redirect("core:home")

            # best-effort: revoke trusted device used by this browser
            raw_td = get_trusted_cookie(request)
            if raw_td:
                _cleanup_trusted_devices(user, raw_cookie_token=raw_td)

            # ✅ PAS 5.1(5): set message before logout (and also re-add after, to survive session flush)
            messages.success(request, _("Contul tău a fost șters."))

            logout(request)
            # re-add in the new anonymous session (survives session flush)
            messages.success(request, _("Contul tău a fost șters."))

            clear_trusted_cookie(resp)

            # delete user after logout
            user.delete()

            return resp
    else:
        form = DeleteAccountConfirmForm()

    return render(request, "accounts/profile/delete_account_confirm.html", {"form": form})


# =============================================================================
# Email change (enterprise)
# =============================================================================

@login_required
@require_POST
@ratelimit(key="user", rate="3/h", block=False)
def email_change_request(request: HttpRequest) -> HttpResponse:
    if getattr(request, "limited", False):
        messages.error(request, _("Prea multe cereri. Încearcă mai târziu."))
        return redirect("accounts:profile_security")

    new_email = (request.POST.get("new_email") or "").strip().lower()
    next_url = safe_next(request, fallback=reverse("accounts:profile_security"))

    if not new_email:
        messages.error(request, _("Email invalid."))
        return redirect("accounts:profile_security")

    if new_email == (request.user.email or "").strip().lower():
        messages.info(request, _("Acesta este deja emailul curent."))
        return redirect("accounts:profile_security")

    if CustomUser.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        messages.error(request, _("Această adresă de email este deja folosită."))
        return redirect("accounts:profile_security")

    try:
        pending = EmailChangeRequest.objects.filter(
            user=request.user, status=EmailChangeRequest.STATUS_PENDING
        ).first()
        if pending:
            pending.status = EmailChangeRequest.STATUS_CANCELLED
            pending.save(update_fields=["status"])
    except Exception:
        pass

    req, token = EmailChangeRequest.issue(
        request.user,
        new_email,
        ttl_hours=24,
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    ok = send_email_change_confirmation(request, request.user, new_email, token, next_url=next_url)
    if not ok and settings.DEBUG:
        messages.error(request, _("Nu am putut trimite emailul (DEBUG). Verifică SMTP/logurile serverului."))

    try:
        AccountEvent.objects.create(
            user=request.user,
            event=AccountEvent.EMAIL_CHANGE_REQUEST,
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
    except Exception:
        pass

    messages.success(request, _("Ți-am trimis un email de confirmare pe noua adresă."))
    return redirect("accounts:profile_security")


@login_required
def email_change_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    next_url = safe_next(request, fallback=reverse("accounts:profile_security"))

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except Exception:
        user = None

    if not user or user.pk != request.user.pk:
        messages.error(request, _("Link invalid."))
        return redirect(next_url)

    req = EmailChangeRequest.objects.filter(user=user, status=EmailChangeRequest.STATUS_PENDING).first()
    if not req:
        messages.error(request, _("Nu există o cerere activă de schimbare a emailului."))
        return redirect(next_url)

    if req.mark_expired_if_needed(commit=True):
        messages.error(request, _("Cererea a expirat. Te rog inițiază din nou schimbarea."))
        return redirect(next_url)

    if not req.matches(token):
        messages.error(request, _("Token invalid."))
        return redirect(next_url)

    if CustomUser.objects.filter(email__iexact=req.new_email).exclude(pk=user.pk).exists():
        req.status = EmailChangeRequest.STATUS_CANCELLED
        req.save(update_fields=["status"])
        messages.error(request, _("Această adresă de email este deja folosită."))
        return redirect(next_url)

    with transaction.atomic():
        user.email = (req.new_email or "").strip().lower()
        user.save(update_fields=["email"])

        req.status = EmailChangeRequest.STATUS_CONFIRMED
        req.confirmed_at = timezone.now()
        req.save(update_fields=["status", "confirmed_at"])

        if EmailAddress is not None:
            try:
                EmailAddress.objects.filter(user=user).update(primary=False)
                ea, _ = EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={"verified": True, "primary": True},
                )
                if not ea.verified or not ea.primary:
                    ea.verified = True
                    ea.primary = True
                    ea.save(update_fields=["verified", "primary"])
            except Exception:
                pass

        try:
            AccountEvent.objects.create(
                user=user,
                event=AccountEvent.EMAIL_CHANGE_CONFIRMED,
                ip=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except Exception:
            pass

    # ✅ revoke trusted devices after email change
    _revoke_all_trusted_devices(user)

    messages.success(request, _("Email actualizat cu succes."))
    resp = redirect(next_url)
    clear_trusted_cookie(resp)
    return resp


# =============================================================================
# GDPR / Sessions
# =============================================================================

@login_required
def gdpr_export(request: HttpRequest) -> HttpResponse:
    messages.info(request, _("Exportul GDPR va fi implementat în următoarea iterație."))
    return redirect("accounts:profile_security")


@login_required
def sessions_center(request: HttpRequest) -> HttpResponse:
    devices = TrustedDevice.objects.filter(user=request.user).order_by("-last_used_at")
    return render(request, "accounts/profile/sessions_center.html", {"devices": devices})


@login_required
@require_POST
@transaction.atomic
def logout_all_sessions(request: HttpRequest) -> HttpResponse:
    TrustedDevice.objects.filter(user=request.user).delete()

    try:
        from django.contrib.sessions.models import Session
        now = timezone.now()
        qs = Session.objects.filter(expire_date__gt=now)
        for s in qs.iterator(chunk_size=500):
            try:
                data = s.get_decoded()
                if str(data.get("_auth_user_id")) == str(request.user.pk):
                    s.delete()
            except Exception:
                continue
    except Exception:
        pass

    resp = redirect("accounts:login")
    logout(request)
    clear_trusted_cookie(resp)

    messages.success(request, _("Ai fost deconectat din toate sesiunile."))
    return resp


# =============================================================================
# Social login (django-allauth)
# =============================================================================

def social_login_start(request: HttpRequest) -> HttpResponse:
    provider = (request.GET.get("provider") or request.POST.get("provider") or "").strip().lower()
    if not provider:
        messages.info(request, _("Alege un provider pentru social login."))
        return redirect("accounts:login")

    url = _reverse_social(provider)
    if not url:
        messages.error(request, _("Social login nu este configurat corect (allauth)."))
        return redirect("accounts:login")

    # ✅ PAS 5.1(1): preserve next on the redirect too (for custom start endpoint)
    next_url = safe_next(request, fallback=None)
    url = add_next_param(url, next_url)
    return redirect(url)


# =============================================================================
# KYC staff (outside admin)
# =============================================================================

@shop_manager_required
def staff_kyc_queue(request: HttpRequest) -> HttpResponse:
    qs = KycRequest.objects.all().order_by(
        models.Case(
            models.When(status="NEEDS_MORE_INFO", then=models.Value(0)),
            models.When(status="IN_REVIEW", then=models.Value(1)),
            models.When(status="NOT_STARTED", then=models.Value(2)),
            models.When(status="REJECTED", then=models.Value(3)),
            models.When(status="APPROVED", then=models.Value(4)),
            default=models.Value(9),
            output_field=models.IntegerField(),
        ),
        "-updated_at",
    )
    return render(request, "accounts/staff/kyc_queue.html", {"requests": qs})


@shop_manager_required
def staff_kyc_review(request: HttpRequest, pk: int) -> HttpResponse:
    kyc_req = get_object_or_404(KycRequest, pk=pk)
    docs = KycDocument.objects.filter(user=kyc_req.user).order_by("-created_at")
    return render(
        request,
        "accounts/staff/kyc_review.html",
        {"kyc_request": kyc_req, "documents": docs},
    )


@shop_manager_required
@transaction.atomic
def staff_kyc_approve(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("accounts:staff_kyc_review", pk=pk)

    kyc_req = get_object_or_404(KycRequest, pk=pk)
    kyc_req.status = KycRequest.STATUS_APPROVED
    kyc_req.reviewed_by = request.user
    kyc_req.reviewed_at = timezone.now()
    kyc_req.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

    try:
        kyc_req.sync_profile_status(commit=True)
    except Exception:
        pass

    # ✅ PAS 5.1(3): KYC influences score immediately
    try:
        prof = getattr(kyc_req.user, "profile", None)
        if prof:
            sync_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(kyc_req.user, "sellerprofile", None)
        if seller:
            sync_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("KYC aprobat."))
    return redirect("accounts:staff_kyc_review", pk=pk)


@shop_manager_required
@transaction.atomic
def staff_kyc_reject(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("accounts:staff_kyc_review", pk=pk)

    kyc_req = get_object_or_404(KycRequest, pk=pk)
    reason = (request.POST.get("reason") or "").strip()

    kyc_req.status = KycRequest.STATUS_REJECTED
    kyc_req.rejection_reason = reason
    kyc_req.reviewed_by = request.user
    kyc_req.reviewed_at = timezone.now()
    kyc_req.save(update_fields=["status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"])

    try:
        kyc_req.sync_profile_status(commit=True)
    except Exception:
        pass

    # ✅ PAS 5.1(3): KYC influences score immediately (bonus removed if it was applied)
    try:
        prof = getattr(kyc_req.user, "profile", None)
        if prof:
            sync_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(kyc_req.user, "sellerprofile", None)
        if seller:
            sync_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("KYC respins."))
    return redirect("accounts:staff_kyc_review", pk=pk)
