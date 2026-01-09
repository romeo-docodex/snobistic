# cart/models.py
from __future__ import annotations

from decimal import Decimal
from typing import Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from catalog.models import Product


class Coupon(models.Model):
    """
    ✅ Robust coupon model:
    - code: normalized + case-insensitive uniqueness (DB + clean)
    - discount: 0..100 validators
    - expiry: optional (valid_from / expires_at)
    - usage limit: optional (usage_limit, used_count)
    - min order: optional (min_order_amount)
    - max discount: optional (max_discount_amount)
    """
    code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Cod promoțional (se salvează normalizat: UPPER, fără spații).",
    )

    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Discount în procente (ex: 10 pentru 10%). Interval permis: 0–100.",
    )

    is_active = models.BooleanField(default=True)

    # Optional validity window
    valid_from = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Usage limits (global)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Limită globală de utilizări.")
    used_count = models.PositiveIntegerField(default=0, help_text="Număr utilizări consumate (global).")

    # Order constraints
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Subtotal minim (fără shipping/fees) pentru a aplica cuponul.",
    )

    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Plafon maxim pentru suma discount-ului (RON).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # ✅ Guarantee case-insensitive uniqueness at DB level
            models.UniqueConstraint(Lower("code"), name="uniq_coupon_code_ci"),
        ]

    def __str__(self):
        return self.code

    @staticmethod
    def normalize_code(code: str) -> str:
        return (code or "").strip().upper()

    def clean(self):
        super().clean()

        self.code = self.normalize_code(self.code)

        if self.discount is None:
            raise ValidationError({"discount": "Discount-ul este obligatoriu."})

        # Defensive clamp validation (in addition to field validators)
        try:
            d = Decimal(self.discount)
        except Exception:
            raise ValidationError({"discount": "Discount invalid."})

        if d < Decimal("0.00") or d > Decimal("100.00"):
            raise ValidationError({"discount": "Discount-ul trebuie să fie între 0 și 100."})

        if self.valid_from and self.expires_at and self.expires_at <= self.valid_from:
            raise ValidationError({"expires_at": "Data de expirare trebuie să fie după valid_from."})

        if self.usage_limit is not None and int(self.usage_limit) == 0:
            raise ValidationError({"usage_limit": "usage_limit nu poate fi 0 (lasă gol pentru nelimitat)."})

        # ✅ App-level CI uniqueness (works even if DB backend is limited)
        qs = Coupon.objects.filter(code__iexact=self.code)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError({"code": "Există deja un cupon cu acest cod (case-insensitive)."})

    def save(self, *args, **kwargs):
        self.code = self.normalize_code(self.code)

        # make clean() effective even outside ModelForms
        self.full_clean()

        super().save(*args, **kwargs)

    # -----------------------------
    # Validations & application
    # -----------------------------
    def is_currently_valid(self) -> Tuple[bool, str | None]:
        if not self.is_active:
            return False, "Cupon inactiv."
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False, "Cuponul nu este încă activ."
        if self.expires_at and now >= self.expires_at:
            return False, "Cupon expirat."
        if self.usage_limit is not None and int(self.used_count or 0) >= int(self.usage_limit):
            return False, "Cuponul a atins limita de utilizări."
        return True, None

    def validate_for_cart(self, cart: "Cart") -> Tuple[bool, str | None]:
        ok, msg = self.is_currently_valid()
        if not ok:
            return False, msg

        subtotal = Decimal(cart.get_subtotal() or 0)

        if self.min_order_amount is not None:
            if subtotal < Decimal(self.min_order_amount):
                return False, "Subtotal prea mic pentru acest cupon."

        # If subtotal is 0 -> no point
        if subtotal <= Decimal("0.00"):
            return False, "Cuponul nu poate fi aplicat pe un coș gol."

        return True, None

    def compute_discount_amount(self, subtotal: Decimal) -> Decimal:
        subtotal = Decimal(subtotal or 0)
        if subtotal <= Decimal("0.00"):
            return Decimal("0.00")

        ok, _ = self.is_currently_valid()
        if not ok:
            return Decimal("0.00")

        pct = (Decimal(self.discount) / Decimal("100.00"))
        discount_amount = (subtotal * pct).quantize(Decimal("0.01"))

        if self.max_discount_amount is not None:
            cap = Decimal(self.max_discount_amount)
            if cap >= Decimal("0.00"):
                discount_amount = min(discount_amount, cap)

        # never exceed subtotal
        discount_amount = min(discount_amount, subtotal)
        if discount_amount < Decimal("0.00"):
            discount_amount = Decimal("0.00")
        return discount_amount

    def consume_one(self) -> None:
        """
        ✅ Atomic consume (usage_limit-safe).
        Called when an Order is created successfully.
        """
        with transaction.atomic():
            c = Coupon.objects.select_for_update().get(pk=self.pk)

            ok, msg = c.is_currently_valid()
            if not ok:
                raise ValueError(msg or "Cupon invalid.")

            c.used_count = int(c.used_count or 0) + 1

            # enforce limit after increment
            if c.usage_limit is not None and c.used_count > int(c.usage_limit):
                raise ValueError("Cuponul a atins limita de utilizări.")

            c.save(update_fields=["used_count"])


class Cart(models.Model):
    # Either owned by a user OR a session
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True,
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
    )

    coupon = models.ForeignKey(
        Coupon,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=Q(session_key__isnull=False),
                name="uniq_cart_per_session",
            )
        ]

    def __str__(self):
        who = getattr(self.user, "email", None) or self.session_key or "unknown"
        return f"Cart<{who}>"

    def get_subtotal(self) -> Decimal:
        # qty=1 policy: subtotal = sum(product.price)
        total = Decimal("0.00")
        for item in self.items.select_related("product").all():
            total += (item.product.price or Decimal("0.00"))
        return total

    def get_discount_amount(self) -> Decimal:
        subtotal = self.get_subtotal()
        if not self.coupon:
            return Decimal("0.00")

        ok, _ = self.coupon.validate_for_cart(self)
        if not ok:
            return Decimal("0.00")

        return self.coupon.compute_discount_amount(subtotal)

    def get_total_price(self) -> Decimal:
        subtotal = self.get_subtotal()
        discount_amount = self.get_discount_amount()
        total = subtotal - discount_amount
        if total < Decimal("0.00"):
            total = Decimal("0.00")
        return total


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        related_name="items",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_cartitem_cart_product"),
        ]

    def __str__(self):
        return f"{self.product.title}"

    def get_cost(self) -> Decimal:
        """
        Backwards-compat helper (în caz că mai există template-uri vechi):
        qty=1 => cost == product.price
        """
        return (self.product.price or Decimal("0.00"))
