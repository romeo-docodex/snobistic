# accounts/views.py

# --- Optional rate limiting (django-ratelimit). Falls back to no-op if not installed.
try:
    from ratelimit.decorators import ratelimit  # pip install django-ratelimit
except Exception:
    def ratelimit(*args, **kwargs):
        def _decorator(view_func):
            return view_func
        return _decorator

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView,
    PasswordChangeView, PasswordChangeDoneView,
)
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views import View
from django.utils.translation import gettext as _
from django.utils import timezone
from django.core.cache import cache
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils.decorators import method_decorator
from django.utils.crypto import get_random_string

from .forms import (
    LoginForm, RegisterForm, TwoFactorForm,
    ProfilePersonalForm, ProfilePreferencesForm,
    AddressForm, ProfileDimensionsForm,
    SellerSettingsForm, SellerLocationForm,
    DeleteAccountConfirmForm,
)
from .tokens import account_activation_token
from .models import (
    CustomUser, Address, Profile,
    TrustedDevice, SellerProfile, SellerLocation,
    AccountEvent,
)
from .utils import safe_next, client_ip, set_trusted_cookie, get_trusted_cookie, clear_trusted_cookie
from .notifications import (
    send_activation_email,
    send_email_2fa_code,
    send_delete_account_code,
)
from .services.score import (
    apply_buyer_identity_bonuses,
    apply_seller_identity_bonuses,
)

from catalog.models import Favorite

try:
    import pyotp
except Exception:
    pyotp = None


def make_backup_codes(n=10, length=8):
    # alfabet fără caractere ușor de confundat (fără 0/O și 1/I)
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    from django.utils.crypto import get_random_string as _grs
    return [_grs(length, allowed_chars=alphabet) for _ in range(n)]


# ===============================
# Authentication
# ===============================

class LoginView(View):
    form_class = LoginForm
    template_name = 'accounts/auth/login.html'

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    @method_decorator(ratelimit(key="post:username", rate="5/m", block=False))
    def post(self, request):
        was_limited = getattr(request, "limits", False)
        next_url = safe_next(request, fallback=reverse("accounts:profile"))

        form = self.form_class(request, data=request.POST)

        if was_limited:
            messages.error(request, _("Prea multe încercări. Încearcă din nou în câteva minute."))
            return render(request, self.template_name, {'form': form})

        if form.is_valid():
            user = form.get_user()

            # Remember me
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)  # expires on browser close

            # Stash pre-login session key (for cart merge reliability)
            request.session['pre_login_session_key'] = request.session.session_key

            profile = getattr(user, "profile", None)

            # 2FA bypass via trusted device
            td_token = get_trusted_cookie(request)
            if td_token:
                for td in user.trusted_devices.all():
                    if td.matches(td_token) and td.expires_at > timezone.now():
                        login(request, user)  # user_logged_in signal will log the event
                        return redirect(next_url)

            # 2FA gating
            if profile and profile.two_factor_enabled:
                request.session['pre_2fa_user_id'] = user.id
                request.session['2fa_next'] = next_url

                method = profile.two_factor_method

                # EMAIL – generăm codul de 6 cifre și îl trimitem
                if method == "EMAIL":
                    key = f"2fa_email_send_limit:{user.id}"
                    if not cache.get(key):
                        from django.utils.crypto import get_random_string as _grs
                        code = _grs(6, allowed_chars="0123456789")
                        cache.set(f"2fa_email_code:{user.id}", code, 600)  # 10 minute
                        cache.set(key, True, 30)  # 1 send / 30s
                        send_email_2fa_code(user, code)

                # SMS – opțional, dacă utilizatorul are telefon salvat
                elif method == "SMS":
                    if profile.phone:
                        # throttle simplu: max 1 SMS / 30s și 10 SMS / zi
                        limit_key = f"2fa_sms_send_limit:{user.id}"
                        daily_key = f"2fa_sms_daily:{user.id}"
                        daily_left = cache.get(daily_key, 10)

                        if not cache.get(limit_key) and daily_left > 0:
                            from django.utils.crypto import get_random_string as _grs
                            code = _grs(6, allowed_chars="0123456789")
                            cache.set(f"2fa_sms_code:{user.id}", code, 600)  # 10 minute
                            cache.set(limit_key, True, 30)  # 1 SMS / 30 sec
                            cache.set(daily_key, daily_left - 1, 24 * 3600)
                            try:
                                # lazy import ca să nu stricăm importurile dacă backend-ul lipsește
                                from .notifications import send_sms_2fa_code
                                send_sms_2fa_code(user, code)
                            except Exception:
                                # dacă SMS-ul eșuează, nu blocăm complet login flow;
                                # userul poate folosi alte metode (după ce le implementăm)
                                pass
                    else:
                        messages.warning(
                            request,
                            _("2FA prin SMS este activat, dar nu există un număr de telefon valid în profil.")
                        )

                return redirect('accounts:two_factor')

            # No 2FA: login now (signal handles audit + cart merge)
            login(request, user)
            return redirect(next_url)

        # If user inactive, show resend CTA hint
        email = request.POST.get("username")
        if email and CustomUser.objects.filter(email=email, is_active=False).exists():
            messages.warning(
                request,
                _("Contul nu este activ. Ți-am trimis emailul de activare sau poți cere re-trimitere.")
            )

        return render(request, self.template_name, {'form': form})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


