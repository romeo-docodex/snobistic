# payments/views.py
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from .forms import TopUpForm, WithdrawForm
from .models import Wallet, WalletTransaction, Payment

# ==========================
# Stripe config
# ==========================

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


def is_seller(user):
    """
    Regula pentru cine are acces la wallet (vânzători).

    Folosește aceeași logică ca în dashboard:
    - Profile.role_seller = True
    - sau există SellerProfile
    - fallback: user.is_seller
    """
    if not user.is_authenticated:
        return False

    prof = getattr(user, "profile", None)
    if prof is not None and getattr(prof, "role_seller", False):
        return True

    if hasattr(user, "sellerprofile"):
        return True

    return getattr(user, "is_seller", False)


# ==========================
# WALLET – topup / withdraw
# ==========================


@login_required
@user_passes_test(is_seller)
def wallet_topup(request):
    """
    Încărcare wallet prin Stripe Checkout.
    - NU mai modificăm direct soldul aici
    - soldul este actualizat în webhook Stripe când plata este SUCCEEDED
    """
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = TopUpForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            method = form.cleaned_data["method"]

            # momentan doar card (Stripe)
            if method != "card":
                messages.error(
                    request,
                    "Momentan poți încărca wallet-ul doar cu cardul (prin Stripe).",
                )
                return redirect("payments:wallet_topup")

            if not stripe.api_key:
                messages.error(
                    request,
                    "Plata online nu este disponibilă momentan. Te rugăm să încerci mai târziu.",
                )
                return redirect("dashboard:wallet")

            currency_code = getattr(settings, "SNOBISTIC_CURRENCY", "RON")
            stripe_currency = currency_code.lower()

            try:
                session = stripe.checkout.Session.create(
                    mode="payment",
                    customer_email=request.user.email,
                    line_items=[
                        {
                            "price_data": {
                                "currency": stripe_currency,
                                "product_data": {
                                    "name": "Încărcare Wallet Snobistic",
                                },
                                "unit_amount": int(
                                    (amount * Decimal("100")).quantize(Decimal("1"))
                                ),
                            },
                            "quantity": 1,
                        }
                    ],
                    metadata={
                        "purpose": "wallet_topup",
                        "user_id": str(request.user.id),
                        "amount": str(amount),
                        "currency": stripe_currency,
                    },
                    automatic_payment_methods={"enabled": True},
                    success_url=(
                        request.build_absolute_uri(
                            reverse("payments:wallet_topup_success")
                        )
                        + "?session_id={CHECKOUT_SESSION_ID}"
                    ),
                    cancel_url=request.build_absolute_uri(
                        reverse("payments:wallet_topup_cancel")
                    ),
                )
            except Exception as e:
                messages.error(
                    request,
                    f"A apărut o eroare la inițierea plății: {e}",
                )
                return redirect("dashboard:wallet")

            return redirect(session.url, code=303)
    else:
        form = TopUpForm()

    return render(
        request,
        "payments/wallet_topup.html",
        {
            "form": form,
            "wallet": wallet,
        },
    )


@login_required
@user_passes_test(is_seller)
def wallet_topup_success(request):
    """
    Pagina de întoarcere după succes Stripe pentru încărcare wallet.
    Soldul efectiv se actualizează în webhook.
    """
    messages.success(
        request,
        "Plata a fost procesată. Suma va apărea în wallet imediat ce primim confirmarea de la procesatorul de plăți.",
    )
    return redirect("dashboard:wallet")


@login_required
@user_passes_test(is_seller)
def wallet_topup_cancel(request):
    """
    Pagina de întoarcere după cancel Stripe pentru încărcare wallet.
    """
    messages.info(
        request,
        "Încărcarea wallet-ului a fost anulată. Nu s-a realizat nicio tranzacție.",
    )
    return redirect("dashboard:wallet")


