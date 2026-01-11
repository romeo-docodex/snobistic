# wallet/models.py
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Wallet(models.Model):
    """
    Sold intern pentru user. Ledger-ul este în WalletTransaction.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet",
    )

    currency = models.CharField(max_length=10, default="RON")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["currency"]),
        ]

    def __str__(self) -> str:
        return f"Wallet({self.user_id}) {self.balance} {self.currency}"

    @property
    def is_zero(self) -> bool:
        return self.balance <= Decimal("0.00")


class WalletTransaction(models.Model):
    """
    Ledger entry.
    Important:
    - folosim external_id pentru idempotency (Stripe payment_intent, refund_id, etc.)
    - balance_after e snapshot după tranzacție
    """

    class Type(models.TextChoices):
        TOP_UP = "TOP_UP", "Încărcare"
        WITHDRAW = "WITHDRAW", "Retragere"
        ORDER_PAYMENT = "ORDER_PAYMENT", "Plată comandă"
        REFUND = "REFUND", "Refund"
        SALE_PAYOUT = "SALE_PAYOUT", "Încasare vânzare"
        ADJUSTMENT = "ADJUSTMENT", "Ajustare"

    class Direction(models.TextChoices):
        CREDIT = "CREDIT", "Credit (+)"
        DEBIT = "DEBIT", "Debit (-)"

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    tx_type = models.CharField(max_length=30, choices=Type.choices, db_index=True)
    direction = models.CharField(max_length=10, choices=Direction.choices)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Ex: card, bank, internal, stripe_refund, etc.",
    )

    external_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="ID extern pentru idempotency (ex: Stripe payment_intent).",
    )

    note = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(blank=True, null=True)

    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["tx_type", "created_at"]),
        ]
        constraints = [
            # idempotency “best effort”: pentru același wallet + tx_type + external_id să nu duplicăm
            models.UniqueConstraint(
                fields=["wallet", "tx_type", "external_id"],
                condition=~Q(external_id=""),
                name="uniq_wallet_tx_type_external_id_when_present",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tx_type} {self.direction} {self.amount} {self.wallet.currency} (wallet={self.wallet_id})"


class WithdrawalRequest(models.Model):
    """
    Cerere retragere (workflow intern / manual).
    Pentru început: la submit debităm soldul imediat și creăm request.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "În așteptare"
        APPROVED = "APPROVED", "Aprobat"
        REJECTED = "REJECTED", "Respins"
        PAID = "PAID", "Plătit"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="withdrawals")

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00"))],
    )
    iban = models.CharField(max_length=34)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"WithdrawalRequest({self.wallet_id}) {self.amount} {self.wallet.currency} {self.status}"
