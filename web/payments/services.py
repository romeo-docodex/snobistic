# payments/services.py
from __future__ import annotations

from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from .models import Payment, Wallet, WalletTransaction, Refund

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


@transaction.atomic
def charge_order_from_wallet(order: Order, user=None) -> Payment:
    if user is None:
        user = order.buyer

    if order.payment_status == Order.PAYMENT_PAID:
        return order.payments.order_by("-created_at").first()

    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
    amount = order.total

    if amount <= 0:
        raise ValueError("Suma comenzii trebuie să fie > 0.")

    ext_id = f"order:{order.id}:wallet_payment"
    if WalletTransaction.objects.filter(
        user=user,
        transaction_type=WalletTransaction.ORDER_PAYMENT,
        external_id=ext_id,
    ).exists():
        if order.payment_status != Order.PAYMENT_PAID:
            order.mark_as_paid()
        return order.payments.order_by("-created_at").first()

    if wallet.balance < amount:
        raise ValueError("Fonduri insuficiente în wallet pentru această comandă.")

    payment = Payment.objects.create(
        order=order,
        user=user,
        provider=Payment.Provider.WALLET,
        wallet=wallet,
        amount=amount,
        currency=getattr(settings, "SNOBISTIC_CURRENCY", "RON").upper(),
        status=Payment.Status.SUCCEEDED,
    )

    wallet.balance -= amount
    wallet.save(update_fields=["balance"])

    WalletTransaction.objects.create(
        user=user,
        transaction_type=WalletTransaction.ORDER_PAYMENT,
        amount=amount,
        method="wallet",
        balance_after=wallet.balance,
        external_id=ext_id,
    )

    order.mark_as_paid()
    return payment


@transaction.atomic
def refund_payment(
    payment: Payment,
    amount: Decimal,
    *,
    by_user,
    reason: str = "",
    to_wallet: bool = True,
    via_stripe: bool = False,
) -> Refund:
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
        to_wallet=to_wallet,
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

    if to_wallet:
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=target_user)

        ext_id = stripe_refund_id or f"refund:{refund.id}"
        if not WalletTransaction.objects.filter(
            user=target_user,
            transaction_type=WalletTransaction.REFUND,
            external_id=ext_id,
        ).exists():
            wallet.balance += amount
            wallet.save(update_fields=["balance"])

            WalletTransaction.objects.create(
                user=target_user,
                transaction_type=WalletTransaction.REFUND,
                amount=amount,
                method="wallet_refund",
                balance_after=wallet.balance,
                external_id=ext_id,
            )

    refund.status = Refund.Status.SUCCEEDED
    if stripe_refund_id:
        refund.stripe_refund_id = stripe_refund_id
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "stripe_refund_id", "processed_at"])

    # ✅ dacă după refund nu mai rămâne nimic refundable -> FULL REFUND -> Order REFUNDED
    # (payment.refundable_amount e calculat din refunds PENDING+SUCCEEDED)
    if payment.refundable_amount <= Decimal("0.00"):
        try:
            order.mark_as_refunded()
        except Exception:
            pass

    return refund
