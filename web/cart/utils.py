# cart/utils.py
from importlib import import_module
from typing import Optional

from django.conf import settings
from django.db import transaction

from catalog.models import Product
from .models import Cart, CartItem

SESSION_CART_KEY = "cart_items"  # legacy simple-session store (still supported)


# ---------- helpers ----------

def _has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())


def _ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _normalize_product_ids(raw: dict) -> list[int]:
    """
    Legacy session dict: {product_id: qty}
    qty=1 policy => ignorăm qty, păstrăm doar product_id valid.
    """
    out: list[int] = []
    for k in (raw or {}).keys():
        try:
            pid = int(k)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            out.append(pid)
    # unique, stable
    seen = set()
    uniq = []
    for pid in out:
        if pid in seen:
            continue
        seen.add(pid)
        uniq.append(pid)
    return uniq


def _load_session_store(session_key: str):
    engine = import_module(settings.SESSION_ENGINE)
    Store = engine.SessionStore
    return Store(session_key=session_key)


# ---------- public API used by views ----------

def get_cart(request) -> Optional[Cart]:
    """
    Return the current cart without creating a new one.
    - Authenticated: user's cart
    - Anonymous: cart by session_key
    """
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first()

    sk = request.session.session_key
    if not sk:
        return None

    if _has_field(Cart, "session_key"):
        return Cart.objects.filter(session_key=sk, user__isnull=True).first()

    return None


def get_or_create_cart(request) -> Cart:
    """
    Return a cart, creating one if needed.
    - Authenticated: Cart(user=request.user)
    - Anonymous: Cart(session_key=<session>)
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    sk = _ensure_session_key(request)

    if _has_field(Cart, "session_key"):
        cart, _ = Cart.objects.get_or_create(session_key=sk, defaults={"user": None})
        return cart

    # Fallback (should not be hit since your Cart DOES have session_key)
    cart, _ = Cart.objects.get_or_create(user=None)
    return cart


# ---------- merge logic called from accounts.signals on login ----------

def merge_session_cart_to_user(user, request_session, pre_login_session_key: str | None = None):
    """
    qty=1 policy:
    - dacă produsul există deja în coșul userului: nu faci nimic
    - dacă nu există: îl adaugi o singură dată
    """
    cart, _ = Cart.objects.get_or_create(user=user)

    # 1) Merge DB-based anonymous carts (Cart.session_key)
    if _has_field(Cart, "session_key"):
        for sk in filter(None, [pre_login_session_key, request_session.session_key]):
            try:
                qs = Cart.objects.filter(user__isnull=True, session_key=sk)
            except Exception:
                qs = Cart.objects.none()

            anon = qs.first()
            if not anon or anon.pk == cart.pk:
                continue

            with transaction.atomic():
                for item in CartItem.objects.select_for_update().filter(cart=anon).select_related("product"):
                    CartItem.objects.get_or_create(
                        cart=cart,
                        product=item.product,
                    )
                anon.delete()

    # 2) Merge legacy simple-session dict cart (if any)
    legacy_pids = _normalize_product_ids(request_session.get(SESSION_CART_KEY) or {})
    if legacy_pids:
        products = Product.objects.filter(id__in=legacy_pids, is_active=True).in_bulk(field_name="id")
        with transaction.atomic():
            for pid in legacy_pids:
                product = products.get(pid)
                if not product:
                    continue
                CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                )
        request_session.pop(SESSION_CART_KEY, None)