class RegisterView(View):
    form_class = RegisterForm
    template_name = 'accounts/auth/register.html'

    def get(self, request):
        return render(request, self.template_name, {'form': self.form_class()})

    @method_decorator(ratelimit(key="post:email", rate="5/m", block=False))
    def post(self, request):
        form = self.form_class(request.POST)
        next_url = safe_next(request, fallback=None)
        if form.is_valid():
            user = form.save()
            send_activation_email(user, request, next_url=next_url)
            messages.success(request, _('Verifică-ți email-ul pentru link-ul de activare.'))
            return redirect('accounts:registration_email_sent')
        return render(request, self.template_name, {'form': form})


def registration_email_sent(request):
    return render(request, 'accounts/auth/registration_email_sent.html')


def activate_account(request, uidb64, token):
    next_url = safe_next(request, fallback=reverse("accounts:login"))
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except Exception:
        user = None

    if user and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, _('Cont activat cu succes!'))
        return redirect(next_url or 'accounts:login')

    messages.error(request, _('Link-ul de activare este invalid sau a expirat.'))
    return redirect('accounts:registration_email_sent')


@ratelimit(key="post:email", rate="3/h", block=False)
def resend_activation(request):
    if request.method != "POST":
        return redirect("accounts:login")

    email = (request.POST.get("email") or "").strip().lower()
    user = CustomUser.objects.filter(email=email).first()
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
    cache.set(f"act_resend:{user.pk}", True, 3600)  # 1 hour
    messages.success(request, _("Am retrimis emailul de activare."))
    return redirect("accounts:registration_email_sent")


# ===============================
# Two-Factor Authentication
# ===============================