@login_required
@user_passes_test(is_seller)
def wallet_withdraw(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = WithdrawForm(request.POST, user=request.user)
        if form.is_valid():
            amt = form.cleaned_data["amount"]
            iban = form.cleaned_data["iban"]  # momentan doar îl validăm/extragem

            wallet.balance -= amt
            wallet.save(update_fields=["balance"])

            WalletTransaction.objects.create(
                user=request.user,
                transaction_type=WalletTransaction.WITHDRAW,
                amount=amt,  # pozitiv, direcția e dată de transaction_type
                method="bank",
                balance_after=wallet.balance,
            )

            messages.success(
                request,
                f"Retragere de {amt} RON inițiată către IBAN {iban}.",
            )
            return redirect("dashboard:wallet")
    else:
        form = WithdrawForm(user=request.user)

    return render(
        request,
        "payments/wallet_withdraw.html",
        {
            "form": form,
            "wallet": wallet,
        },
    )


# ==========================
# STRIPE CHECKOUT – card, Apple Pay, Google Pay
# ==========================


@login_required
def payment_confirm(request, order_id):
    """
    View-ul principal care pornește plata Stripe pentru un Order.
    - Creează un Payment în DB
    - Creează un Stripe Checkout Session
    - Redirect 303 către Stripe
    """
    order = get_object_or_404(Order, id=order_id, buyer=request.user)

    # Dacă e deja plătită, trimitem userul direct la succes
    if order.payment_status == Order.PAYMENT_PAID:
        messages.info(request, f"Comanda #{order.id} este deja plătită.")
        return redirect("cart:checkout_success", order_id=order.id)

    if not stripe.api_key:
        messages.error(
            request,
            "Plata online nu este disponibilă momentan (config Stripe lipsă).",
        )
        return redirect("cart:checkout_cancel")

    # Stripe vrea lowercase, noi salvăm uppercase în DB
    currency_code = getattr(settings, "SNOBISTIC_CURRENCY", "RON")
    stripe_currency = currency_code.lower()

    # 1) Creăm Payment în DB
    payment = Payment.objects.create(
        order=order,
        user=request.user,
        provider=Payment.Provider.STRIPE,
        amount=order.total,
        currency=currency_code.upper(),
        status=Payment.Status.PENDING,
    )

    # 2) Construim Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=request.user.email,
            line_items=[
                {
                    "price_data": {
                        "currency": stripe_currency,
                        "product_data": {
                            "name": f"Comanda #{order.id} – Snobistic",
                            "metadata": {
                                "order_id": str(order.id),
                            },
                        },
                        "unit_amount": payment.amount_minor_units,
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "order_id": order.id,
                "payment_id": payment.id,
                "user_id": request.user.id,
            },
            # Stripe se ocupă de card + Apple Pay + Google Pay (dacă sunt activate în Dashboard)
            automatic_payment_methods={
                "enabled": True,
            },
            success_url=(
                request.build_absolute_uri(
                    reverse("payments:payment_success", args=[order.id])
                )
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=request.build_absolute_uri(
                reverse("payments:payment_failure", args=[order.id])
            ),
        )
    except Exception as e:
        messages.error(
            request,
            f"A apărut o eroare la inițierea plății: {e}",
        )
        return redirect("cart:checkout_cancel")

    # 3) Actualizăm Payment cu datele Stripe
    payment.stripe_session_id = session.id
    payment.raw_response = session
    payment.save(update_fields=["stripe_session_id", "raw_response"])

    # 4) Redirect la Stripe
    return redirect(session.url, code=303)


@login_required
def payment_success(request, order_id):
    """
    Pagina la care Stripe trimite user-ul după checkout reușit
    SAU după plată cu wallet (redirecționăm manual).
    ATENȚIE: pentru Stripe ne bazăm pe webhook să marcheze plata ca SUCCEEDED.
    """
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    payment = order.payments.order_by("-created_at").first()

    # Dacă webhook-ul a venit deja și a marcat ca plătit, ok.
    if order.payment_status == Order.PAYMENT_PAID:
        paid = True
    else:
        paid = False

    return render(
        request,
        "payments/payment_success.html",
        {"order": order, "payment": payment, "paid": paid},
    )


@login_required
def payment_failure(request, order_id):
    """
    Pagina la care Stripe trimite user-ul după cancel sau eroare.
    """
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    payment = order.payments.order_by("-created_at").first()

    messages.error(
        request,
        "Plata nu a fost procesată. Poți încerca din nou sau alege altă metodă.",
    )
    return render(
        request,
        "payments/payment_failure.html",
        {"order": order, "payment": payment},
    )


# ==========================
# STRIPE WEBHOOK
# ==========================


@csrf_exempt
def stripe_webhook(request):
    """
    Webhook oficial Stripe.
    - verificăm semnătura
    - pentru `checkout.session.completed`:
        * dacă este sesiune legată de un Payment → marcăm Payment + Order ca plătite
        * dacă este sesiune de wallet_topup → alimentăm wallet-ul
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    if not endpoint_secret:
        # Dacă nu e setat, mai bine nu acceptăm nimic
        return HttpResponseBadRequest("Stripe webhook secret missing")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret,
        )
    except ValueError:
        # payload invalid
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        # semnătură invalidă
        return HttpResponseBadRequest("Invalid signature")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        session_id = data.get("id")
        payment_intent_id = data.get("payment_intent")
        metadata = data.get("metadata", {}) or {}

        # 1) Încercăm să găsim un Payment legat de un Order
        payment = (
            Payment.objects.select_related("order")
            .filter(stripe_session_id=session_id)
            .first()
        )

        if payment:
            # Idempotency: dacă deja e SUCCEEDED, nu mai facem nimic
            if payment.status == Payment.Status.SUCCEEDED:
                return HttpResponse(status=200)

            # actualizăm Payment
            payment.status = Payment.Status.SUCCEEDED
            if payment_intent_id:
                payment.stripe_payment_intent_id = payment_intent_id
            payment.raw_response = data
            payment.save(
                update_fields=[
                    "status",
                    "stripe_payment_intent_id",
                    "raw_response",
                ]
            )

            # marcăm Order ca plătit + escrow HELD
            order = payment.order
            if order and order.payment_status != Order.PAYMENT_PAID:
                order.mark_as_paid()

        else:
            # 2) Dacă nu avem Payment, verificăm dacă este un top-up de wallet
            purpose = metadata.get("purpose")
            if purpose == "wallet_topup":
                from decimal import Decimal as D
                from django.contrib.auth import get_user_model

                user_id = metadata.get("user_id")
                amount_str = metadata.get("amount")
                currency = metadata.get("currency", "ron").upper()

                if not user_id or not amount_str:
                    return HttpResponse(status=200)

                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return HttpResponse(status=200)

                try:
                    amount = D(amount_str)
                except Exception:
                    return HttpResponse(status=200)

                wallet, _ = Wallet.objects.get_or_create(user=user)

                # Idempotency: dacă avem deja o tranzacție TOP_UP cu acest payment_intent, ieșim
                if payment_intent_id and WalletTransaction.objects.filter(
                    user=user,
                    transaction_type=WalletTransaction.TOP_UP,
                    external_id=payment_intent_id,
                ).exists():
                    return HttpResponse(status=200)

                wallet.balance += amount
                wallet.save(update_fields=["balance"])

                WalletTransaction.objects.create(
                    user=user,
                    transaction_type=WalletTransaction.TOP_UP,
                    amount=amount,
                    method="card",
                    balance_after=wallet.balance,
                    external_id=payment_intent_id or "",
                )

    # poți trata și alte event_type-uri mai târziu (refund, etc.)
    return HttpResponse(status=200)
