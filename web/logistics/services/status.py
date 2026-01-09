# logistics/services/status.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from logistics.models import Shipment
from orders.models import Order


@transaction.atomic
def mark_handed_to_courier(order_id: int, seller_id: int) -> bool:
    """
    Atomic:
    - locks Order + Shipment
    - setează Shipment.status=HANDED_TO_COURIER + shipped_at
    - setează Order.shipping_status=SHIPPED
    - trigger trust hooks (idempotent)
    """
    order = Order.objects.select_for_update().get(pk=order_id)

    try:
        shipment = Shipment.objects.select_for_update().get(order_id=order_id)
    except Shipment.DoesNotExist:
        return False

    # security: shipment trebuie să aparțină sellerului (sau seller să fie implicat)
    if shipment.seller_id != seller_id:
        # dacă ai comenzi multi-seller și shipment e "principal", poți relaxa asta,
        # dar în MVP e corect să fie strict.
        return False

    # Idempotency: dacă deja e HANDED/IN_TRANSIT/DELIVERED, nu mai repetăm.
    if shipment.status in (
        Shipment.Status.HANDED_TO_COURIER,
        Shipment.Status.IN_TRANSIT,
        Shipment.Status.DELIVERED,
        Shipment.Status.RETURNED,
    ):
        return True

    shipment.status = Shipment.Status.HANDED_TO_COURIER
    shipment.shipped_at = shipment.shipped_at or timezone.now()
    shipment.save(update_fields=["status", "shipped_at"])

    # setăm Order.SHIPPED (idempotent)
    if order.shipping_status != Order.SHIPPING_SHIPPED:
        order.shipping_status = Order.SHIPPING_SHIPPED
        order.save(update_fields=["shipping_status"])

    # Trust hook
    try:
        from orders.services.trust_hooks import on_order_shipped
        on_order_shipped(order.id, shipped_at=shipment.shipped_at)
    except Exception:
        pass

    return True
