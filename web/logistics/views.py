# logistics/views.py
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order
from .forms import ShipmentCreateForm
from .models import Shipment, Courier
from .services.curiera import create_shipment_for_order
from .services.status import mark_handed_to_courier


def _is_seller(user) -> bool:
    prof = getattr(user, "profile", None)
    return bool(prof and getattr(prof, "role_seller", False))


def _can_generate_awb(order: Order) -> bool:
    return (
        order.payment_status == Order.PAYMENT_PAID
        and order.escrow_status == Order.ESCROW_HELD
    )


@login_required
def generate_awb_view(request, order_id):
    user = request.user
    order = get_object_or_404(Order, pk=order_id)

    if not _is_seller(user) or not order.items.filter(product__owner=user).exists():
        messages.error(request, "Nu ai permisiunea să generezi AWB pentru această comandă.")
        return redirect("orders:order_detail", pk=order.pk)

    if not _can_generate_awb(order):
        messages.error(
            request,
            "Poți genera AWB doar pentru comenzi plătite, cu fondurile blocate în escrow Snobistic."
        )
        return redirect("orders:order_detail", pk=order.pk)

    courier, _ = Courier.objects.get_or_create(
        slug="curiera",
        defaults={
            "name": "Curiera",
            "tracking_url_template": "https://app.curiera.ro/track/{tracking_number}",
        },
    )

    try:
        shipment = order.shipment
    except Shipment.DoesNotExist:
        shipment = None

    if request.method == "POST":
        form = ShipmentCreateForm(request.POST, request.FILES, instance=shipment)
        if form.is_valid():
            cleaned = form.cleaned_data

            if cleaned.get("cash_on_delivery"):
                messages.error(
                    request,
                    "Pe Snobistic toate plățile se fac prin escrow. Rambursul la curier nu este permis."
                )
                return render(
                    request,
                    "logistics/generate_awb.html",
                    {"order": order, "form": form, "shipment": shipment},
                )

            if shipment is None:
                weight_kg = cleaned.get("weight_kg") or Decimal("1.00")
                service_name = cleaned.get("service_name") or "Standard"

                result = create_shipment_for_order(
                    order=order,
                    seller=user,
                    weight_kg=weight_kg,
                    service_name=service_name,
                    cash_on_delivery=False,
                    cod_amount=Decimal("0.00"),
                )

                if not result.success:
                    messages.error(
                        request,
                        f"Eroare la generarea AWB prin Curiera: {result.error_message}",
                    )
                    return render(
                        request,
                        "logistics/generate_awb.html",
                        {"order": order, "form": form, "shipment": shipment},
                    )

                shipment = form.save(commit=False)
                shipment.order = order
                shipment.seller = user
                shipment.courier = courier
                shipment.provider = Shipment.Provider.CURIERA
                shipment.tracking_number = result.tracking_number or ""
                shipment.external_id = result.external_id or ""
                shipment.tracking_url = result.tracking_url or ""
                shipment.label_url = result.label_url or ""
                shipment.status = Shipment.Status.LABEL_GENERATED
                shipment.cash_on_delivery = False
                shipment.cod_amount = Decimal("0.00")
                shipment.save()
            else:
                instance = form.save(commit=False)
                instance.cash_on_delivery = False
                instance.cod_amount = Decimal("0.00")
                instance.save()
                shipment = instance

            # IMPORTANT: NU setăm Order.SHIPPED aici.
            messages.success(request, "AWB generat și salvat pentru această comandă.")
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = ShipmentCreateForm(instance=shipment)

    return render(
        request,
        "logistics/generate_awb.html",
        {"order": order, "form": form, "shipment": shipment},
    )


@login_required
def hand_to_courier_view(request, order_id: int):
    """
    Seller marchează expediția ca 'Predat curierului'.
    Asta setează:
      - Shipment.status = HANDED_TO_COURIER + shipped_at
      - Order.shipping_status = SHIPPED
      - trust hooks seller (+2 on-time / -3 late) (idempotent)
    """
    user = request.user
    order = get_object_or_404(Order, pk=order_id)

    if not _is_seller(user) or not order.items.filter(product__owner=user).exists():
        messages.error(request, "Nu ai permisiunea să marchezi această comandă ca trimisă.")
        return redirect("orders:order_detail", pk=order.pk)

    ok = mark_handed_to_courier(order_id=order.id, seller_id=user.id)
    if not ok:
        messages.error(request, "Nu există un Shipment pentru această comandă (generează AWB întâi).")
        return redirect("orders:order_detail", pk=order.pk)

    messages.success(request, "Comanda a fost marcată ca predată curierului.")
    return redirect("orders:order_detail", pk=order.pk)
