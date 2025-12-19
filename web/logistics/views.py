# logistics/views.py
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order
from .forms import ShipmentCreateForm
from .models import Shipment, Courier
from .services.curiera import create_shipment_for_order


def _is_seller(user) -> bool:
    """
    Aceeași logică ca în orders._is_seller:
    presupunem că user.profile.role_seller există.
    """
    prof = getattr(user, "profile", None)
    return bool(prof and getattr(prof, "role_seller", False))


def _can_generate_awb(order: Order) -> bool:
    """
    Pe Snobistic, AWB se generează DOAR dacă:
      - comanda este plătită
      - fondurile sunt în escrow (ESCROW_HELD)

    Nu permitem AWB pentru:
      - comenzi neplătite
      - comenzi fără escrow (pending/released/disputed)
    """
    return (
        order.payment_status == Order.PAYMENT_PAID
        and order.escrow_status == Order.ESCROW_HELD
    )


@login_required
def generate_awb_view(request, order_id):
    """
    Seller generează AWB prin Curiera pentru o comandă:
      - verificăm că userul este seller
      - verificăm că are produse în comanda respectivă
      - verificăm că ORDER este plătită + escrow HELD (nu acceptăm ramburs)
      - dacă nu există Shipment -> îl creăm prin API Curiera
      - dacă există Shipment -> îi permitem doar să vadă/resalveze pozele (nu regenerezi AWB)
    """
    user = request.user
    order = get_object_or_404(Order, pk=order_id)

    # verificăm că este seller și că în comanda asta are produse
    if not _is_seller(user) or not order.items.filter(product__owner=user).exists():
        messages.error(request, "Nu ai permisiunea să generezi AWB pentru această comandă.")
        return redirect("orders:order_detail", pk=order.pk)

    # 🔒 ESCROW GATE:
    # Nu generăm AWB decât dacă banii sunt deja plătiți și ținuți în escrow Snobistic.
    if not _can_generate_awb(order):
        messages.error(
            request,
            "Poți genera AWB doar pentru comenzi plătite, cu fondurile blocate în escrow Snobistic."
        )
        return redirect("orders:order_detail", pk=order.pk)

    # curierul principal: Curiera
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

            # 🔒 NO COD (Ramburs) – TOTUL prin escrow:
            if cleaned.get("cash_on_delivery"):
                messages.error(
                    request,
                    "Pe Snobistic toate plățile se fac prin escrow. Rambursul la curier nu este permis."
                )
                # nu trimitem nimic la Curiera dacă cineva încearcă COD
                return render(
                    request,
                    "logistics/generate_awb.html",
                    {
                        "order": order,
                        "form": form,
                        "shipment": shipment,
                    },
                )

            if shipment is None:
                weight_kg = cleaned.get("weight_kg") or Decimal("1.00")
                service_name = cleaned.get("service_name") or "Standard"

                # forțăm COD OFF în integrarea Curiera
                cod = False
                cod_amount = Decimal("0.00")

                result = create_shipment_for_order(
                    order=order,
                    seller=user,
                    weight_kg=weight_kg,
                    service_name=service_name,
                    cash_on_delivery=cod,
                    cod_amount=cod_amount,
                )

                if not result.success:
                    messages.error(
                        request,
                        f"Eroare la generarea AWB prin Curiera: {result.error_message}",
                    )
                    return render(
                        request,
                        "logistics/generate_awb.html",
                        {
                            "order": order,
                            "form": form,
                            "shipment": shipment,
                        },
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
                # asigurare suplimentară că nu rămâne COD în model
                shipment.cash_on_delivery = False
                shipment.cod_amount = Decimal("0.00")
                shipment.save()
            else:
                # dacă shipment există deja, doar actualizăm pozele/opțiunile locale,
                # dar NU modificăm AWB-ul și NU activăm COD.
                instance = form.save(commit=False)
                instance.cash_on_delivery = False
                instance.cod_amount = Decimal("0.00")
                instance.save()
                shipment = instance

            # marcăm comanda ca trimisă (MVP – când AWB e generat)
            try:
                order.shipping_status = Order.SHIPPING_SHIPPED
                order.save(update_fields=["shipping_status"])
            except Exception:
                pass

            messages.success(request, "AWB generat și salvat pentru această comandă.")
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = ShipmentCreateForm(instance=shipment)

    return render(
        request,
        "logistics/generate_awb.html",
        {
            "order": order,
            "form": form,
            "shipment": shipment,
        },
    )