class TwoFactorView(View):
    form_class = TwoFactorForm
    template_name = 'accounts/auth/two_factor.html'

    def get(self, request):
        if not request.session.get('pre_2fa_user_id'):
            return redirect('accounts:login')
        return render(request, self.template_name, {'form': self.form_class()})

    @method_decorator(ratelimit(key="ip", rate="10/m", block=False))
    def post(self, request):
        user_id = request.session.get('pre_2fa_user_id')
        next_url = request.session.get('2fa_next') or reverse("accounts:profile")
        if not user_id:
            return redirect('accounts:login')

        user = CustomUser.objects.filter(id=user_id).first()
        prof = getattr(user, "profile", None)
        if not user or not prof or not prof.two_factor_enabled:
            return redirect('accounts:login')

        form = self.form_class(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code'].strip()
            ok = False
            method = prof.two_factor_method

            # Metoda principală, în funcție de tip
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

            # Dacă nu a mers metoda principală, încercăm backup codes
            if not ok and prof.backup_codes:
                backup_list = [c.strip() for c in (prof.backup_codes or [])]
                if code in backup_list:
                    ok = True
                    # Backup code folosit -> îl scoatem din listă
                    backup_list.remove(code)
                    prof.backup_codes = backup_list
                    prof.save(update_fields=["backup_codes"])

            if ok:
                # Logăm 2FA success + updatăm last_2fa_at
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

                login(request, user)  # user_logged_in signal will handle audit + cart merge
                request.session.pop('pre_2fa_user_id', None)

                # Remember this device for 30 days
                if request.POST.get("remember_device") == "on":
                    try:
                        TDModel = user.trusted_devices.model  # the TrustedDevice class
                        td, raw = TDModel.issue(
                            user,
                            user_agent=request.META.get("HTTP_USER_AGENT", ""),
                            ip=client_ip(request),
                            ttl_days=30,
                        )
                        # set cookie
                        resp = redirect(next_url)
                        set_trusted_cookie(resp, raw, max_age_days=30)
                        return resp
                    except Exception:
                        pass  # if something goes wrong, just continue

                return redirect(next_url)
            else:
                # Logăm 2FA fail
                try:
                    AccountEvent.objects.create(
                        user=user,
                        event=AccountEvent.TWOFA_FAIL,
                        ip=client_ip(request),
                        user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    )
                except Exception:
                    pass

        messages.error(request, _('Cod invalid.'))
        return render(request, self.template_name, {'form': form})


@login_required
def enable_2fa(request):
    """
    Activează fluxul TOTP (Google Authenticator etc.).
    Efectiv 2FA devine activ după ce user-ul scanează codul și îl confirmă
    în two_factor_setup_verify.
    """
    prof = request.user.profile
    if pyotp and not prof.totp_secret:
        # secret de minim 160 biți (default pyotp.random_base32() este OK)
        prof.totp_secret = pyotp.random_base32()
    prof.two_factor_method = "TOTP"
    prof.save()
    return redirect("accounts:two_factor_setup")


@login_required
def two_factor_setup(request):
    prof = request.user.profile
    if not pyotp:
        messages.error(request, _("TOTP indisponibil pe server."))
        return redirect("accounts:profile_security")

    issuer = "Snobistic"
    totp = pyotp.TOTP(prof.totp_secret)
    otpauth = totp.provisioning_uri(name=request.user.email, issuer_name=issuer)
    return render(request, "accounts/auth/two_factor_setup.html", {"otpauth_uri": otpauth})


@login_required
def two_factor_setup_verify(request):
    if request.method != "POST":
        return redirect("accounts:two_factor_setup")

    prof = request.user.profile
    if not pyotp or not prof.totp_secret:
        return redirect("accounts:profile_security")

    was_enabled = prof.two_factor_enabled
    code = (request.POST.get("code") or "").strip()
    totp = pyotp.TOTP(prof.totp_secret)
    if totp.verify(code, valid_window=1):
        prof.two_factor_enabled = True
        prof.two_factor_method = "TOTP"
        # generează coduri de rezervă „umane”
        if not was_enabled:
            prof.backup_codes = make_backup_codes()
        prof.save()

        # Bonus identitate pentru scor (2FA + eventual KYC)
        try:
            apply_buyer_identity_bonuses(prof, commit=True)
            seller = getattr(request.user, "sellerprofile", None)
            if seller:
                apply_seller_identity_bonuses(seller, commit=True)
        except Exception:
            pass

        messages.success(request, _("2FA activat și coduri de rezervă generate."))
    else:
        messages.error(request, _("Cod invalid. Încercați din nou."))
        return redirect("accounts:two_factor_setup")

    return redirect("accounts:profile_security")


@login_required
def regenerate_backup_codes(request):
    if request.method == "POST":
        prof = request.user.profile
        prof.backup_codes = make_backup_codes()
        prof.save()
        messages.success(request, _("Am generat noi coduri de rezervă."))
    return redirect("accounts:profile_security")


@login_required
def disable_2fa(request):
    profile = request.user.profile
    profile.two_factor_enabled = False
    profile.two_factor_method = "NONE"
    profile.save()
    messages.success(request, _("Autentificarea cu doi factori a fost dezactivată."))
    return redirect('accounts:profile_security')


# ===============================
# Password reset / change
# ===============================

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password/password_reset.html'
    email_template_name = 'accounts/password/password_reset_email.html'
    subject_template_name = 'accounts/password/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password/password_reset_complete.html'


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')

    def form_valid(self, form):
        response = super().form_valid(form)
        # Logăm evenimentul de schimbare parolă
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
    template_name = 'accounts/password/password_change_done.html'


# ===============================
# Profile area
# ===============================

@login_required
def profile(request):
    user = request.user
    profile = user.profile

    # Favorite
    favorites_count = Favorite.objects.filter(user=user).count()

    # Adrese
    addresses_count = Address.objects.filter(user=user).count()

    # Dimensiuni – considerăm „complet” dacă utilizatorul are înălțimea +
    # câteva măsurători de bază (greutatea rămâne opțională).
    required_dimension_fields = [
        "height_cm",
        "shoulders",
        "bust",
        "waist",
        "hips",
        "length",
        "inseam",
    ]
    dimension_values = [getattr(profile, f, None) for f in required_dimension_fields]
    dimensions_complete = all(bool(v) for v in dimension_values)

    # Profil vânzător
    seller = getattr(user, "sellerprofile", None)
    seller_level_label = None
    seller_commission_label = None
    seller_trust_score = None

    if seller:
        # Nivel vânzător (folosim get_level_display dacă există choices)
        if hasattr(seller, "get_level_display"):
            seller_level_label = seller.get_level_display()
        else:
            seller_level_label = getattr(seller, "level", None)

        # Comision – acceptă commission_percent sau commission
        commission = getattr(seller, "commission_percent", None)
        if commission is None:
            commission = getattr(seller, "commission", None)
        if commission is not None:
            seller_commission_label = f"{commission}% comision"

        # Trust score
        seller_trust_score = getattr(seller, "trust_score", None)

    # KYC status – de obicei pe profil
    kyc_status_label = None
    if hasattr(profile, "get_kyc_status_display"):
        kyc_status_label = profile.get_kyc_status_display()
    else:
        kyc_raw = getattr(profile, "kyc_status", None)
        if kyc_raw:
            kyc_status_label = str(kyc_raw)

    context = {
        "favorites_count": favorites_count,
        "addresses_count": addresses_count,
        "dimensions_complete": dimensions_complete,
        "seller_level_label": seller_level_label,
        "seller_commission_label": seller_commission_label,
        "seller_trust_score": seller_trust_score,
        "seller_kyc_status_label": kyc_status_label,
    }

    return render(
        request,
        "accounts/profile/profile.html",
        context,
    )


@login_required
def profile_data(request):
    profile = request.user.profile

    if request.method == 'POST':
        if 'save_prefs' in request.POST:
            prefs_form = ProfilePreferencesForm(request.POST, instance=profile)
            form = ProfilePersonalForm(instance=profile)  # nu legăm celălalt form
            if prefs_form.is_valid():
                prefs_form.save()
                messages.success(request, _("Preferințele au fost salvate."))
                return redirect('accounts:profile_data')
        else:
            form = ProfilePersonalForm(request.POST, request.FILES, instance=profile)
            prefs_form = ProfilePreferencesForm(instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, _("Datele personale au fost actualizate."))
                return redirect('accounts:profile_data')
    else:
        form = ProfilePersonalForm(instance=profile)
        prefs_form = ProfilePreferencesForm(instance=profile)

    return render(request, 'accounts/profile/profile_data.html', {
        'form': form,
        'prefs_form': prefs_form,
    })


@login_required
def profile_security(request):
    devices = TrustedDevice.objects.filter(user=request.user).order_by('-last_used_at')
    events = AccountEvent.objects.filter(user=request.user).order_by('-created_at')[:20]

    return render(
        request,
        'accounts/profile/profile_security.html',
        {
            "devices": devices,
            "events": events,
        },
    )


# ===============================
# KYC – upload & overview (user)
# ===============================

@login_required
def kyc_center(request):
    """
    Pagina centrală KYC pentru utilizator:
    - vede statusul KYC din profil
    - vede documentele încărcate
    - poate încărca un document nou
    """
    profile = request.user.profile

    # import local pentru a evita probleme dacă nu ai migrat încă
    try:
        from .models import KycDocument
        from .forms import KycDocumentForm
    except Exception:
        KycDocument = None
        KycDocumentForm = None

    documents = []
    form = None

    if KycDocument and KycDocumentForm:
        documents = KycDocument.objects.filter(user=request.user).order_by("-created_at")

        if request.method == "POST":
            form = KycDocumentForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.user = request.user
                # când userul încarcă, status-ul inițial este PENDING
                if not doc.status:
                    doc.status = KycDocument.STATUS_PENDING
                doc.save()
                messages.success(
                    request,
                    _("Documentul a fost încărcat. Echipa noastră îl va verifica în cel mai scurt timp.")
                )
                return redirect("accounts:kyc_center")
        else:
            form = KycDocumentForm()

    context = {
        "profile": profile,
        "documents": documents,
        "form": form,
    }
    return render(request, "accounts/profile/kyc_center.html", context)


@login_required
def kyc_document_delete(request, pk):
    """
    Permite ștergerea unui document KYC propriu,
    doar dacă este în status PENDING sau REJECTED.
    """
    try:
        from .models import KycDocument
    except Exception:
        messages.error(request, _("Sistemul KYC nu este disponibil momentan."))
        return redirect("accounts:kyc_center")

    doc = get_object_or_404(KycDocument, pk=pk, user=request.user)

    if request.method == "POST":
        if doc.status in [KycDocument.STATUS_PENDING, KycDocument.STATUS_REJECTED]:
            doc.delete()
            messages.success(request, _("Documentul KYC a fost șters."))
        else:
            messages.error(
                request,
                _("Nu poți șterge un document KYC care este deja aprobat sau în curs de verificare.")
            )
        return redirect("accounts:kyc_center")

    # GET – afișăm o pagină simplă de confirmare
    return render(request, "accounts/profile/kyc_document_confirm_delete.html", {"document": doc})


# ===============================
# Addresses
# ===============================

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'accounts/profile/address_list.html', {
        'addresses': addresses,
        'user': request.user,
    })


