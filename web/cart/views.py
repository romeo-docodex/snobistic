# cart/views.py
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from catalog.models import Product
from orders.models import Order, _pct
from logistics.services.shipping import calculate_shipping_for_cart
from payments.models import Wallet, Payment
from payments.services import charge_order_from_wallet
from .forms import CheckoutForm, CouponApplyForm
from .models import Cart, CartItem, Coupon
from .utils import get_or_create_cart, get_cart


def cart_add(request, product_id):
    if request.method != 'POST':
        return redirect('catalog:product_list')

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
                return redirect('catalog:product_list')

    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, pk=product_id, is_active=True)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": 1},
    )
    if not created:
        pass

    total_qty = cart.items.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "count": total_qty,
            "item_id": item.id,
            "qty": item.quantity,
            "cart_total": str(cart.get_total_price()),
        })

    return redirect(request.META.get('HTTP_REFERER', 'cart:cart'))


def cart_offcanvas_partial(request):
    cart = get_cart(request)
    html = render_to_string('cart/partials/cart_offcanvas.html', {'cart': cart}, request=request)
    return JsonResponse({"html": html})


def cart_view(request):
    cart = get_or_create_cart(request)

    shipping_address = None
    if request.user.is_authenticated and request.user.addresses.exists():
        shipping_address = request.user.addresses.first()

    related_products = Product.objects.filter(is_active=True).order_by('-created_at')[:8]

    coupon_form = CouponApplyForm()
    coupon_error = None

    if request.method == 'POST':
        if 'apply_coupon' in request.POST:
            coupon_form = CouponApplyForm(request.POST)
            if coupon_form.is_valid():
                code = coupon_form.cleaned_data['code'].strip()
                try:
                    coupon = Coupon.objects.get(code__iexact=code, is_active=True)
                    cart.coupon = coupon
                    cart.save()
                    messages.success(request, "Cupon aplicat cu succes.")
                except Coupon.DoesNotExist:
                    coupon_error = "Cod promoțional invalid sau expirat."
                    messages.error(request, coupon_error)
            return redirect('cart:cart')

        action = request.POST.get('action')

        if action:
            if action == 'remove':
                try:
                    item_id = int(request.POST.get('item_id', '0'))
                    cart.items.get(id=item_id).delete()
                except Exception:
                    pass

            elif action.startswith('remove_'):
                try:
                    item_id = int(action.split('_', 1)[1])
                    cart.items.get(id=item_id).delete()
                except Exception:
                    pass

        return redirect('cart:cart')

    context = {
        'cart': cart,
        'shipping_address': shipping_address,
        'related_products': related_products,
        'coupon_form': coupon_form,
        'coupon_error': coupon_error,
    }
    return render(request, 'cart/cart.html', context)


@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, user=request.user)

    if not cart.items.exists():
        messages.info(
            request,
            "Coșul tău este gol. Adaugă produse înainte de a finaliza comanda."
        )
        return redirect("cart:cart")

    addresses = request.user.addresses.all()
    if not addresses.exists():
        messages.info(
            request,
            "Adaugă o adresă de livrare înainte de a continua cu plata."
        )
        return redirect("accounts:address_form")

    # estimare transport pentru coș
    shipping_cost, shipping_days_min, shipping_days_max = calculate_shipping_for_cart(cart)

    # wallet-ul userului (îl avem și pentru afișare în template)
    wallet_obj, _ = Wallet.objects.get_or_create(user=request.user)

    form = CheckoutForm(request.POST or None)
    form.fields["address"].choices = [(addr.id, str(addr)) for addr in addresses]

    if request.method == "POST" and form.is_valid():
        address_id = form.cleaned_data["address"]
        shipping_method = form.cleaned_data["shipping_method"]
        payment_method = form.cleaned_data["payment_method"]

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
                    },
                )

        # 2) Pre-check pentru Wallet (înainte să creăm comanda)
        if payment_method == "wallet":
            # subtotalul după cupoane:
            subtotal = cart.get_total_price()

            buyer_protection_percent = Decimal(
                getattr(settings, "SNOBISTIC_BUYER_PROTECTION_PERCENT", "5.0")
            )
            buyer_protection_fee = _pct(subtotal, buyer_protection_percent)

            estimated_total = subtotal + buyer_protection_fee + (shipping_cost or Decimal("0.00"))

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
                    },
                )

        # 3) Adresa de livrare
        address = get_object_or_404(
            request.user.addresses.model,
            pk=address_id,
            user=request.user,
        )

        # 4) Creăm Order din coș (inclusiv shipping + buyer protection în interior)
        order = Order.create_from_cart(
            cart=cart,
            address=address,
            shipping_method=shipping_method,
            shipping_cost=shipping_cost,
            shipping_days_min=shipping_days_min,
            shipping_days_max=shipping_days_max,
        )

        # 5) Card (Stripe) – redirecționăm spre payments:payment_confirm
        if payment_method == "card":
            return redirect(order.get_payment_url())

        # 6) Wallet – folosim serviciul centralizat charge_order_from_wallet
        if payment_method == "wallet":
            try:
                charge_order_from_wallet(order, user=request.user)
            except ValueError as e:
                # ex: fonduri insuficiente, sumă invalidă etc.
                messages.error(request, str(e))
                return redirect("dashboard:orders_list")

            # redirectăm către pagina standard de succes din payments
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

            messages.success(
                request,
                "Comanda ta a fost plasată cu succes. Vei plăti în numerar la livrare."
            )
            return redirect("cart:checkout_success", order_id=order.id)

        # fallback – orice altă metodă necunoscută merge ca și card
        return redirect(order.get_payment_url())

    # GET sau POST invalid → reafișăm formularul
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
        },
    )


@login_required
def checkout_success_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)
    return render(request, 'cart/success.html', {'order': order})


@login_required
def checkout_cancel_view(request):
    return render(request, 'cart/cancel.html')
