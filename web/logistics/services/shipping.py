# logistics/services/shipping.py
from decimal import Decimal
from typing import Tuple

from logistics.models import Courier, ShippingRate

DEFAULT_ITEM_WEIGHT_G = 500  # fallback dacă produsul nu are weight_g


def _get_total_weight_kg(cart) -> Decimal:
    """
    Calculează greutatea totală a coșului în kg, pe baza Product.weight_g.
    """
    total_grams = 0
    items = cart.items.select_related("product")

    for item in items:
        weight_g = item.product.weight_g or DEFAULT_ITEM_WEIGHT_G
        total_grams += weight_g * item.quantity

    if total_grams <= 0:
        return Decimal("0.50")  # minim 0.5 kg

    return (Decimal(total_grams) / Decimal("1000")).quantize(Decimal("0.01"))


def calculate_shipping_for_cart(cart) -> Tuple[Decimal, int, int]:
    """
    Returnează (shipping_cost, days_min, days_max) pentru conținutul coșului.

    MVP:
      - caută Curiera după slug='curiera'
      - ia cel mai potrivit ShippingRate după greutate
      - altfel cazi pe primul rate activ (cel mai ieftin)
    """
    weight_kg = _get_total_weight_kg(cart)

    try:
        curiera = Courier.objects.get(slug="curiera")
        rates_qs = ShippingRate.objects.filter(courier=curiera, is_active=True)
    except Courier.DoesNotExist:
        rates_qs = ShippingRate.objects.filter(is_active=True)

    if not rates_qs.exists():
        return Decimal("0.00"), 0, 0

    # încercăm să găsim un tarif care acoperă greutatea
    rate = (
        rates_qs.filter(min_weight_kg__lte=weight_kg, max_weight_kg__gte=weight_kg)
        .order_by("base_price")
        .first()
        or rates_qs.order_by("base_price").first()
    )

    if not rate:
        return Decimal("0.00"), 0, 0

    shipping_cost = rate.base_price
    days_min = int(rate.delivery_days_min)
    days_max = int(rate.delivery_days_max)

    return shipping_cost, days_min, days_max