@login_required
def address_form(request, pk=None):
    address = get_object_or_404(Address, pk=pk, user=request.user) if pk else None
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, _('Adresă salvată cu succes.'))
            return redirect('accounts:address_list')
    else:
        form = AddressForm(instance=address)
    return render(request, 'accounts/profile/address_form.html', {'form': form})


@login_required
def address_delete(request, pk):
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        addr.delete()
        messages.success(request, _("Adresa a fost ștearsă."))
    return redirect('accounts:address_list')


# ===============================
# Profile – măsurători
# ===============================

@login_required
def profile_dimensions(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileDimensionsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("Măsurătorile au fost salvate."))
            return redirect("accounts:profile_dimensions")
    else:
        form = ProfileDimensionsForm(instance=profile)

    # Status pentru badge (aceeași logică ca în dashboard)
    required_dimension_fields = [
        "height_cm",
        "shoulders",
        "bust",
        "waist",
        "hips",
        "length",
        "inseam",
    ]
    dimension_values = [getattr(profile, f, None) for f in required_dimension_fields]
    dimensions_complete = all(bool(v) for v in dimension_values)

    return render(
        request,
        "accounts/profile/profile_dimensions.html",
        {
            "form": form,
            "dimensions_complete": dimensions_complete,
        },
    )


