from decimal import Decimal
from django.db import models
from django.conf import settings
from django.db.models import Q
from catalog.models import Product


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Discount în procente (ex: 10 pentru 10%)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class Cart(models.Model):
    # Either owned by a user OR a session
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
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
                fields=['session_key'],
                condition=Q(session_key__isnull=False),
                name='uniq_cart_per_session',
            )
        ]

    def __str__(self):
        who = getattr(self.user, 'email', None) or self.session_key or 'unknown'
        return f"Cart<{who}>"

    def get_subtotal(self):
        return sum(item.get_cost() for item in self.items.all())

    def get_total_price(self):
        subtotal = self.get_subtotal()
        if self.coupon and self.coupon.is_active:
            discount_amount = subtotal * (self.coupon.discount / Decimal('100'))
            return subtotal - discount_amount
        return subtotal


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        related_name='items',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.quantity}× {self.product.title}"

    def get_cost(self):
        # aici folosim prețul de pe produs; dacă vei introduce sale_price sau final_price(),
        # e suficient să înlocuiești cu product.final_price()
        return self.product.price * self.quantity
