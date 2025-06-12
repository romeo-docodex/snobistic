from django.db import models
from django.conf import settings
from products.models import Product
from django.urls import reverse

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',   'În așteptare'),
        ('paid',      'Plătită'),
        ('shipped',   'Expediată'),
        ('delivered', 'Livrată'),
        ('cancelled', 'Anulată'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.TextField()
    billing_address = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comandă #{self.pk} – {self.user.email}"

    def is_returnable(self):
        return self.status == 'delivered'

    def get_absolute_url(self):
        return reverse('orders:order_detail', args=[self.pk])


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # la momentul cumpărării

    def __str__(self):
        name = self.product.name if self.product else "(Produs șters)"
        return f"{name} × {self.quantity}"

    def subtotal(self):
        return self.quantity * self.price


class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Solicitat'),
        ('approved',  'Aprobat'),
        ('rejected',  'Respins'),
    ]

    order_item = models.OneToOneField(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='return_request'
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='requested'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        prod = self.order_item.product
        name = prod.name if prod else "(Produs șters)"
        return f"Retur {name} – {self.get_status_display()}"