# ===============================
# 2FA – EMAIL + SMS + Trusted devices
# ===============================

@login_required
def enable_2fa_email(request):
    """
    Activează metoda de 2FA prin e-mail:
    - la login, userul primește un cod pe email.
    """
    prof = request.user.profile
    prof.two_factor_method = "EMAIL"
    prof.two_factor_enabled = True
    prof.save()

    # Bonus identitate pentru scor (2FA + eventual KYC)
    try:
        apply_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(request.user, "sellerprofile", None)
        if seller:
            apply_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(request, _("2FA prin e-mail a fost activat. Vei primi un cod la autentificare."))
    return redirect("accounts:profile_security")


@login_required
def enable_2fa_sms(request):
    """
    Activează metoda de 2FA prin SMS:
    - necesită un număr de telefon valid în profil.
    """
    prof = request.user.profile
    if not prof.phone:
        messages.error(
            request,
            _("Pentru 2FA prin SMS trebuie să adaugi mai întâi un număr de telefon în profil.")
        )
        return redirect("accounts:profile_data")

    prof.two_factor_method = "SMS"
    prof.two_factor_enabled = True
    prof.save()

    # Bonus identitate pentru scor (2FA + eventual KYC)
    try:
        apply_buyer_identity_bonuses(prof, commit=True)
        seller = getattr(request.user, "sellerprofile", None)
        if seller:
            apply_seller_identity_bonuses(seller, commit=True)
    except Exception:
        pass

    messages.success(
        request,
        _("2FA prin SMS a fost activat. Vei primi un cod pe telefon la autentificare.")
    )
    return redirect("accounts:profile_security")


