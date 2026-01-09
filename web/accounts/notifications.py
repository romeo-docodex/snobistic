# accounts/notifications.py

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import account_activation_token
from .utils import add_next_param

logger = logging.getLogger(__name__)


def _site_name() -> str:
    return getattr(settings, "SITE_NAME", "Snobistic")


def _default_from_email():
    return getattr(settings, "DEFAULT_FROM_EMAIL", None)


def _reply_to_list():
    val = getattr(settings, "SNOBISTIC_REPLY_TO_EMAIL", None)
    return [val] if val else None


def _subject(subject: str) -> str:
    prefix = getattr(settings, "EMAIL_SUBJECT_PREFIX", "") or ""
    return f"{prefix}{subject}"


def _fail_silently() -> bool:
    # În dev vrei să vezi erorile; în prod nu vrei să crape flow-ul userului.
    return not bool(getattr(settings, "DEBUG", False))


def send_activation_email(user, request, next_url=None) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)

    activate_path = reverse("accounts:activate", kwargs={"uidb64": uid, "token": token})
    activate_url = request.build_absolute_uri(activate_path)
    activate_url = add_next_param(activate_url, next_url)

    ctx = {"user": user, "activate_url": activate_url, "site_name": _site_name()}
    subject = _subject(f"{_site_name()} – Activează-ți contul")
    html = render_to_string("accounts/emails/activation.html", ctx)
    text = render_to_string("accounts/emails/activation.txt", ctx)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=_default_from_email(),
            to=[user.email],
            reply_to=_reply_to_list(),
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=_fail_silently())
        return True
    except Exception as exc:
        logger.exception("Activation email send failed (user_id=%s): %s", getattr(user, "pk", None), exc)
        return False


def send_email_2fa_code(user, code) -> bool:
    ctx = {"user": user, "code": code, "site_name": _site_name()}
    subject = _subject(f"{_site_name()} – Cod de autentificare (2FA)")
    html = render_to_string("accounts/emails/2fa_code.html", ctx)
    text = render_to_string("accounts/emails/2fa_code.txt", ctx)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=_default_from_email(),
            to=[user.email],
            reply_to=_reply_to_list(),
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=_fail_silently())
        return True
    except Exception as exc:
        logger.exception("2FA email send failed (user_id=%s): %s", getattr(user, "pk", None), exc)
        return False


def send_delete_account_code(user, code) -> bool:
    subject = _subject(f"{_site_name()} – Confirmare ștergere cont")
    message = (
        f"Bună, {user.first_name or user.email}\n\n"
        f"Codul tău de confirmare pentru ștergerea contului este: {code}\n"
        f"Codul expiră în 10 minute.\n\n"
        f"Dacă nu tu ai inițiat această acțiune, ignoră acest mesaj."
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_default_from_email(),
            recipient_list=[user.email],
            fail_silently=_fail_silently(),
        )
        return True
    except Exception as exc:
        logger.exception("Delete-account email send failed (user_id=%s): %s", getattr(user, "pk", None), exc)
        return False


def send_email_change_confirmation(request, user, new_email: str, token: str, next_url: str | None = None) -> bool:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    url = request.build_absolute_uri(
        reverse("accounts:email_change_confirm", kwargs={"uidb64": uidb64, "token": token})
    )
    url = add_next_param(url, next_url)

    subject = _subject(f"{_site_name()} – Confirmă schimbarea emailului")
    body = (
        f"Bună, {getattr(user, 'full_name', '') or user.email}!\n\n"
        f"Ai cerut schimbarea adresei de email către: {new_email}\n\n"
        f"Confirmă schimbarea accesând linkul:\n{url}\n\n"
        f"Dacă nu tu ai făcut cererea, ignoră acest mesaj.\n"
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=_default_from_email(),
            to=[new_email],
            reply_to=_reply_to_list(),
        )
        msg.send(fail_silently=_fail_silently())
        return True
    except Exception as exc:
        logger.exception("Email-change confirmation send failed (user_id=%s): %s", getattr(user, "pk", None), exc)
        return False
