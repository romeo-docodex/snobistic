# logistics/services/status.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from logistics.models import Shipment
from orders.models import Order


@transaction.atomic
def mark_handed_to_courier(order_id: int, seller_id: int) -> bool:
    order = Order.objects.select_for_update().get(pk=order_id)

    try:
        shipment = Shipment.objects.select_for_update().get(order_id=order_id)
    except Shipment.DoesNotExist:
        return False

    if shipment.seller_id != seller_id:
        return False

    if shipment.status in (
        Shipment.Status.HANDED_TO_COURIER,
        Shipment.Status.IN_TRANSIT,
        Shipment.Status.DELIVERED,
        Shipment.Status.RETURNED,
    ):
        # ensure order shipped at least
        order.mark_shipped(shipped_at=shipment.shipped_at or timezone.now())
        return True

    shipment.status = Shipment.Status.HANDED_TO_COURIER
    shipment.shipped_at = shipment.shipped_at or timezone.now()
    shipment.save(update_fields=["status", "shipped_at"])

    # ✅ Order transition
    order.mark_shipped(shipped_at=shipment.shipped_at)

    try:
        from orders.services.trust_hooks import on_order_shipped
        on_order_shipped(order.id, shipped_at=shipment.shipped_at)
    except Exception:
        pass

    return True


@transaction.atomic
def mark_in_transit(order_id: int) -> bool:
    order = Order.objects.select_for_update().get(pk=order_id)
    try:
        shipment = Shipment.objects.select_for_update().get(order_id=order_id)
    except Shipment.DoesNotExist:
        return False

    if shipment.status in (Shipment.Status.DELIVERED, Shipment.Status.RETURNED):
        return True

    shipment.status = Shipment.Status.IN_TRANSIT
    shipment.save(update_fields=["status"])

    order.mark_in_transit()
    return True


@transaction.atomic
def mark_delivered(order_id: int) -> bool:
    order = Order.objects.select_for_update().get(pk=order_id)
    try:
        shipment = Shipment.objects.select_for_update().get(order_id=order_id)
    except Shipment.DoesNotExist:
        return False

    shipment.status = Shipment.Status.DELIVERED
    shipment.delivered_at = getattr(shipment, "delivered_at", None) or timezone.now()
    shipment.save(update_fields=["status", "delivered_at"] if hasattr(shipment, "delivered_at") else ["status"])

    order.mark_delivered(delivered_at=timezone.now())
    return True


@transaction.atomic
def mark_returned(order_id: int) -> bool:
    order = Order.objects.select_for_update().get(pk=order_id)
    try:
        shipment = Shipment.objects.select_for_update().get(order_id=order_id)
    except Shipment.DoesNotExist:
        return False

    shipment.status = Shipment.Status.RETURNED
    shipment.save(update_fields=["status"])

    order.mark_returned()
    return True
