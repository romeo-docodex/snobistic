# payments/views.py
from __future__ import annotations

import json

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from .models import Payment
from .signals import payment_succeeded, payment_failed, payment_canceled

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


@login_required
def payment_confirm(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)

    if order.payment_status == Order.PAYMENT_PAID:
        messages.info(request, f"Comanda #{order.id} este deja plătită.")
        return redirect("cart:checkout_success", order_id=order.id)

    if not stripe.api_key:
        messages.error(request, "Plata online nu este disponibilă momentan (config Stripe lipsă).")
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
                            "metadata": {"order_id": str(order.id)},
                        },
                        "unit_amount": payment.amount_minor_units,
                    },
                    "quantity": 1,
                }
            ],
            metadata={"order_id": str(order.id), "payment_id": str(payment.id), "user_id": str(request.user.id)},
            automatic_payment_methods={"enabled": True},
            success_url=(
                request.build_absolute_uri(reverse("payments:payment_success", args=[order.id]))
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=request.build_absolute_uri(reverse("payments:payment_failure", args=[order.id])),
        )
    except Exception as e:
        messages.error(request, f"A apărut o eroare la inițierea plății: {e}")
        return redirect("cart:checkout_cancel")

    payment.stripe_session_id = session.id

    # ✅ salvează JSON serializabil (nu obiect Stripe brut)
    try:
        payment.raw_response = session.to_dict()  # stripe-python modern
    except Exception:
        try:
            payment.raw_response = dict(session)
        except Exception:
            payment.raw_response = {"id": session.id}

    payment.save(update_fields=["stripe_session_id", "raw_response"])

    return redirect(session.url, code=303)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    payment = order.payments.order_by("-created_at").first()
    paid = order.payment_status == Order.PAYMENT_PAID
    return render(request, "payments/payment_success.html", {"order": order, "payment": payment, "paid": paid})


@login_required
def payment_failure(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    payment = order.payments.order_by("-created_at").first()
    messages.error(request, "Plata nu a fost procesată. Poți încerca din nou sau alege altă metodă.")
    return render(request, "payments/payment_failure.html", {"order": order, "payment": payment})


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    if not endpoint_secret:
        return HttpResponseBadRequest("Stripe webhook secret missing")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {}) or {}

    # ------------------------------------------------------------
    # 1) Success: checkout.session.completed
    # ------------------------------------------------------------
    if event_type == "checkout.session.completed":
        session_id = data.get("id")
        payment_intent_id = data.get("payment_intent")

        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .select_related("order")
                .filter(stripe_session_id=session_id)
                .first()
            )

            if not payment:
                return HttpResponse(status=200)

            if payment.status == Payment.Status.SUCCEEDED:
                return HttpResponse(status=200)

            payment.status = Payment.Status.SUCCEEDED
            if payment_intent_id:
                payment.stripe_payment_intent_id = payment_intent_id

            payment.raw_response = data
            payment.save(update_fields=["status", "stripe_payment_intent_id", "raw_response"])

            order = payment.order
            if order and order.payment_status != Order.PAYMENT_PAID:
                order.mark_as_paid()

            # ✅ event pentru integrare (wallet / notificări / analytics)
            payment_succeeded.send(sender=Payment, payment=payment, order=order)

        return HttpResponse(status=200)

    # ------------------------------------------------------------
    # 2) Expired / Fail
    # ------------------------------------------------------------
    if event_type == "checkout.session.expired":
        session_id = data.get("id")
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .select_related("order")
                .filter(stripe_session_id=session_id)
                .first()
            )
            if payment and payment.status == Payment.Status.PENDING:
                payment.status = Payment.Status.CANCELED
                payment.raw_response = data
                payment.save(update_fields=["status", "raw_response"])

                if payment.order and payment.order.payment_status != Order.PAYMENT_PAID:
                    payment.order.mark_payment_cancelled()

                payment_canceled.send(sender=Payment, payment=payment, order=payment.order)

        return HttpResponse(status=200)

    if event_type in ("checkout.session.async_payment_failed", "payment_intent.payment_failed"):
        payment_intent_id = data.get("payment_intent") or data.get("id")
        if payment_intent_id:
            with transaction.atomic():
                payment = (
                    Payment.objects.select_for_update()
                    .select_related("order")
                    .filter(stripe_payment_intent_id=payment_intent_id)
                    .first()
                )
                if payment and payment.status != Payment.Status.SUCCEEDED:
                    payment.status = Payment.Status.FAILED
                    payment.raw_response = data
                    payment.save(update_fields=["status", "raw_response"])

                    if payment.order and payment.order.payment_status != Order.PAYMENT_PAID:
                        payment.order.mark_payment_failed()

                    payment_failed.send(sender=Payment, payment=payment, order=payment.order)

        return HttpResponse(status=200)

    # ------------------------------------------------------------
    # 3) Disputes / chargebacks (escrow order-side)
    # ------------------------------------------------------------
    if event_type == "charge.dispute.created":
        payment_intent = data.get("payment_intent")
        if payment_intent:
            payment = Payment.objects.select_related("order").filter(
                stripe_payment_intent_id=payment_intent
            ).first()
            if payment and payment.order:
                payment.order.mark_escrow_disputed()
        return HttpResponse(status=200)

    if event_type == "charge.dispute.closed":
        dispute_status = (data.get("status") or "").lower()
        payment_intent = data.get("payment_intent")

        if payment_intent:
            payment = Payment.objects.select_related("order").filter(
                stripe_payment_intent_id=payment_intent
            ).first()
            if payment and payment.order:
                payment.order.mark_escrow_disputed()
                if dispute_status == "lost":
                    payment.order.mark_chargeback()

        return HttpResponse(status=200)

    return HttpResponse(status=200)
