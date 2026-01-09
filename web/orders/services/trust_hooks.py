# orders/services/trust_hooks.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile, SellerProfile
from accounts.services.score import DEFAULT_BUYER_WEIGHTS, DEFAULT_SELLER_WEIGHTS, register_seller_sale
from accounts.services.trust_engine import record_event
from .models import Order


def _iter_sellers_for_order(order: Order) -> Iterable[int]:
    """
    Returnează user_id-urile sellerilor implicați în comandă (distinct).
    """
    return (
        order.items.select_related("product__owner")
        .values_list("product__owner_id", flat=True)
        .distinct()
    )


def _paid_at_for_order(order: Order):
    """
    Preferăm un paid_at derivat din Payment SUCCEEDED (dacă există),
    altfel cădem pe created_at.
    """
    try:
        p = order.payments.filter(status="succeeded").order_by("created_at").first()
        if p:
            return p.created_at
    except Exception:
        pass
    return order.created_at


@transaction.atomic
def on_order_paid(order_id: int) -> None:
    """
    Trigger la Order.mark_as_paid()
    - buyer: +2
    - fiecare seller: +1
    - register seller sale (tier+commission progression) per seller (net din linii)
    """
    order = (
        Order.objects.select_for_update()
        .prefetch_related("items__product")
        .select_related("buyer")
        .get(pk=order_id)
    )

    buyer = order.buyer
    buyer_profile = getattr(buyer, "profile", None)

    # Buyer +2 (idempotent by source_event_id)
    if buyer_profile:
        record_event(
            buyer,
            kind="ORDER_PAID",
            source_app="orders",
            source_event_id=f"order:{order.id}:paid",
            meta={"order_id": str(order.id)},
            delta_buyer=int(DEFAULT_BUYER_WEIGHTS.order_paid),
            delta_seller=0,
            apply_bonus_sync=True,
        )

    # Seller events + tier progression
    # Calculăm net per seller = suma liniilor sellerului (gross), comisionul real îl poți calcula separat;
    # pentru progresie tier (lifetime_sales_net) e OK să folosești gross sau net; aici folosesc gross ca "net sales"
    # (tu ai denumit lifetime_sales_net, dar nu ai definit încă clar dacă e net după comision).
    per_seller_total = {}
    for it in order.items.all():
        owner_id = getattr(it.product, "owner_id", None)
        if not owner_id:
            continue
        per_seller_total.setdefault(owner_id, Decimal("0.00"))
        per_seller_total[owner_id] += (it.price * it.quantity)

    for seller_id, amount in per_seller_total.items():
        # +1 seller trust
        record_event(
            target_user_id=seller_id,  # trust_engine ar trebui să suporte și user_id; dacă nu, folosește user obj
            kind="ORDER_PAID",
            source_app="orders",
            source_event_id=f"order:{order.id}:paid:seller:{seller_id}",
            meta={"order_id": str(order.id), "seller_id": str(seller_id), "gross": str(amount)},
            delta_buyer=0,
            delta_seller=int(DEFAULT_SELLER_WEIGHTS.order_paid),
            apply_bonus_sync=True,
        )

        # Tier progression (atomic in register_seller_sale)
        try:
            seller_prof = SellerProfile.objects.get(user_id=seller_id)
            register_seller_sale(seller_prof, amount, commit=True)
        except Exception:
            pass


@transaction.atomic
def on_escrow_released(order_id: int) -> None:
    """
    Trigger când escrow devine RELEASED.
    - buyer: +1 (completed)
    - seller: +1 (completed ok)
    """
    order = Order.objects.select_for_update().select_related("buyer").get(pk=order_id)
    buyer = order.buyer

    # Buyer +1
    if getattr(buyer, "profile", None):
        record_event(
            buyer,
            kind="ESCROW_RELEASED",
            source_app="orders",
            source_event_id=f"order:{order.id}:escrow:released:buyer",
            meta={"order_id": str(order.id)},
            delta_buyer=int(DEFAULT_BUYER_WEIGHTS.order_completed),
            delta_seller=0,
            apply_bonus_sync=True,
        )

    # Sellers +1
    for seller_id in _iter_sellers_for_order(order):
        record_event(
            target_user_id=seller_id,
            kind="ESCROW_RELEASED",
            source_app="orders",
            source_event_id=f"order:{order.id}:escrow:released:seller:{seller_id}",
            meta={"order_id": str(order.id), "seller_id": str(seller_id)},
            delta_buyer=0,
            delta_seller=int(DEFAULT_SELLER_WEIGHTS.order_completed_ok),
            apply_bonus_sync=True,
        )


@transaction.atomic
def on_order_shipped(order_id: int, *, shipped_at=None) -> None:
    """
    Trigger când seller marchează 'Predat curierului' (nu la AWB generated).
    Score:
      - on time: +2
      - late: -3
    On-time logic:
      shipped_at - paid_at <= SNOBISTIC_SELLER_HANDLING_DAYS_MAX (default 2 zile)
    """
    order = (
        Order.objects.select_for_update()
        .select_related("buyer")
        .prefetch_related("items__product")
        .get(pk=order_id)
    )

    shipped_at = shipped_at or timezone.now()
    paid_at = _paid_at_for_order(order)

    max_days = int(getattr(settings, "SNOBISTIC_SELLER_HANDLING_DAYS_MAX", 2))
    deadline = paid_at + timedelta(days=max_days)

    on_time = shipped_at <= deadline
    delta = int(DEFAULT_SELLER_WEIGHTS.order_shipped_on_time if on_time else DEFAULT_SELLER_WEIGHTS.late_shipment)

    # eveniment per seller (idempotent)
    for seller_id in _iter_sellers_for_order(order):
        record_event(
            target_user_id=seller_id,
            kind="ORDER_SHIPPED",
            source_app="logistics",
            source_event_id=f"order:{order.id}:shipped:seller:{seller_id}",
            meta={
                "order_id": str(order.id),
                "seller_id": str(seller_id),
                "shipped_at": shipped_at.isoformat(),
                "paid_at": paid_at.isoformat() if paid_at else None,
                "handling_days_max": max_days,
                "on_time": bool(on_time),
            },
            delta_buyer=0,
            delta_seller=delta,
            apply_bonus_sync=True,
        )
