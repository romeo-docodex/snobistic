# cart/views.py
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from catalog.models import Product
from logistics.services.shipping import calculate_shipping_for_cart
from orders.models import Order, _pct
from payments.models import Wallet, Payment
from payments.services import charge_order_from_wallet

from .forms import CheckoutForm, CouponApplyForm
from .models import Cart, CartItem, Coupon
from .utils import get_or_create_cart, get_cart


def _is_ajax(request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _cart_items_count(cart: Cart | None) -> int:
    if not cart:
        return 0
    return cart.items.count()


def _compute_cart_totals(
    cart: Cart | None,
    *,
    shipping_cost: Decimal | None = None,
) -> dict:
    """
    Standard totals calculator (reused across cart/offcanvas/checkout):
    - subtotal_before_discount
    - discount_amount
    - subtotal (after coupon)
    - buyer_protection_fee
    - shipping_cost
    - total (estimated)
    """
    zero = Decimal("0.00")
    if not cart:
        return {
            "subtotal_before_discount": zero,
            "discount_amount": zero,
            "subtotal": zero,
            "buyer_protection_fee": zero,
            "shipping_cost": shipping_cost or zero,
            "total": (shipping_cost or zero),
        }

    subtotal_before_discount = cart.get_subtotal()
    subtotal = cart.get_total_price()  # after coupon (if any)
    discount_amount = cart.get_discount_amount()

    buyer_protection_percent = Decimal(getattr(settings, "SNOBISTIC_BUYER_PROTECTION_PERCENT", "5.0"))
    buyer_protection_fee = _pct(subtotal, buyer_protection_percent)

    ship = shipping_cost if shipping_cost is not None else zero
    total = subtotal + buyer_protection_fee + ship

    return {
        "subtotal_before_discount": subtotal_before_discount,
        "discount_amount": discount_amount,
        "subtotal": subtotal,
        "buyer_protection_fee": buyer_protection_fee,
        "shipping_cost": ship,
        "total": total,
    }


@require_POST
def cart_add(request, product_id):
    # buyer gating pentru seller
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile:
            is_seller = getattr(profile, "role_seller", False)
            is_buyer = getattr(profile, "role_buyer", False)
            seller_can_buy = getattr(profile, "seller_can_buy", False)

            if is_seller and not (is_buyer and seller_can_buy):
                messages.error(
                    request,
                    "Contul tău este configurat ca vânzător. Pentru a cumpăra, activează opțiunea "
                    "«Pot cumpăra ca buyer» în setările contului."
                )
                return redirect("catalog:product_list")

    # ✅ creezi cart DOAR aici (POST/add)
    cart = get_or_create_cart(request)

    # ✅ doar produse publice (marketplace)
    product_qs = Product.objects.public() if hasattr(Product.objects, "public") else Product.objects.filter(is_active=True)
    product = get_object_or_404(product_qs, pk=product_id)

    # ✅ Prevent buy your own product
    if request.user.is_authenticated and getattr(product, "owner_id", None) == request.user.id:
        messages.error(request, "Nu poți adăuga în coș propriul tău produs.")
        return redirect(request.META.get("HTTP_REFERER") or product.get_absolute_url())

    # ✅ qty=1 policy: dacă există deja, nu mai facem nimic
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
    )
    if not created:
        messages.info(request, "Produsul este deja în coș.")

    count = _cart_items_count(cart)
    totals = _compute_cart_totals(cart, shipping_cost=None)

    if _is_ajax(request):
        html = render_to_string(
            "cart/partials/cart_offcanvas.html",
            {"cart": cart, "totals": totals},
            request=request,
        )
        return JsonResponse(
            {
                "ok": True,
                "count": count,
                "item_id": item.id,
                "message": "Produs adăugat în coș." if created else "Produsul este deja în coș.",
                "cart_subtotal": str(totals["subtotal"]),
                "cart_total": str(totals["total"]),
                "html": html,
            }
        )

    return redirect(request.META.get("HTTP_REFERER") or reverse("cart:cart"))


