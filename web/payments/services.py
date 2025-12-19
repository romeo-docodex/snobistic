# payments/services.py
from decimal import Decimal

import stripe
from django.conf import settings
from django.utils import timezone

from orders.models import Order
from .models import Payment, Wallet, WalletTransaction, Refund

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


def charge_order_from_wallet(order: Order, user=None) -> Payment:
    """
    Plătește o comandă folosind wallet-ul intern al userului (buyer).
    - debitează wallet-ul
    - creează Payment cu provider=WALLET
    - marchează Order ca plătit (payment_status=paid, escrow=held)
    """
    if user is None:
        user = order.buyer

    wallet, _ = Wallet.objects.get_or_create(user=user)
    amount = order.total

    if amount <= 0:
        raise ValueError("Suma comenzii trebuie să fie > 0.")

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
    )

    # marcăm comanda ca plătită + escrow HELD
    if order.payment_status != Order.PAYMENT_PAID:
        order.mark_as_paid()

    return payment


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
    Creează un refund (total sau parțial) pentru un Payment.

    - validează suma (<= refundable_amount)
    - blochează eliberarea escrow-ului (marchează comanda ca DISPUTED)
    - opțional:
        * creditează wallet-ul userului
        * trimite refund și în Stripe (card)

    IMPORTANT (escrow):
    - Refund-ul este permis doar cât timp escrow-ul NU a fost eliberat către seller.
      Dacă order.escrow_status == RELEASED, ridicăm eroare și tratăm manual
      situația (ex: luat din wallet-ul sellerului).
    """
    if amount <= 0:
        raise ValueError("Suma de refund trebuie să fie > 0.")

    if amount > payment.refundable_amount:
        raise ValueError("Suma depășește valoarea disponibilă pentru refund.")

    order = payment.order
    target_user = payment.user  # în mod normal buyer-ul

    # 1) Validări legate de ESCROW
    # ----------------------------
    if order.escrow_status == Order.ESCROW_RELEASED:
        # în acest scenariu banii au fost deja plătiți seller-ului,
        # deci refund-ul automat ar crea un minus pentru platformă.
        raise ValueError(
            "Nu poți face refund automat după ce escrow-ul a fost eliberat către vânzător. "
            "Este necesară o procedură manuală (ex: ajustare din wallet-ul vânzătorului)."
        )

    # dacă încă nu este în DISPUTED, îl marcăm acum
    order.mark_escrow_disputed()

    # 2) Creăm obiectul Refund (stare PENDING)
    # ----------------------------------------
    refund = Refund.objects.create(
        payment=payment,
        order=order,
        user=target_user,
        amount=amount,
        to_wallet=to_wallet,
        status=Refund.Status.PENDING,
        reason=reason or "",
    )

    # 3) Refund prin Stripe (card) – opțional
    # ---------------------------------------
    stripe_refund_id = ""
    if via_stripe and payment.provider == Payment.Provider.STRIPE:
        if not payment.stripe_payment_intent_id:
            raise ValueError(
                "Payment nu are stripe_payment_intent_id setat – nu pot trimite refund la Stripe."
            )
        # Stripe lucrează în minor units (bani, cents)
        stripe_amount = int((amount * Decimal("100")).quantize(Decimal("1")))
        stripe_ref = stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            amount=stripe_amount,
        )
        stripe_refund_id = stripe_ref["id"]

    # 4) Refund în wallet intern (creditează buyer)
    # ---------------------------------------------
    if to_wallet:
        wallet, _ = Wallet.objects.get_or_create(user=target_user)
        wallet.balance += amount
        wallet.save(update_fields=["balance"])

        WalletTransaction.objects.create(
            user=target_user,
            transaction_type=WalletTransaction.REFUND,
            amount=amount,
            method="wallet_refund",
            balance_after=wallet.balance,
        )

    # 5) Marcăm refund-ul ca SUCCEEDED (în varianta simplă, sync)
    # ------------------------------------------------------------
    refund.status = Refund.Status.SUCCEEDED
    if stripe_refund_id:
        refund.stripe_refund_id = stripe_refund_id
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "stripe_refund_id", "processed_at"])

    return refund
