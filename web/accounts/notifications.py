# accounts/notifications.py
import logging
from importlib import import_module

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse

from .tokens import account_activation_token

logger = logging.getLogger(__name__)


def _default_from_email():
    return getattr(settings, "DEFAULT_FROM_EMAIL", None)


def send_activation_email(user, request, next_url=None):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)

    activate_path = reverse("accounts:activate", kwargs={"uidb64": uid, "token": token})
    if next_url:
        activate_url = f"{request.scheme}://{request.get_host()}{activate_path}?next={next_url}"
    else:
        activate_url = f"{request.scheme}://{request.get_host()}{activate_path}"

    ctx = {"user": user, "activate_url": activate_url, "site_name": "Snobistic"}
    subject = "Activează-ți contul Snobistic"
    html = render_to_string("accounts/emails/activation.html", ctx)
    text = render_to_string("accounts/emails/activation.txt", ctx)

    msg = EmailMultiAlternatives(subject, text, _default_from_email(), [user.email])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


def send_email_2fa_code(user, code):
    ctx = {"user": user, "code": code}
    subject = "Codul tău de autentificare (2FA)"
    html = render_to_string("accounts/emails/2fa_code.html", ctx)
    text = render_to_string("accounts/emails/2fa_code.txt", ctx)
    msg = EmailMultiAlternatives(subject, text, _default_from_email(), [user.email])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


def send_delete_account_code(user, code):
    subject = "Confirmare ștergere cont"
    message = (
        f"Bună, {user.first_name or user.email}\n\n"
        f"Codul tău de confirmare pentru ștergerea contului este: {code}\n"
        f"Codul expiră în 10 minute.\n\n"
        f"Dacă nu tu ai inițiat această acțiune, ignoră acest mesaj."
    )
    send_mail(
        subject,
        message,
        _default_from_email(),
        [user.email],
        fail_silently=False,
    )


def send_sms_2fa_code(user, code: str) -> None:
    """
    Helper generic pentru 2FA prin SMS.

    Se bazează pe o setare opțională:
        SNOBISTIC_SMS_2FA_BACKEND = "module.path.func_name"

    Funcția target trebuie să aibă semnătura:
        func(phone_number_str: str, code: str) -> None
    """
    phone = getattr(getattr(user, "profile", None), "phone", None)
    if not phone:
        logger.warning("Nu există număr de telefon pe profil pentru 2FA SMS (user_id=%s).", user.pk)
        return

    backend_path = getattr(settings, "SNOBISTIC_SMS_2FA_BACKEND", None)
    if not backend_path:
        # Nu blocăm nimic – doar logăm. Poți decide ulterior să ridici excepție dacă vrei strict.
        logger.warning(
            "SNOBISTIC_SMS_2FA_BACKEND nu este configurat. "
            "Nu pot trimite SMS 2FA pentru user_id=%s, code=%s.",
            user.pk,
            code,
        )
        return

    try:
        module_path, func_name = backend_path.rsplit(".", 1)
        mod = import_module(module_path)
        func = getattr(mod, func_name)
    except Exception as exc:
        logger.error("Nu pot importa backend-ul SMS 2FA (%s): %s", backend_path, exc)
        return

    try:
        # PhoneNumberField => îl convertim la string simplu
        func(str(phone), code)
    except Exception as exc:
        logger.error("Eroare la trimiterea SMS 2FA către %s: %s", phone, exc)
