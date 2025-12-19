# accounts/signals.py
from __future__ import annotations

from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    CustomUser,
    Profile,
    SellerProfile,
    SellerLocation,
    AccountEvent,
)
from .utils import client_ip

from catalog.models import Favorite


def _default_loc3(user: CustomUser) -> str:
    base = (user.last_name or user.first_name or user.email.split("@")[0]).upper()
    letters = "".join(ch for ch in base if ch.isalpha())
    return (letters[:3] or "USR").ljust(3, "X")


# ---- Ensure related profiles/locations exist --------------------------------

@receiver(post_save, sender=CustomUser)
def ensure_related_profiles(sender, instance: CustomUser, created, **kwargs):
    # Asigurăm existența profilului și sincronizăm rolurile de bază.
    prof, _ = Profile.objects.get_or_create(user=instance)

    changed = False
    # role_seller urmărește flag-ul de business is_seller
    if instance.is_seller and not prof.role_seller:
        prof.role_seller = True
        changed = True
    if not instance.is_seller and prof.role_seller:
        prof.role_seller = False
        changed = True

    if changed:
        prof.save(update_fields=["role_seller"])

    # Creăm profilul de vânzător + locația implicită doar dacă userul e vânzător
    if instance.is_seller:
        SellerProfile.objects.get_or_create(user=instance)
        if not instance.locations.exists():
            SellerLocation.objects.create(
                user=instance,
                code=_default_loc3(instance),
                is_default=True,
            )


@receiver(post_save, sender=CustomUser)
def save_related_profiles(sender, instance: CustomUser, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()
    if instance.is_seller and hasattr(instance, "sellerprofile"):
        instance.sellerprofile.save()


# ---- Audit + cart merge on login/fail ---------------------------------------

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    try:
        AccountEvent.objects.create(
            user=user,
            event=AccountEvent.LOGIN_SUCCESS,
            ip=client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
            created_at=timezone.now(),
        )
    except Exception:
        # nu blocăm login-ul dacă logging-ul eșuează
        pass

    # Merge guest session cart în coșul userului (dacă utilitarul există)
    try:
        from cart.utils import merge_session_cart_to_user
        pre_key = request.session.pop("pre_login_session_key", None)
        merge_session_cart_to_user(user, request.session, pre_key)
    except Exception:
        pass

    # Merge "favorites" din sesiune în DB (și golește sesiunea)
    try:
        from catalog.models import Favorite, Product
        raw = request.session.get("favorites") or []
        # normalizează la listă de int
        pks = []
        for x in raw:
            try:
                pks.append(int(x))
            except Exception:
                pass

        if pks:
            exist = set(
                Favorite.objects.filter(user=user, product_id__in=pks)
                .values_list("product_id", flat=True)
            )
            to_add = set(pks) - exist
            if to_add:
                valid_ids = set(
                    Product.objects.filter(pk__in=to_add, is_active=True)
                    .values_list("pk", flat=True)
                )
                Favorite.objects.bulk_create(
                    [Favorite(user=user, product_id=pid) for pid in valid_ids],
                    ignore_conflicts=True,
                )
            # goliți favoritele din sesiune (am migrat în cont)
            request.session.pop("favorites", None)
    except Exception:
        # nu stricăm login-ul dacă ceva e în neregulă
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
            created_at=timezone.now(),
        )
    except Exception:
        pass
