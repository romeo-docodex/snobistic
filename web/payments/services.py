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
    """
    Plătește o comandă folosind wallet-ul intern al userului (buyer).
    ENTERPRISE:
    - atomic + row lock pe Wallet
    - idempotency pe ORDER_PAYMENT (external_id = f"order:{order.id}")
    """
    if user is None:
        user = order.buyer

    if order.payment_status == Order.PAYMENT_PAID:
        # deja plătită — nu mai debităm wallet-ul
        return order.payments.order_by("-created_at").first()

    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
    amount = order.total

    if amount <= 0:
        raise ValueError("Suma comenzii trebuie să fie > 0.")

    # Idempotency: dacă există deja tranzacție ORDER_PAYMENT pt acest order, ieșim
    ext_id = f"order:{order.id}:wallet_payment"
    if WalletTransaction.objects.filter(
        user=user,
        transaction_type=WalletTransaction.ORDER_PAYMENT,
        external_id=ext_id,
    ).exists():
        # asigurăm și comanda ca PAID dacă cumva lipsește
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

    # debităm wallet-ul
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

    # marcăm comanda ca plătită + escrow HELD (declanșează trust hooks)
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
    """
    Refund total/parțial pentru un Payment.
    ENTERPRISE:
    - atomic
    - idempotency pentru creditare wallet (external_id = f"refund:{refund.id}" / stripe_refund_id)
    - escrow DISPUTED (ordine safe)
    """
    if amount <= 0:
        raise ValueError("Suma de refund trebuie să fie > 0.")

    if amount > payment.refundable_amount:
        raise ValueError("Suma depășește valoarea disponibilă pentru refund.")

    order = payment.order
    target_user = payment.user  # în mod normal buyer-ul

    # 1) Validări legate de ESCROW
    if order.escrow_status == Order.ESCROW_RELEASED:
        raise ValueError(
            "Nu poți face refund automat după ce escrow-ul a fost eliberat către vânzător. "
            "Este necesară o procedură manuală (ex: ajustare din wallet-ul vânzătorului)."
        )

    # 2) escrow DISPUTED (blochează release)
    order.mark_escrow_disputed()

    # 3) Creăm Refund PENDING
    refund = Refund.objects.create(
        payment=payment,
        order=order,
        user=target_user,
        amount=amount,
        to_wallet=to_wallet,
        status=Refund.Status.PENDING,
        reason=reason or "",
    )

    # 4) Refund prin Stripe (card) – opțional
    stripe_refund_id = ""
    if via_stripe and payment.provider == Payment.Provider.STRIPE:
        if not payment.stripe_payment_intent_id:
            raise ValueError(
                "Payment nu are stripe_payment_intent_id setat – nu pot trimite refund la Stripe."
            )
        stripe_amount = int((amount * Decimal("100")).quantize(Decimal("1")))
        stripe_ref = stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            amount=stripe_amount,
        )
        stripe_refund_id = stripe_ref["id"]

    # 5) Refund în wallet intern (creditează buyer) + idempotency
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

    # 6) SUCCEEDED
    refund.status = Refund.Status.SUCCEEDED
    if stripe_refund_id:
        refund.stripe_refund_id = stripe_refund_id
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "stripe_refund_id", "processed_at"])

    # (Opțional) TRUST audit event fără delta — recomandat pentru trasabilitate.
    try:
        from accounts.services.trust_engine import record_event

        record_event(
            target_user,
            kind="MANUAL_ADJUST",
            source_app="payments",
            source_event_id=f"refund:{refund.id}:succeeded",
            meta={
                "event": "REFUND_SUCCEEDED",
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "amount": str(amount),
                "via_stripe": bool(via_stripe),
                "to_wallet": bool(to_wallet),
                "reason": reason or "",
            },
            delta_buyer=0,
            delta_seller=0,
            apply_bonus_sync=True,
        )
    except Exception:
        pass

    return refund