@require_POST
def cart_remove(request, item_id: int):
    # ✅ NU creăm cart aici (altfel umpli DB cu coșuri goale)
    cart = get_cart(request)
    if not cart:
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "Cart not found."}, status=404)
        return redirect("cart:cart")

    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()

    totals = _compute_cart_totals(cart, shipping_cost=None)
    count = _cart_items_count(cart)

    if _is_ajax(request):
        html = render_to_string(
            "cart/partials/cart_offcanvas.html",
            {"cart": cart if count else None, "totals": totals},
            request=request,
        )
        return JsonResponse(
            {
                "ok": True,
                "count": count,
                "subtotal": str(totals["subtotal"]),
                "buyer_protection_fee": str(totals["buyer_protection_fee"]),
                "shipping_cost": str(totals["shipping_cost"]),
                "total": str(totals["total"]),
                "html": html,
            }
        )

    return redirect(request.META.get("HTTP_REFERER") or reverse("cart:cart"))


@require_GET
def cart_offcanvas_partial(request):
    cart = get_cart(request)
    totals = _compute_cart_totals(cart, shipping_cost=None)
    html = render_to_string(
        "cart/partials/cart_offcanvas.html",
        {"cart": cart, "totals": totals},
        request=request,
    )
    return JsonResponse({"html": html})


def cart_view(request):
    # ✅ P0: pe GET nu creăm cart (anti-bots / anti-DB spam)
    cart = get_cart(request)

    shipping_address = None
    if request.user.is_authenticated and hasattr(request.user, "addresses") and request.user.addresses.exists():
        shipping_address = request.user.addresses.first()

    related_products = Product.objects.filter(is_active=True).order_by("-created_at")[:8]

    coupon_form = CouponApplyForm()
    coupon_error = None

    shipping_cost = None
    shipping_days_min = None
    shipping_days_max = None
    if cart and cart.items.exists():
        try:
            shipping_cost, shipping_days_min, shipping_days_max = calculate_shipping_for_cart(cart)
        except Exception:
            shipping_cost, shipping_days_min, shipping_days_max = None, None, None

    totals = _compute_cart_totals(cart, shipping_cost=(shipping_cost or Decimal("0.00")))

    if request.method == "POST":
        # ✅ dacă cineva postează fără cart real, nu îl creăm aici
        if not cart or not cart.items.exists():
            messages.info(request, "Coșul tău este gol.")
            return redirect("cart:cart")

        # cupon
        if "apply_coupon" in request.POST:
            coupon_form = CouponApplyForm(request.POST)
            if coupon_form.is_valid():
                code = coupon_form.cleaned_data["code"]

                coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
                if not coupon:
                    coupon_error = "Cod promoțional invalid sau expirat."
                    messages.error(request, coupon_error)
                    return redirect("cart:cart")

                ok, msg = coupon.validate_for_cart(cart)
                if not ok:
                    coupon_error = msg or "Cod promoțional invalid."
                    messages.error(request, coupon_error)
                    return redirect("cart:cart")

                cart.coupon = coupon
                cart.save(update_fields=["coupon"])
                messages.success(request, "Cupon aplicat cu succes.")
                return redirect("cart:cart")

            return redirect("cart:cart")

        return redirect("cart:cart")

    context = {
        "cart": cart,
        "shipping_address": shipping_address,
        "related_products": related_products,
        "coupon_form": coupon_form,
        "coupon_error": coupon_error,
        "shipping_cost": shipping_cost,
        "shipping_days_min": shipping_days_min,
        "shipping_days_max": shipping_days_max,
        "totals": totals,
    }
    return render(request, "cart/cart.html", context)


