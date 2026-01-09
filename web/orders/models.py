# orders/models.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property

from accounts.models import Address


def _pct(amount: Decimal, percent: Decimal) -> Decimal:
    """
    Calculează percent (%) din amount, rotunjit la 2 zecimale.
    """
    if amount is None:
        amount = Decimal("0.00")
    return (amount * percent / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


class Order(models.Model):
    # -----------------------------
    # Order type
    # -----------------------------
    TYPE_STANDARD = "standard"
    TYPE_AUCTION_WIN = "auction_win"
    TYPE_CHOICES = [
        (TYPE_STANDARD, "Comandă magazin"),
        (TYPE_AUCTION_WIN, "Comandă licitație"),
    ]

    # -----------------------------
    # Lifecycle status (high-level)
    # -----------------------------
    STATUS_CREATED = "created"
    STATUS_AWAITING_PAYMENT = "awaiting_payment"
    STATUS_PAID = "paid"
    STATUS_SHIPPED = "shipped"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_DELIVERED = "delivered"
    STATUS_COMPLETED = "completed"
    STATUS_REFUNDED = "refunded"
    STATUS_DISPUTED = "disputed"
    STATUS_CANCELLED_BY_BUYER = "cancelled_by_buyer"
    STATUS_CANCELLED_BY_SELLER = "cancelled_by_seller"
    STATUS_CANCELLED_BY_ADMIN = "cancelled_by_admin"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Creată"),
        (STATUS_AWAITING_PAYMENT, "În așteptare plată"),
        (STATUS_PAID, "Plătită"),
        (STATUS_SHIPPED, "Predată curierului"),
        (STATUS_IN_TRANSIT, "În tranzit"),
        (STATUS_DELIVERED, "Livrată"),
        (STATUS_COMPLETED, "Finalizată"),
        (STATUS_REFUNDED, "Rambursată"),
        (STATUS_DISPUTED, "În dispută"),
        (STATUS_CANCELLED_BY_BUYER, "Anulată de cumpărător"),
        (STATUS_CANCELLED_BY_SELLER, "Anulată de vânzător"),
        (STATUS_CANCELLED_BY_ADMIN, "Anulată de Snobistic"),
    ]

    # -----------------------------
    # Payment status (low-level)
    # -----------------------------
    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_CANCELLED = "cancelled"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_CHARGEBACK = "chargeback"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "În așteptare"),
        (PAYMENT_PAID, "Plătită"),
        (PAYMENT_FAILED, "Eșuată"),
        (PAYMENT_CANCELLED, "Anulată"),
        (PAYMENT_REFUNDED, "Rambursată"),
        (PAYMENT_CHARGEBACK, "Chargeback"),
    ]

    # -----------------------------
    # Shipping status (low-level)
    # -----------------------------
    SHIPPING_PENDING = "pending"
    SHIPPING_SHIPPED = "shipped"
    SHIPPING_IN_TRANSIT = "in_transit"
    SHIPPING_DELIVERED = "delivered"
    SHIPPING_RETURNED = "returned"
    SHIPPING_CANCELLED = "cancelled"

    SHIPPING_STATUS_CHOICES = [
        (SHIPPING_PENDING, "Neexpediată"),
        (SHIPPING_SHIPPED, "Predată curierului"),
        (SHIPPING_IN_TRANSIT, "În tranzit"),
        (SHIPPING_DELIVERED, "Livrată"),
        (SHIPPING_RETURNED, "Returnată"),
        (SHIPPING_CANCELLED, "Anulată"),
    ]

    # -----------------------------
    # Escrow status
    # -----------------------------
    ESCROW_PENDING = "pending"
    ESCROW_HELD = "held"
    ESCROW_RELEASED = "released"
    ESCROW_DISPUTED = "disputed"
    ESCROW_REFUNDED = "refunded"

    ESCROW_STATUS_CHOICES = [
        (ESCROW_PENDING, "În așteptare plată"),
        (ESCROW_HELD, "Fonduri în escrow"),
        (ESCROW_RELEASED, "Escrow eliberat"),
        (ESCROW_DISPUTED, "Escrow în dispută"),
        (ESCROW_REFUNDED, "Escrow rambursat"),
    ]

    # -----------------------------
    # Core relations
    # -----------------------------
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        verbose_name="Adresă livrare",
    )

    shipping_method = models.CharField(max_length=50)

    order_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_STANDARD,
    )

    # New: lifecycle status (for UI)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
        db_index=True,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
        db_index=True,
    )
    shipping_status = models.CharField(
        max_length=20,
        choices=SHIPPING_STATUS_CHOICES,
        default=SHIPPING_PENDING,
        db_index=True,
    )
    escrow_status = models.CharField(
        max_length=20,
        choices=ESCROW_STATUS_CHOICES,
        default=ESCROW_PENDING,
        db_index=True,
    )

    # -----------------------------
    # Amounts
    # -----------------------------
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    buyer_protection_fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    shipping_days_min = models.PositiveSmallIntegerField(
        default=0,
        help_text="Număr minim de zile până la livrare (handling + curier).",
    )
    shipping_days_max = models.PositiveSmallIntegerField(
        default=0,
        help_text="Număr maxim de zile până la livrare.",
    )

    seller_commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # -----------------------------
    # Timestamps (audit)
    # -----------------------------
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comanda #{self.pk} de {self.buyer}"

    @property
    def buyer_protection_percent(self) -> Decimal:
        return Decimal(getattr(settings, "SNOBISTIC_BUYER_PROTECTION_PERCENT", "5.0"))

    @property
    def seller_commission_percent(self) -> Decimal:
        return Decimal(getattr(settings, "SNOBISTIC_SELLER_COMMISSION_PERCENT", "9.0"))

    @cached_property
    def latest_payment(self):
        return self.payments.order_by("-created_at").first()

    @property
    def payment_status_label(self) -> str:
        # Preferăm Payment.status dacă există (mai granular), altfel Order.payment_status
        if self.latest_payment:
            return self.latest_payment.get_status_display()
        return self.get_payment_status_display()

    @property
    def escrow_status_label(self) -> str:
        return self.get_escrow_status_display()

    @property
    def has_pending_return(self) -> bool:
        return self.return_requests.filter(status=ReturnRequest.STATUS_PENDING).exists()

    def get_payment_url(self):
        return reverse("payments:payment_confirm", args=[self.id])

    # -----------------------------
    # Lifecycle sync helpers
    # -----------------------------
    def _ensure_awaiting_payment_if_needed(self):
        if self.status == self.STATUS_CREATED:
            self.status = self.STATUS_AWAITING_PAYMENT

    def _set_status_if_not_terminal(self, new_status: str):
        terminal = {
            self.STATUS_COMPLETED,
            self.STATUS_REFUNDED,
            self.STATUS_CANCELLED_BY_BUYER,
            self.STATUS_CANCELLED_BY_SELLER,
            self.STATUS_CANCELLED_BY_ADMIN,
        }
        if self.status in terminal:
            return
        self.status = new_status

    # -----------------------------
    # Payment transitions
    # -----------------------------
    def mark_as_paid(self):
        """
        Payment confirmed -> escrow HELD.
        Idempotent.
        """
        if self.payment_status == self.PAYMENT_PAID and self.escrow_status == self.ESCROW_HELD:
            return

        now = timezone.now()

        self.payment_status = self.PAYMENT_PAID
        self.escrow_status = self.ESCROW_HELD
        self.paid_at = self.paid_at or now

        # high-level status
        self._set_status_if_not_terminal(self.STATUS_PAID)

        self.save(update_fields=["payment_status", "escrow_status", "paid_at", "status"])

        try:
            from .services.trust_hooks import on_order_paid
            on_order_paid(self.id)
        except Exception:
            pass

    def mark_payment_failed(self):
        """
        Stripe/wallet payment failed (but order can still be retried).
        """
        if self.payment_status == self.PAYMENT_PAID:
            return
        if self.payment_status == self.PAYMENT_FAILED:
            return

        self.payment_status = self.PAYMENT_FAILED
        self._ensure_awaiting_payment_if_needed()
        self.save(update_fields=["payment_status", "status"])

    def mark_payment_cancelled(self):
        """
        User cancelled checkout. Order stays retryable.
        """
        if self.payment_status == self.PAYMENT_PAID:
            return
        if self.payment_status == self.PAYMENT_CANCELLED:
            return

        self.payment_status = self.PAYMENT_CANCELLED
        self._ensure_awaiting_payment_if_needed()
        self.save(update_fields=["payment_status", "status"])

    def mark_as_refunded(self):
        """
        Full refund processed -> payment REFUNDED + escrow REFUNDED.
        """
        now = timezone.now()

        self.payment_status = self.PAYMENT_REFUNDED
        self.escrow_status = self.ESCROW_REFUNDED
        self.refunded_at = self.refunded_at or now

        # high-level
        self.status = self.STATUS_REFUNDED

        self.save(update_fields=["payment_status", "escrow_status", "refunded_at", "status"])

    def mark_chargeback(self):
        """
        Chargeback / dispute lost -> treat as CHARGEBACK and disputed.
        """
        now = timezone.now()

        self.payment_status = self.PAYMENT_CHARGEBACK
        self.escrow_status = self.ESCROW_DISPUTED
        self.disputed_at = self.disputed_at or now
        self.status = self.STATUS_DISPUTED

        self.save(update_fields=["payment_status", "escrow_status", "disputed_at", "status"])

    # -----------------------------
    # Shipping transitions
    # -----------------------------
    def mark_shipped(self, *, shipped_at=None):
        """
        Seller handed to courier.
        """
        shipped_at = shipped_at or timezone.now()

        if self.shipping_status == self.SHIPPING_SHIPPED:
            # ensure lifecycle timestamp if missing
            if not self.shipped_at:
                self.shipped_at = shipped_at
                self._set_status_if_not_terminal(self.STATUS_SHIPPED)
                self.save(update_fields=["shipped_at", "status"])
            return

        self.shipping_status = self.SHIPPING_SHIPPED
        self.shipped_at = self.shipped_at or shipped_at
        self._set_status_if_not_terminal(self.STATUS_SHIPPED)
        self.save(update_fields=["shipping_status", "shipped_at", "status"])

    def mark_in_transit(self):
        if self.shipping_status in (self.SHIPPING_DELIVERED, self.SHIPPING_RETURNED):
            return
        self.shipping_status = self.SHIPPING_IN_TRANSIT
        self._set_status_if_not_terminal(self.STATUS_IN_TRANSIT)
        self.save(update_fields=["shipping_status", "status"])

    def mark_delivered(self, *, delivered_at=None):
        delivered_at = delivered_at or timezone.now()

        if self.shipping_status == self.SHIPPING_DELIVERED:
            if not self.delivered_at:
                self.delivered_at = delivered_at
                self._set_status_if_not_terminal(self.STATUS_DELIVERED)
                self.save(update_fields=["delivered_at", "status"])
            return

        self.shipping_status = self.SHIPPING_DELIVERED
        self.delivered_at = self.delivered_at or delivered_at
        self._set_status_if_not_terminal(self.STATUS_DELIVERED)
        self.save(update_fields=["shipping_status", "delivered_at", "status"])

    def mark_returned(self):
        self.shipping_status = self.SHIPPING_RETURNED
        self.save(update_fields=["shipping_status"])

    # -----------------------------
    # Escrow transitions
    # -----------------------------
    def _payout_sellers_from_escrow(self):
        from collections import defaultdict
        from payments.models import Wallet, WalletTransaction

        per_seller_gross = defaultdict(lambda: Decimal("0.00"))

        items_qs = self.items.select_related("product__owner")
        for item in items_qs:
            seller = getattr(item.product, "owner", None)
            if not seller:
                continue
            line_total = (item.price * item.quantity).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            per_seller_gross[seller] += line_total

        commission_percent = self.seller_commission_percent

        for seller, gross in per_seller_gross.items():
            if gross <= 0:
                continue

            commission = _pct(gross, commission_percent)
            net = gross - commission

            if net <= 0:
                continue

            wallet, _ = Wallet.objects.get_or_create(user=seller)
            wallet.balance += net
            wallet.save(update_fields=["balance"])

            WalletTransaction.objects.create(
                user=seller,
                transaction_type=WalletTransaction.SALE_PAYOUT,
                amount=net,
                method="escrow_release",
                balance_after=wallet.balance,
            )

    def release_escrow(self, *, force: bool = False):
        if self.escrow_status != self.ESCROW_HELD:
            return

        if not force:
            # minim: trebuie să fie predată curierului / în tranzit / livrată
            if self.shipping_status not in (
                self.SHIPPING_SHIPPED,
                self.SHIPPING_IN_TRANSIT,
                self.SHIPPING_DELIVERED,
            ):
                return
            if self.has_pending_return:
                return

        self._payout_sellers_from_escrow()
        self.escrow_status = self.ESCROW_RELEASED
        self.save(update_fields=["escrow_status"])

        # high-level: dacă e livrată și nu există retur pending -> poate fi completed
        if self.shipping_status == self.SHIPPING_DELIVERED and not self.has_pending_return:
            self.status = self.STATUS_COMPLETED
            self.completed_at = self.completed_at or timezone.now()
            self.save(update_fields=["status", "completed_at"])

        try:
            from .services.trust_hooks import on_escrow_released
            on_escrow_released(self.id)
        except Exception:
            pass

    def mark_escrow_disputed(self):
        if self.escrow_status in (self.ESCROW_HELD, self.ESCROW_PENDING):
            self.escrow_status = self.ESCROW_DISPUTED
            self.disputed_at = self.disputed_at or timezone.now()
            self.status = self.STATUS_DISPUTED
            self.save(update_fields=["escrow_status", "disputed_at", "status"])

    # -----------------------------
    # Cancellation transitions
    # -----------------------------
    def cancel_by_buyer(self):
        if self.status in (self.STATUS_COMPLETED, self.STATUS_REFUNDED):
            return
        self.status = self.STATUS_CANCELLED_BY_BUYER
        self.cancelled_at = self.cancelled_at or timezone.now()
        self.save(update_fields=["status", "cancelled_at"])

    def cancel_by_seller(self):
        if self.status in (self.STATUS_COMPLETED, self.STATUS_REFUNDED):
            return
        self.status = self.STATUS_CANCELLED_BY_SELLER
        self.cancelled_at = self.cancelled_at or timezone.now()
        self.save(update_fields=["status", "cancelled_at"])

    def cancel_by_admin(self):
        if self.status in (self.STATUS_COMPLETED, self.STATUS_REFUNDED):
            return
        self.status = self.STATUS_CANCELLED_BY_ADMIN
        self.cancelled_at = self.cancelled_at or timezone.now()
        self.save(update_fields=["status", "cancelled_at"])

    # -----------------------------
    # Factory
    # -----------------------------
    @classmethod
    def create_from_cart(
        cls,
        cart,
        address,
        shipping_method,
        *,
        order_type=None,
        shipping_cost=None,
        shipping_days_min=None,
        shipping_days_max=None,
    ):
        if order_type is None:
            order_type = cls.TYPE_STANDARD

        if shipping_cost is None:
            shipping_cost = Decimal("0.00")

        order = cls.objects.create(
            buyer=cart.user,
            address=address,
            shipping_method=shipping_method,
            order_type=order_type,
            status=cls.STATUS_CREATED,
            payment_status=cls.PAYMENT_PENDING,
            shipping_status=cls.SHIPPING_PENDING,
            escrow_status=cls.ESCROW_PENDING,
        )

        subtotal = Decimal("0.00")

        for cart_item in cart.items.select_related("product").all():
            price = cart_item.product.price or Decimal("0.00")

            # qty=1 policy in cart => order_item.quantity = 1
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=1,
                price=price,
            )
            subtotal += price

        buyer_protection_fee = _pct(subtotal, order.buyer_protection_percent)
        seller_commission = _pct(subtotal, order.seller_commission_percent)

        total = subtotal + buyer_protection_fee + shipping_cost

        order.subtotal = subtotal
        order.buyer_protection_fee_amount = buyer_protection_fee
        order.shipping_cost = shipping_cost
        order.seller_commission_amount = seller_commission
        order.total = total

        order.shipping_days_min = shipping_days_min or 0
        order.shipping_days_max = shipping_days_max or 0

        # după ce s-a creat comanda, practic e în așteptare plată
        order.status = cls.STATUS_AWAITING_PAYMENT

        order.save(
            update_fields=[
                "subtotal",
                "buyer_protection_fee_amount",
                "shipping_cost",
                "seller_commission_amount",
                "total",
                "shipping_days_min",
                "shipping_days_max",
                "status",
            ]
        )

        cart.items.all().delete()
        return order


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity}×{self.product.title} (Comanda #{self.order.pk})"


class ReturnRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_PENDING, "În așteptare"),
        (STATUS_APPROVED, "Aprobat"),
        (STATUS_REJECTED, "Respins"),
        (STATUS_REFUNDED, "Rambursat"),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="return_requests",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_requests",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retur #{self.pk} pentru comanda #{self.order_id}"
