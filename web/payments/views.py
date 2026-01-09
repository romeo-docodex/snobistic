# payments/views.py
from __future__ import annotations

from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from .forms import TopUpForm, WithdrawForm
from .models import Wallet, WalletTransaction, Payment

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


def is_seller(user):
    if not user.is_authenticated:
        return False

    prof = getattr(user, "profile", None)
    if prof is not None and getattr(prof, "role_seller", False):
        return True

    if hasattr(user, "sellerprofile"):
        return True

    return getattr(user, "is_seller", False)


@login_required
@user_passes_test(is_seller)
def wallet_topup(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = TopUpForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            method = form.cleaned_data["method"]

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
    messages.success(
        request,
        "Plata a fost procesată. Suma va apărea în wallet imediat ce primim confirmarea de la procesatorul de plăți.",
    )
    return redirect("dashboard:wallet")


@login_required
@user_passes_test(is_seller)
def wallet_topup_cancel(request):
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
            iban = form.cleaned_data["iban"]

            wallet.balance -= amt
            wallet.save(update_fields=["balance"])

            WalletTransaction.objects.create(
                user=request.user,
                transaction_type=WalletTransaction.WITHDRAW,
                amount=amt,
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


@login_required
def payment_confirm(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)

    if order.payment_status == Order.PAYMENT_PAID:
        messages.info(request, f"Comanda #{order.id} este deja plătită.")
        return redirect("cart:checkout_success", order_id=order.id)

    if not stripe.api_key:
        messages.error(
            request,
            "Plata online nu este disponibilă momentan (config Stripe lipsă).",
        )
        return redirect("cart:checkout_cancel")

    currency_code = getattr(settings, "SNOBISTIC_CURRENCY", "RON")
    stripe_currency = currency_code.lower()

    payment = Payment.objects.create(
        order=order,
        user=request.user,
        provider=Payment.Provider.STRIPE,
        amount=order.total,
        currency=currency_code.upper(),
        status=Payment.Status.PENDING,
    )

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
            automatic_payment_methods={"enabled": True},
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

    payment.stripe_session_id = session.id
    payment.raw_response = session
    payment.save(update_fields=["stripe_session_id", "raw_response"])

    return redirect(session.url, code=303)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    payment = order.payments.order_by("-created_at").first()
    paid = order.payment_status == Order.PAYMENT_PAID

    return render(
        request,
        "payments/payment_success.html",
        {"order": order, "payment": payment, "paid": paid},
    )


@login_required
def payment_failure(request, order_id):
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


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    if not endpoint_secret:
        return HttpResponseBadRequest("Stripe webhook secret missing")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret,
        )
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {}) or {}

    # -------------------------------------------------------------------------
    # 1) checkout.session.completed  (Order payment OR wallet topup)
    # -------------------------------------------------------------------------
    if event_type == "checkout.session.completed":
        session_id = data.get("id")
        payment_intent_id = data.get("payment_intent")
        metadata = data.get("metadata", {}) or {}

        # 1A) Payment for Order
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .select_related("order")
                .filter(stripe_session_id=session_id)
                .first()
            )

            if payment:
                if payment.status == Payment.Status.SUCCEEDED:
                    return HttpResponse(status=200)

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

                order = payment.order
                if order and order.payment_status != Order.PAYMENT_PAID:
                    # triggers trust hooks
                    order.mark_as_paid()

                return HttpResponse(status=200)

        # 1B) Wallet topup
        purpose = metadata.get("purpose")
        if purpose == "wallet_topup":
            from decimal import Decimal as D
            from django.contrib.auth import get_user_model

            user_id = metadata.get("user_id")
            amount_str = metadata.get("amount")
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

            with transaction.atomic():
                wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

                # Idempotency by payment_intent_id
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

        return HttpResponse(status=200)

    # -------------------------------------------------------------------------
    # 2) Stripe disputes / chargebacks
    # -------------------------------------------------------------------------
    # NOTE: Stripe dispute object includes payment_intent / charge fields depending on event.
    if event_type == "charge.dispute.created":
        # escrow DISPUTED asap, dar fără penalizare încă
        payment_intent = data.get("payment_intent")
        if payment_intent:
            payment = Payment.objects.select_related("order").filter(
                stripe_payment_intent_id=payment_intent
            ).first()
            if payment and payment.order:
                payment.order.mark_escrow_disputed()

                # audit event (delta 0)
                try:
                    from accounts.services.trust_engine import record_event

                    record_event(
                        payment.user,
                        kind="MANUAL_ADJUST",
                        source_app="payments",
                        source_event_id=f"stripe:dispute:created:{data.get('id')}",
                        meta={
                            "event": "STRIPE_DISPUTE_CREATED",
                            "order_id": str(payment.order.id),
                            "payment_id": str(payment.id),
                            "dispute_id": str(data.get("id")),
                            "payment_intent": str(payment_intent),
                        },
                        delta_buyer=0,
                        delta_seller=0,
                        apply_bonus_sync=True,
                    )
                except Exception:
                    pass

        return HttpResponse(status=200)

    if event_type == "charge.dispute.closed":
        # Penalizăm doar dacă LOST (chargeback final)
        dispute_status = (data.get("status") or "").lower()  # won / lost / ...
        payment_intent = data.get("payment_intent")
        dispute_id = data.get("id")

        if payment_intent:
            payment = Payment.objects.select_related("order").filter(
                stripe_payment_intent_id=payment_intent
            ).first()
            if payment and payment.order:
                payment.order.mark_escrow_disputed()

                if dispute_status == "lost":
                    try:
                        from accounts.services.trust_engine import record_event
                        from accounts.services.score import DEFAULT_BUYER_WEIGHTS

                        record_event(
                            payment.user,
                            kind="MANUAL_ADJUST",
                            source_app="payments",
                            source_event_id=f"stripe:dispute:lost:{dispute_id}",
                            meta={
                                "event": "STRIPE_CHARGEBACK_LOST",
                                "order_id": str(payment.order.id),
                                "payment_id": str(payment.id),
                                "dispute_id": str(dispute_id),
                                "payment_intent": str(payment_intent),
                            },
                            delta_buyer=int(DEFAULT_BUYER_WEIGHTS.chargeback),
                            delta_seller=0,
                            apply_bonus_sync=True,
                        )
                    except Exception:
                        pass
                else:
                    # audit close (won/other)
                    try:
                        from accounts.services.trust_engine import record_event

                        record_event(
                            payment.user,
                            kind="MANUAL_ADJUST",
                            source_app="payments",
                            source_event_id=f"stripe:dispute:closed:{dispute_id}",
                            meta={
                                "event": "STRIPE_DISPUTE_CLOSED",
                                "status": dispute_status,
                                "order_id": str(payment.order.id),
                                "payment_id": str(payment.id),
                                "dispute_id": str(dispute_id),
                                "payment_intent": str(payment_intent),
                            },
                            delta_buyer=0,
                            delta_seller=0,
                            apply_bonus_sync=True,
                        )
                    except Exception:
                        pass

        return HttpResponse(status=200)

    # -------------------------------------------------------------------------
    # 3) Refund-related events (optional audit; delta 0)
    # -------------------------------------------------------------------------
    if event_type in ("refund.updated", "charge.refunded"):
        # aici poți face mapping la Payment via payment_intent / charge dacă vrei audit complet
        return HttpResponse(status=200)

    return HttpResponse(status=200)