@login_required
def checkout_view(request):
    # ✅ P0: nu mai există 404 pentru user fără cart
    cart = get_cart(request) or get_or_create_cart(request)

    if not cart.items.exists():
        messages.info(request, "Coșul tău este gol. Adaugă produse înainte de a finaliza comanda.")
        return redirect("cart:cart")

    addresses = request.user.addresses.all()
    if not addresses.exists():
        messages.info(request, "Adaugă o adresă de livrare înainte de a continua cu plata.")
        return redirect("accounts:address_form")

    shipping_cost, shipping_days_min, shipping_days_max = calculate_shipping_for_cart(cart)

    wallet_obj, _ = Wallet.objects.get_or_create(user=request.user)

    form = CheckoutForm(request.POST or None)
    form.fields["address"].choices = [(addr.id, str(addr)) for addr in addresses]

    totals = _compute_cart_totals(cart, shipping_cost=(shipping_cost or Decimal("0.00")))

    if request.method == "POST" and form.is_valid():
        address_id = form.cleaned_data["address"]
        shipping_method = form.cleaned_data["shipping_method"]
        payment_method = form.cleaned_data["payment_method"]

        # 0) Validate coupon again at checkout (robust)
        if cart.coupon_id:
            ok, msg = cart.coupon.validate_for_cart(cart)
            if not ok:
                messages.error(request, msg or "Cupon invalid. Te rugăm să reîncerci.")
                cart.coupon = None
                cart.save(update_fields=["coupon"])
                return redirect("cart:cart")

        # 1) Reguli minime pentru ramburs (COD)
        if payment_method == "cash_on_delivery":
            can_cod = False
            profile = getattr(request.user, "profile", None)
            if profile:
                buyer_class = getattr(profile, "buyer_trust_class", None)
                if buyer_class in ("A", "B"):
                    can_cod = True

            if not can_cod:
                messages.error(
                    request,
                    "Plata ramburs nu este disponibilă pentru contul tău. "
                    "Te rugăm să alegi o altă metodă de plată."
                )
                return render(
                    request,
                    "cart/checkout.html",
                    {
                        "form": form,
                        "cart": cart,
                        "shipping_cost": shipping_cost,
                        "shipping_days_min": shipping_days_min,
                        "shipping_days_max": shipping_days_max,
                        "wallet": wallet_obj,
                        "totals": totals,
                    },
                )

        # 2) Pre-check pentru Wallet
        if payment_method == "wallet":
            estimated_total = totals["total"]
            if wallet_obj.balance < estimated_total:
                messages.error(
                    request,
                    "Sold insuficient în Wallet Snobistic pentru a plăti această comandă. "
                    "Te rugăm să încarci wallet-ul sau să alegi o altă metodă de plată."
                )
                return render(
                    request,
                    "cart/checkout.html",
                    {
                        "form": form,
                        "cart": cart,
                        "shipping_cost": shipping_cost,
                        "shipping_days_min": shipping_days_min,
                        "shipping_days_max": shipping_days_max,
                        "wallet": wallet_obj,
                        "totals": totals,
                    },
                )

        # 3) Adresa
        address = get_object_or_404(
            request.user.addresses.model,
            pk=address_id,
            user=request.user,
        )

        # 4) Creăm Order din coș
        order = Order.create_from_cart(
            cart=cart,
            address=address,
            shipping_method=shipping_method,
            shipping_cost=shipping_cost,
            shipping_days_min=shipping_days_min,
            shipping_days_max=shipping_days_max,
        )

        # ✅ 4.1) Consume coupon usage AFTER order creation (atomic)
        if cart.coupon_id:
            try:
                cart.coupon.consume_one()
            except ValueError as e:
                try:
                    order.delete()
                except Exception:
                    pass
                cart.coupon = None
                cart.save(update_fields=["coupon"])
                messages.error(request, str(e))
                return redirect("cart:cart")

        # 5) Card
        if payment_method == "card":
            return redirect(order.get_payment_url())

        # 6) Wallet
        if payment_method == "wallet":
            try:
                charge_order_from_wallet(order, user=request.user)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("dashboard:orders_list")
            return redirect("payments:payment_success", order_id=order.id)

        # 7) Numerar / Ramburs
        if payment_method == "cash_on_delivery":
            Payment.objects.create(
                order=order,
                user=request.user,
                provider=Payment.Provider.CASH,
                amount=order.total,
                currency=getattr(settings, "SNOBISTIC_CURRENCY", "RON"),
                status=Payment.Status.PENDING,
            )
            messages.success(request, "Comanda ta a fost plasată cu succes. Vei plăti în numerar la livrare.")
            return redirect("cart:checkout_success", order_id=order.id)

        return redirect(order.get_payment_url())

    return render(
        request,
        "cart/checkout.html",
        {
            "form": form,
            "cart": cart,
            "shipping_cost": shipping_cost,
            "shipping_days_min": shipping_days_min,
            "shipping_days_max": shipping_days_max,
            "wallet": wallet_obj,
            "totals": totals,
        },
    )


@login_required
def checkout_success_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)
    return render(request, "cart/success.html", {"order": order})


@login_required
def checkout_cancel_view(request):
    return render(request, "cart/cancel.html")
