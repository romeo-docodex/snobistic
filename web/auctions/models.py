# auctions/models.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

User = settings.AUTH_USER_MODEL


def _q2(x: Decimal) -> Decimal:
    """Quantize to 0.01 with rounding up (safe for bid thresholds)."""
    if x is None:
        return x
    return x.quantize(Decimal("0.01"), rounding=ROUND_UP)


class AuctionQuerySet(models.QuerySet):
    def due_to_expire(self):
        now = timezone.now()
        return self.filter(status=Auction.Status.ACTIVE, end_time__lte=now)

    def active(self):
        now = timezone.now()
        return self.filter(
            status=Auction.Status.ACTIVE,
            start_time__lte=now,
            end_time__gt=now,
        )

    def upcoming(self):
        now = timezone.now()
        return self.filter(status=Auction.Status.PENDING, start_time__gt=now)

    def ended(self):
        return self.filter(status=Auction.Status.ENDED)


class Auction(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "În așteptare"
        ACTIVE = "ACTIVE", "Activă"
        ENDED = "ENDED", "Încheiată"
        CANCELED = "CANCELED", "Anulată"

    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="auction",
        help_text="Produsul scos la licitație",
    )
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_auctions"
    )

    # Prices
    start_price = models.DecimalField(max_digits=10, decimal_places=2)

    # keep nullable for smooth migrations / legacy rows
    reserve_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rezervă (preț minim acceptat)",
    )

    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Prețul curent (ultimul bid / start_price inițial).",
    )

    # Time window
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(blank=True, null=True)
    duration_days = models.PositiveIntegerField(default=7)

    # Rules
    min_increment_percent = models.PositiveIntegerField(default=10)
    payment_window_hours = models.PositiveIntegerField(default=48)

    # Status / settlement
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    canceled_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    winner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="won_auctions",
    )
    winning_bid = models.OneToOneField(
        "auctions.Bid",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="as_winning_bid",
    )
    payment_due_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AuctionQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                name="auction_reserve_gte_start_or_null",
                check=Q(reserve_price__isnull=True)
                | Q(reserve_price__gte=models.F("start_price")),
            )
        ]

    def clean(self):
        errors = {}

        # ✅ creator must own product (hard business rule)
        if self.product_id and self.creator_id:
            try:
                if getattr(self.product, "owner_id", None) != self.creator_id:
                    errors["creator"] = (
                        "Creatorul licitației trebuie să fie proprietarul produsului."
                    )
            except Exception:
                pass

        if self.reserve_price is not None and self.start_price is not None:
            if self.reserve_price < self.start_price:
                errors["reserve_price"] = "Rezerva trebuie să fie ≥ prețul de pornire."
        if self.min_increment_percent is not None and self.min_increment_percent <= 0:
            errors["min_increment_percent"] = "Incrementul minim trebuie să fie > 0."
        if self.duration_days is not None and self.duration_days <= 0:
            errors["duration_days"] = "Durata trebuie să fie >= 1 zi."
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "Data de sfârșit trebuie să fie după data de start."
        if errors:
            raise ValidationError(errors)

    @property
    def effective_reserve_price(self) -> Decimal:
        return (
            _q2(self.reserve_price)
            if self.reserve_price is not None
            else _q2(self.start_price)
        )

    def _desired_end_time(self):
        if not self.start_time or not self.duration_days:
            return None
        return self.start_time + timedelta(days=int(self.duration_days))

    def save(self, *args, **kwargs):
        # Quantize prices
        if self.start_price is not None:
            self.start_price = _q2(self.start_price)
        if self.reserve_price is not None:
            self.reserve_price = _q2(self.reserve_price)
        if self.current_price is not None:
            self.current_price = _q2(self.current_price)

        # Initialize current_price on create if missing/zero
        if (
            (self.current_price is None or self.current_price == Decimal("0.00"))
            and self.start_price is not None
        ):
            self.current_price = _q2(self.start_price)

        # Compute/recompute end_time:
        # - if missing -> compute
        # - if PENDING -> always keep consistent with start_time + duration_days
        desired = self._desired_end_time()
        if desired is not None:
            if self.end_time is None or self.status == self.Status.PENDING:
                self.end_time = desired

        super().save(*args, **kwargs)

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return (
            self.status == self.Status.ACTIVE
            and self.start_time <= now
            and (self.end_time is None or self.end_time > now)
        )

    def time_left(self):
        if not self.end_time:
            return None
        return max(self.end_time - timezone.now(), timedelta())

    def min_next_bid(self) -> Decimal:
        base = _q2(self.current_price or self.start_price)
        inc = _q2((base * Decimal(self.min_increment_percent)) / Decimal("100"))
        if inc < Decimal("0.01"):
            inc = Decimal("0.01")
        return _q2(base + inc)

    def highest_bid(self):
        return self.bids.order_by("-amount", "-placed_at").first()

    def activate(self):
        """
        Move to ACTIVE. Sync Product fields for catalog consistency.
        """
        if self.status != self.Status.PENDING:
            return

        # hard rule
        if getattr(self.product, "owner_id", None) != self.creator_id:
            raise ValidationError(
                "Nu poți activa o licitație pe un produs care nu îți aparține."
            )

        now = timezone.now()
        if not self.start_time:
            self.start_time = now

        if self.reserve_price is None:
            self.reserve_price = self.start_price

        self.status = self.Status.ACTIVE
        self.current_price = _q2(self.start_price)
        self.save(
            update_fields=[
                "start_time",
                "end_time",
                "status",
                "current_price",
                "reserve_price",
                "updated_at",
            ]
        )

        # Sync Product (sale_type + auction fields)
        product = self.product
        product.sale_type = "AUCTION"
        product.price = self.start_price

        product.auction_start_price = self.start_price
        product.auction_reserve_price = self.reserve_price
        product.auction_end_at = self.end_time

        product.save(
            update_fields=[
                "sale_type",
                "price",
                "auction_start_price",
                "auction_reserve_price",
                "auction_end_at",
            ]
        )

    def cancel(self, *, by_user=None):
        if self.status in (self.Status.ENDED, self.Status.CANCELED):
            return
        self.status = self.Status.CANCELED
        self.canceled_at = timezone.now()
        self.save(update_fields=["status", "canceled_at", "updated_at"])

    def settle_if_needed(self):
        if self.status != self.Status.ACTIVE:
            return
        if self.end_time and self.end_time > timezone.now():
            return
        self._end_and_settle()

    def _end_and_settle(self):
        if self.status != self.Status.ACTIVE:
            return

        self.status = self.Status.ENDED
        self.ended_at = timezone.now()

        top = self.highest_bid()
        reserve = self.effective_reserve_price

        if top and top.amount >= reserve:
            self.winner = top.user
            self.winning_bid = top
            self.current_price = _q2(top.amount)
            self.payment_due_at = timezone.now() + timedelta(
                hours=int(self.payment_window_hours)
            )
        else:
            self.winner = None
            self.winning_bid = None
            self.payment_due_at = None

        self.save(
            update_fields=[
                "status",
                "ended_at",
                "winner",
                "winning_bid",
                "current_price",
                "payment_due_at",
                "updated_at",
            ]
        )

        if self.winner and self.winning_bid:
            AuctionOrder.objects.get_or_create(
                auction=self,
                defaults={
                    "buyer": self.winner,
                    "amount": self.winning_bid.amount,
                    "status": AuctionOrder.Status.PENDING_PAYMENT,
                    "payment_due_at": self.payment_due_at,
                },
            )

    def place_bid(self, *, user, amount: Decimal) -> "Bid":
        """
        Atomic bid placement:
        - locks auction row
        - checks status/time
        - enforces min increment
        - updates current_price
        """
        amount = _q2(Decimal(amount))

        if amount <= 0:
            raise ValidationError("Oferta trebuie să fie > 0.")

        with transaction.atomic():
            locked = (
                Auction.objects.select_for_update()
                .select_related("product")
                .get(pk=self.pk)
            )

            # anti self-bid (seller/owner)
            if user and (
                getattr(user, "id", None) == locked.creator_id
                or getattr(user, "id", None) == getattr(locked.product, "owner_id", None)
            ):
                raise ValidationError("Nu poți licita la propria ta licitație.")

            locked.settle_if_needed()
            locked.refresh_from_db()

            if locked.status != locked.Status.ACTIVE:
                raise ValidationError("Licitația nu este activă.")

            now = timezone.now()
            if locked.start_time and locked.start_time > now:
                raise ValidationError("Licitația nu a început încă.")
            if locked.end_time and locked.end_time <= now:
                locked.settle_if_needed()
                raise ValidationError("Licitația este încheiată.")

            min_allowed = locked.min_next_bid()
            if amount < min_allowed:
                raise ValidationError(f"Oferta trebuie să fie ≥ {min_allowed} RON.")

            bid = Bid.objects.create(auction=locked, user=user, amount=amount)
            locked.current_price = amount
            locked.save(update_fields=["current_price", "updated_at"])
            return bid

    def __str__(self):
        return f"Auction #{self.pk} — {getattr(self.product, 'title', 'Produs')}"


