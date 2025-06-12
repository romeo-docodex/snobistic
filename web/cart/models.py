from django.db import models
from django.conf import settings
from products.models import Product


class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='cart_items'
    )
    session_key = models.CharField(
        max_length=40, null=True, blank=True, db_index=True
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('user', 'product'),
            ('session_key', 'product'),
        ]
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['user']),
        ]
        ordering = ['-added_at']

    def __str__(self):
        who = self.user.email if self.user else f"Anonim ({self.session_key})"
        return f"{who}: {self.product.name} x {self.quantity}"

    def subtotal(self):
        return self.product.price * self.quantity
