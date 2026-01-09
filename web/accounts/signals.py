# accounts/signals.py

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    AccountEvent,
    CustomUser,
    Profile,
    SellerLocation,
    SellerProfile,
)
from .utils import client_ip


def _default_loc3(user: CustomUser) -> str:
    base = (user.last_name or user.first_name or user.email.split("@")[0]).upper()
    letters = "".join(ch for ch in base if ch.isalpha())
    return (letters[:3] or "USR").ljust(3, "X")


def _ensure_default_location(user: CustomUser) -> None:
    qs = user.locations.all()
    if not qs.exists():
        SellerLocation.objects.create(
            user=user,
            code=_default_loc3(user),
            is_default=True,
        )
        return

    if not qs.filter(is_default=True).exists():
        first = qs.order_by("id").first()
        if first:
            SellerLocation.objects.filter(pk=first.pk).update(is_default=True)


@receiver(post_save, sender=CustomUser)
def ensure_related_profiles(sender, instance: CustomUser, created: bool, **kwargs):
    """
    ✅ Source-of-truth: Profile.role_seller.
    - Bootstrap: dacă user.is_seller=True la creare (legacy/admin), ridicăm Profile.role_seller=True o singură dată.
    - Sync: user.is_seller devine DERIVAT din Profile.role_seller (prevent contradictions).
    - Seller artifacts (SellerProfile + default location) doar dacă role_seller truth e True.
    """
    if kwargs.get("raw"):
        return

    prof, prof_created = Profile.objects.get_or_create(user=instance)

    # Bootstrap: allow legacy is_seller only at creation (admin add) to lift into truth.
    if (created or prof_created) and bool(instance.is_seller) and not bool(prof.role_seller):
        prof.role_seller = True
        prof.save(update_fields=["role_seller"])

    # Always keep legacy flag aligned to truth
    truth = bool(prof.role_seller)
    if bool(instance.is_seller) != truth:
        CustomUser.objects.filter(pk=instance.pk).update(is_seller=truth)
        instance.is_seller = truth

    # Seller artifacts
    if truth:
        SellerProfile.objects.get_or_create(user=instance)
        _ensure_default_location(instance)


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    try:
        AccountEvent.objects.create(
            user=user,
            event=AccountEvent.LOGIN_SUCCESS,
            ip=client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
        )
    except Exception:
        pass

    # Merge guest session cart -> user cart (best-effort)
    try:
        from cart.utils import merge_session_cart_to_user

        pre_key = request.session.pop("pre_login_session_key", None)
        merge_session_cart_to_user(user, request.session, pre_key)
    except Exception:
        pass

    # Merge favorites from session -> DB
    try:
        from catalog.models import Favorite, Product

        raw = request.session.get("favorites") or []
        pks = []
        for x in raw:
            try:
                pks.append(int(x))
            except Exception:
                pass

        if pks:
            exist = set(
                Favorite.objects.filter(user=user, product_id__in=pks).values_list("product_id", flat=True)
            )
            to_add = set(pks) - exist
            if to_add:
                valid_ids = set(
                    Product.objects.filter(pk__in=to_add, is_active=True).values_list("pk", flat=True)
                )
                Favorite.objects.bulk_create(
                    [Favorite(user=user, product_id=pid) for pid in valid_ids],
                    ignore_conflicts=True,
                )
            request.session.pop("favorites", None)
    except Exception:
        pass


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    try:
        email = (credentials or {}).get("username") or (credentials or {}).get("email")
        if not email:
            return

        u = CustomUser.objects.filter(email__iexact=email).first()
        if not u:
            return

        AccountEvent.objects.create(
            user=u,
            event=AccountEvent.LOGIN_FAIL,
            ip=client_ip(request) if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
        )
    except Exception:
        pass
