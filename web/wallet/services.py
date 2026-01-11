# wallet/services.py
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import Wallet, WalletTransaction


class WalletError(Exception):
    pass


class InsufficientFunds(WalletError):
    pass


def _currency() -> str:
    return getattr(settings, "SNOBISTIC_CURRENCY", "RON").upper()


def get_or_create_wallet_for_user_readonly(user) -> Wallet:
    """
    Read-only helper (NU pune lock).
    Folosește-l în context processors și views de UI.
    """
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        defaults={"currency": _currency()},
    )
    return wallet


@transaction.atomic
def get_or_create_wallet_for_user(user) -> Wallet:
    """
    Locked helper (select_for_update) — folosește-l DOAR în operații financiare.
    """
    wallet, _ = Wallet.objects.select_for_update().get_or_create(
        user=user,
        defaults={"currency": _currency()},
    )
    return wallet


@transaction.atomic
def credit_wallet(
    *,
    user,
    amount: Decimal,
    tx_type: str,
    method: str = "",
    external_id: str = "",
    note: str = "",
    meta: dict | None = None,
) -> WalletTransaction:
    if amount <= 0:
        raise ValueError("amount must be > 0")

    wallet = get_or_create_wallet_for_user(user)

    if external_id:
        existing = WalletTransaction.objects.filter(
            wallet=wallet,
            tx_type=tx_type,
            external_id=external_id,
        ).first()
        if existing:
            return existing

    wallet.balance += amount
    wallet.save(update_fields=["balance"])

    tx = WalletTransaction.objects.create(
        wallet=wallet,
        tx_type=tx_type,
        direction=WalletTransaction.Direction.CREDIT,
        amount=amount,
        method=method or "",
        external_id=external_id or "",
        note=note or "",
        meta=meta,
        balance_after=wallet.balance,
    )
    return tx


@transaction.atomic
def debit_wallet(
    *,
    user,
    amount: Decimal,
    tx_type: str,
    method: str = "",
    external_id: str = "",
    note: str = "",
    meta: dict | None = None,
) -> WalletTransaction:
    if amount <= 0:
        raise ValueError("amount must be > 0")

    wallet = get_or_create_wallet_for_user(user)

    if external_id:
        existing = WalletTransaction.objects.filter(
            wallet=wallet,
            tx_type=tx_type,
            external_id=external_id,
        ).first()
        if existing:
            return existing

    if wallet.balance < amount:
        raise InsufficientFunds("Insufficient funds")

    wallet.balance -= amount
    wallet.save(update_fields=["balance"])

    tx = WalletTransaction.objects.create(
        wallet=wallet,
        tx_type=tx_type,
        direction=WalletTransaction.Direction.DEBIT,
        amount=amount,
        method=method or "",
        external_id=external_id or "",
        note=note or "",
        meta=meta,
        balance_after=wallet.balance,
    )
    return tx


@transaction.atomic
def charge_order_from_wallet(*args, **kwargs):
    """
    (păstrat exact ca la tine, doar că folosește _currency() de aici)
    """
    order = kwargs.pop("order", None)
    user = kwargs.pop("user", None)

    if order is None:
        for a in args:
            if hasattr(a, "total") and hasattr(a, "buyer_id"):
                order = a
                break

    if user is None:
        for a in args:
            if hasattr(a, "is_authenticated"):
                user = a
                break

    if order is None:
        raise ValueError("charge_order_from_wallet: missing order")

    payer = user or getattr(order, "buyer", None)
    if payer is None:
        raise ValueError("charge_order_from_wallet: missing user (and order has no buyer)")

    amount = Decimal(kwargs.pop("amount", None) or getattr(order, "total", None) or "0.00")
    if amount <= 0:
        raise ValueError("charge_order_from_wallet: amount must be > 0")

    external_id = (kwargs.pop("external_id", "") or "").strip() or f"order:{order.pk}"
    note = kwargs.pop("note", "") or ""
    meta = kwargs.pop("meta", None)

    from orders.models import Order
    from payments.models import Payment

    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.payment_status == Order.PAYMENT_PAID and order.escrow_status == Order.ESCROW_HELD:
        existing = (
            Payment.objects.filter(order=order, user=payer)
            .filter(status=Payment.Status.SUCCEEDED)
            .order_by("-created_at")
            .first()
        )
        if existing:
            return existing, None
        p = Payment.objects.create(
            order=order,
            user=payer,
            provider=Payment.Provider.WALLET if hasattr(Payment.Provider, "WALLET") else "wallet",
            amount=amount,
            currency=_currency(),
            status=Payment.Status.SUCCEEDED,
            raw_response={"source": "wallet", "note": "order already paid"},
        )
        return p, None

    paid = Payment.objects.filter(
        order=order,
        user=payer,
        provider=getattr(Payment.Provider, "WALLET", "wallet"),
        status=Payment.Status.SUCCEEDED,
    ).order_by("-created_at").first()
    if paid:
        order.mark_as_paid()
        return paid, None

    payment = Payment.objects.create(
        order=order,
        user=payer,
        provider=getattr(Payment.Provider, "WALLET", "wallet"),
        amount=amount,
        currency=_currency(),
        status=Payment.Status.PENDING,
        raw_response={"source": "wallet", "external_id": external_id, "meta": meta or {}},
    )

    try:
        tx = debit_wallet(
            user=payer,
            amount=amount,
            tx_type=WalletTransaction.Type.ORDER_PAYMENT,
            method="wallet",
            external_id=external_id,
            note=note or f"Plată comandă #{order.pk}",
            meta={"order_id": order.pk, "payment_id": payment.pk, **(meta or {})},
        )

        payment.status = Payment.Status.SUCCEEDED
        payment.raw_response = {
            **(payment.raw_response or {}),
            "wallet_tx_id": tx.pk,
            "balance_after": str(tx.balance_after),
        }
        payment.save(update_fields=["status", "raw_response", "updated_at"])

        order.mark_as_paid()

        try:
            from payments.signals import payment_succeeded
            payment_succeeded.send(sender=Payment, payment=payment, order=order)
        except Exception:
            pass

        return payment, tx

    except InsufficientFunds:
        payment.status = Payment.Status.FAILED
        payment.raw_response = {**(payment.raw_response or {}), "error": "insufficient_funds"}
        payment.save(update_fields=["status", "raw_response", "updated_at"])
        order.mark_payment_failed()

        try:
            from payments.signals import payment_failed
            payment_failed.send(sender=Payment, payment=payment, order=order)
        except Exception:
            pass

        raise

    except Exception as e:
        payment.status = Payment.Status.FAILED
        payment.raw_response = {**(payment.raw_response or {}), "error": str(e)}
        payment.save(update_fields=["status", "raw_response", "updated_at"])
        order.mark_payment_failed()

        try:
            from payments.signals import payment_failed
            payment_failed.send(sender=Payment, payment=payment, order=order)
        except Exception:
            pass

        raise
