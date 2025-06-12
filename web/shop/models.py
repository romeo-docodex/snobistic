# shop/models.py
from django.db import models
from django.conf import settings
from products.models import Product

class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']
        verbose_name = "Favorite"
        verbose_name_plural = "Favorite"

    def __str__(self):
        return f"{self.user.email} ❤️ {self.product.name}"


class ProductAuthenticationRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='auth_requests'
    )
    email = models.EmailField(
        help_text="Dacă nu ești logat, lasă aici emailul la care primești certificatul"
    )
    image = models.ImageField(
        upload_to='auth_requests/',
        help_text="Încarcă o poză clară a produsului"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    processed = models.BooleanField(default=False)
    certificate_url = models.URLField(
        blank=True, null=True,
        help_text="Link către certificatul digital (populat după procesare)"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Cerere autentificare produs"
        verbose_name_plural = "Cereri autentificare produse"

    def __str__(self):
        who = self.user.email if self.user else self.email
        return f"AuthReq #{self.pk} by {who}"