class AuctionImage(models.Model):
    auction = models.ForeignKey(
        "auctions.Auction", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="auctions/images/")
    created_at = models.DateTimeField(
        default=timezone.now, editable=False, db_index=True
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Imagine licitație #{self.auction_id}"


class Bid(models.Model):
    auction = models.ForeignKey(
        "auctions.Auction", on_delete=models.CASCADE, related_name="bids"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-placed_at"]
        indexes = [
            models.Index(fields=["auction", "-amount", "-placed_at"]),
            models.Index(fields=["user", "-placed_at"]),
        ]

    def __str__(self):
        return f"{self.user} → {self.amount} RON (Auction #{self.auction_id})"


class AuctionOrder(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "În așteptare plată"
        PAID = "PAID", "Plătită"
        EXPIRED = "EXPIRED", "Expirată"
        CANCELED = "CANCELED", "Anulată"

    auction = models.OneToOneField(
        "auctions.Auction", on_delete=models.CASCADE, related_name="order"
    )
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auction_orders")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT
    )
    payment_due_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    canceled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def is_payment_overdue(self) -> bool:
        if self.status != self.Status.PENDING_PAYMENT or not self.payment_due_at:
            return False
        return timezone.now() > self.payment_due_at

    def __str__(self):
        return f"Order Auction #{self.auction_id} — {self.buyer} — {self.amount} RON"


class AuctionReturnRequest(models.Model):
    RETURN_WINDOW_DAYS = 3

    class Reason(models.TextChoices):
        NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED", "Produs neconform cu descrierea"

    class Status(models.TextChoices):
        PENDING = "PENDING", "În analiză"
        APPROVED = "APPROVED", "Aprobat"
        REJECTED = "REJECTED", "Respins"
        CLOSED = "CLOSED", "Închis"

    order = models.ForeignKey(
        "auctions.AuctionOrder",
        on_delete=models.CASCADE,
        related_name="return_requests",
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    details = models.TextField(blank=True)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(blank=True, null=True)

    def clean(self):
        if self.order_id and self.order.created_at:
            deadline = self.order.created_at + timedelta(days=self.RETURN_WINDOW_DAYS)
            if timezone.now() > deadline:
                raise ValidationError(
                    "Perioada de retur pentru licitații (3 zile) a expirat."
                )
        if self.reason != self.Reason.NOT_AS_DESCRIBED:
            raise ValidationError(
                "Returul este permis doar pentru produse neconforme cu descrierea."
            )

    def __str__(self):
        return f"Return #{self.pk} — Order #{self.order_id}"
