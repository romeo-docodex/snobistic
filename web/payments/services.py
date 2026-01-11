# payments/services.py
from __future__ import annotations

from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from .models import Payment, Refund
from .signals import refund_succeeded

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


@transaction.atomic
def refund_payment(
    payment: Payment,
    amount: Decimal,
    *,
    by_user,
    reason: str = "",
    via_stripe: bool = False,
) -> Refund:
    """
    Refund total/parțial pentru un Payment.
    IMPORTANT: payments NU creditează wallet.
    Wallet app va asculta semnalul refund_succeeded dacă vrei credit intern.
    """
    if amount <= 0:
        raise ValueError("Suma de refund trebuie să fie > 0.")

    if amount > payment.refundable_amount:
        raise ValueError("Suma depășește valoarea disponibilă pentru refund.")

    order = payment.order
    target_user = payment.user  # buyer

    if order.escrow_status == Order.ESCROW_RELEASED:
        raise ValueError(
            "Nu poți face refund automat după ce escrow-ul a fost eliberat către vânzător. "
            "Necesită procedură manuală."
        )

    # Blochează release
    order.mark_escrow_disputed()

    refund = Refund.objects.create(
        payment=payment,
        order=order,
        user=target_user,
        amount=amount,
        status=Refund.Status.PENDING,
        reason=reason or "",
    )

    stripe_refund_id = ""
    if via_stripe and payment.provider == Payment.Provider.STRIPE:
        if not payment.stripe_payment_intent_id:
            raise ValueError("Payment nu are stripe_payment_intent_id setat – nu pot trimite refund la Stripe.")
        stripe_amount = int((amount * Decimal("100")).quantize(Decimal("1")))
        stripe_ref = stripe.Refund.create(payment_intent=payment.stripe_payment_intent_id, amount=stripe_amount)
        stripe_refund_id = stripe_ref["id"]

    refund.status = Refund.Status.SUCCEEDED
    if stripe_refund_id:
        refund.stripe_refund_id = stripe_refund_id
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "stripe_refund_id", "processed_at"])

    # Dacă e full refund -> Order REFUNDED
    if payment.refundable_amount <= Decimal("0.00"):
        try:
            order.mark_as_refunded()
        except Exception:
            pass

    # ✅ semnal pentru wallet/notifications
    refund_succeeded.send(sender=Refund, refund=refund, payment=payment, order=order)

    return refund
