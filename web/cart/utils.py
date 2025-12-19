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


def _normalize_items(raw: dict) -> dict[int, int]:
    """Ensure keys are ints and quantities are sane (>=1). Aggregates duplicates."""
    out: dict[int, int] = {}
    for k, v in (raw or {}).items():
        try:
            pid = int(k)
            qty = int(v)
        except (TypeError, ValueError):
            continue
        if qty < 1:
            continue
        out[pid] = out.get(pid, 0) + qty
    return out


def _load_session_store(session_key: str):
    engine = import_module(settings.SESSION_ENGINE)
    Store = engine.SessionStore
    return Store(session_key=session_key)


# ---------- public API used by views ----------

def get_cart(request) -> Optional[Cart]:
    """
    Return the current cart without creating a new one.
    - Authenticated: user's cart
    - Anonymous: cart by session_key (if your Cart has that field)
    """
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first()

    sk = request.session.session_key
    if not sk:
        return None

    # Prefer Cart.session_key if it exists
    if _has_field(Cart, "session_key"):
        return Cart.objects.filter(session_key=sk, user__isnull=True).first()

    # No session_key field on Cart -> no DB cart for guests
    return None


def get_or_create_cart(request) -> Cart:
    """
    Return a cart, creating one if needed.
    - Authenticated: Cart(user=request.user)
    - Anonymous: Cart(session_key=<session>) if model supports it; otherwise
      falls back to creating a single anonymous Cart (user=None).
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    sk = _ensure_session_key(request)

    if _has_field(Cart, "session_key"):
        cart, _ = Cart.objects.get_or_create(session_key=sk, defaults={"user": None})
        return cart

    # Fallback (no session_key on Cart). This avoids crashes, but will
    # not isolate carts per visitor. Consider adding a session_key field.
    cart, _ = Cart.objects.get_or_create(user=None)
    return cart


# ---------- merge logic called from accounts.signals on login ----------

def merge_session_cart_to_user(user, request_session, pre_login_session_key: str | None = None):
    """
    Merge any guest carts into the user's DB cart.
    - If Cart has a `session_key` field, merge carts from BOTH the previous
      session (pre_login_session_key) and the current one.
    - Also supports legacy simple-session dict under SESSION_CART_KEY.
    """
    cart, _ = Cart.objects.get_or_create(user=user)

    # 1) Merge DB-based anonymous carts (if Cart.session_key exists)
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
                # move/merge items
                for item in CartItem.objects.select_for_update().filter(cart=anon):
                    existing, created = CartItem.objects.get_or_create(
                        cart=cart,
                        product=item.product,
                        defaults={"quantity": item.quantity},
                    )
                    if not created:
                        existing.quantity += item.quantity
                        existing.save(update_fields=["quantity"])
                # remove the anonymous cart
                anon.delete()

    # 2) Merge legacy simple-session dict cart (if any)
    legacy = _normalize_items(request_session.get(SESSION_CART_KEY) or {})
    if legacy:
        products = Product.objects.filter(id__in=legacy.keys(), is_active=True).in_bulk(field_name="id")
        with transaction.atomic():
            for pid, qty in legacy.items():
                product = products.get(pid)
                if not product:
                    continue
                ci, created = CartItem.objects.select_for_update().get_or_create(
                    cart=cart,
                    product=product,
                    defaults={"quantity": qty},
                )
                if not created:
                    ci.quantity += qty
                    ci.save(update_fields=["quantity"])
        request_session.pop(SESSION_CART_KEY, None)
