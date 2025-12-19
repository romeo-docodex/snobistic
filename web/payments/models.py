# payments/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum


class Payment(models.Model):
    """
    Plată procesată prin Stripe (sau Wallet intern / Numerar).
    Un Order poate avea mai multe încercări de plată (multiple Payment-uri).
    """

    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        WALLET = "wallet", "Wallet intern"
        CASH = "cash", "Numerar / Ramburs"

    class Status(models.TextChoices):
        PENDING = "pending", "În așteptare"
        SUCCEEDED = "succeeded", "Reușit"
        FAILED = "failed", "Eșuat"
        CANCELED = "canceled", "Anulat"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.STRIPE,
    )

    # dacă plata a folosit un wallet intern (provider=WALLET)
    wallet = models.ForeignKey(
        "Wallet",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
        help_text="Dacă plata a folosit un wallet intern, este legată aici.",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Suma totală plătită pentru comanda aceasta (în moneda de mai jos).",
    )
    currency = models.CharField(
        max_length=10,
        default="RON",
        help_text="Moneda (ex: RON, EUR).",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Stripe specific
    stripe_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="ID-ul Checkout Session din Stripe.",
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Payment Intent ID din Stripe (dacă este disponibil).",
    )

    # Pentru debugging / audit – răspunsul JSON de la Stripe
    raw_response = models.JSONField(
        blank=True,
        null=True,
        help_text="Payload JSON Stripe (ultima versiune cunoscută).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment #{self.pk} – Order #{self.order_id} – {self.amount} {self.currency}"

    @property
    def is_successful(self) -> bool:
        return self.status == self.Status.SUCCEEDED

    @property
    def amount_minor_units(self) -> int:
        """
        Stripe lucrează în 'minor units' (bani, cents).
        Pentru RON: 10.50 RON => 1050.
        """
        return int((self.amount * Decimal("100")).quantize(Decimal("1")))

    @property
    def refunded_amount(self) -> Decimal:
        """
        Totalul deja returnat (pending + succeeded) pentru acest payment.
        """
        total = (
            self.refunds.filter(
                status__in=[Refund.Status.PENDING, Refund.Status.SUCCEEDED]
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        return total

    @property
    def refundable_amount(self) -> Decimal:
        """
        Cât mai poți returna (pentru partial/full refund).
        """
        return max(Decimal("0.00"), self.amount - self.refunded_amount)


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Wallet {self.user.email}: {self.balance} RON"


class WalletTransaction(models.Model):
    TOP_UP = "topup"
    WITHDRAW = "withdraw"
    ORDER_PAYMENT = "order_payment"
    REFUND = "refund"
    SALE_PAYOUT = "sale_payout"

    TYPES = [
        (TOP_UP, "Încărcare"),
        (WITHDRAW, "Retragere"),
        (ORDER_PAYMENT, "Plată comandă"),
        (REFUND, "Refund către client"),
        (SALE_PAYOUT, "Încasare vânzare"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
    )
    transaction_type = models.CharField(max_length=20, choices=TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50)  # e.g. 'card', 'bank', 'wallet'
    date = models.DateTimeField(auto_now_add=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    # nou: pentru idempotency / tracking extern (Stripe, etc.)
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID tranzacție externă (ex: Stripe payment_intent).",
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return (
            f"{self.get_transaction_type_display()} {self.amount} RON "
            f"on {self.date.strftime('%Y-%m-%d %H:%M')}"
        )


class Refund(models.Model):
    """
    Refund total/parțial pentru un Payment.
    Poate fi trimis în wallet intern și/sau prin Stripe (refund card).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "În așteptare"
        SUCCEEDED = "succeeded", "Reușit"
        FAILED = "failed", "Eșuat"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refunds",
        help_text="Cui îi facem refund (în mod normal buyer-ul).",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    to_wallet = models.BooleanField(
        default=True,
        help_text="Dacă True, suma se creditează în walletul userului.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Dacă facem refund prin Stripe
    stripe_refund_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID refund Stripe (dacă e cazul).",
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Motivul refund-ului (intern/admin).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund #{self.pk} – Payment #{self.payment_id} – {self.amount} {self.payment.currency}"