@login_required
def revoke_trusted_device(request, pk):
    td = get_object_or_404(TrustedDevice, pk=pk, user=request.user)
    # Acceptăm doar POST pentru acțiune
    if request.method == "POST":
        current_cookie = get_trusted_cookie(request)
        if current_cookie and td.matches(current_cookie):
            # Revocăm chiar dispozitivul curent – ștergem și cookie-ul
            td.delete()
            resp = redirect("accounts:profile_security")
            clear_trusted_cookie(resp)
            messages.success(request, _("Dispozitivul a fost revocat și acest browser a fost uitat."))
            return resp
        td.delete()
        messages.success(request, _("Dispozitivul a fost revocat."))
    return redirect("accounts:profile_security")


# ===============================
# Seller – setări + locații
# ===============================

@login_required
def seller_settings(request):
    if not request.user.is_seller:
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
def seller_location_add(request):
    if not request.user.is_seller:
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    if request.method != "POST":
        return redirect("accounts:seller_settings")

    form = SellerLocationForm(request.POST)
    if form.is_valid():
        loc = form.save(commit=False)
        loc.user = request.user
        loc.save()
        if loc.is_default:
            SellerLocation.objects.filter(
                user=request.user,
                is_default=True
            ).exclude(pk=loc.pk).update(is_default=False)
        messages.success(request, _("Locația a fost adăugată."))
    else:
        messages.error(request, _("Verifică datele locației."))
    return redirect("accounts:seller_settings")


@login_required
def seller_location_delete(request, pk):
    if not request.user.is_seller:
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    loc = get_object_or_404(SellerLocation, pk=pk, user=request.user)
    if request.method == "POST":
        loc.delete()
        messages.success(request, _("Locația a fost ștearsă."))
    return redirect("accounts:seller_settings")


@login_required
def seller_location_make_default(request, pk):
    if not request.user.is_seller:
        messages.error(request, _("Această secțiune este disponibilă doar vânzătorilor."))
        return redirect("accounts:profile")

    loc = get_object_or_404(SellerLocation, pk=pk, user=request.user)
    if request.method == "POST":
        SellerLocation.objects.filter(user=request.user, is_default=True).update(is_default=False)
        loc.is_default = True
        loc.save()
        messages.success(request, _("Locația implicită a fost actualizată."))
    return redirect("accounts:seller_settings")


# ===============================
# Delete account (email code confirmation)
# ===============================

@login_required
@ratelimit(key="user", rate="3/h", block=False)
def delete_account_request(request):
    # Accept doar POST – apasă pe butonul din pagina de securitate
    if request.method != "POST":
        return redirect("accounts:profile_security")

    was_limited = getattr(request, "limits", False)
    if was_limited:
        messages.error(request, _("Prea multe cereri. Încearcă din nou mai târziu."))
        return redirect("accounts:profile_security")

    # Generează cod, salvează-l în cache 10 minute
    code = get_random_string(6, allowed_chars="0123456789")
    cache.set(f"delete_account_code:{request.user.id}", code, 600)  # 10 minute
    # Throttle ușor trimiterea
    if not cache.get(f"delete_account_send_limit:{request.user.id}"):
        send_delete_account_code(request.user, code)
        cache.set(f"delete_account_send_limit:{request.user.id}", True, 30)  # 30 secunde

    messages.info(request, _("Ți-am trimis un cod pe email. Introdu-l pentru a confirma ștergerea contului."))
    return redirect("accounts:delete_account_confirm")


@login_required
def delete_account_confirm(request):
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

            # Cod valid – șterge contul
            user = request.user
            cache.delete(f"delete_account_code:{user.id}")

            # Deloghează sesiunea curentă după ștergere
            user.delete()
            logout(request)

            messages.success(request, _("Contul tău a fost șters. Ne pare rău să te vedem plecând!"))
            return redirect("core:home")
    else:
        form = DeleteAccountConfirmForm()

    return render(request, "accounts/profile/delete_account_confirm.html", {"form": form})
