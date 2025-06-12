from django.db import models
from django.conf import settings
from orders.models import Order
from django.urls import reverse

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending',  'În așteptare'),
        ('paid',     'Plătit'),
        ('failed',   'Eșuat'),
        ('refunded', 'Rambursat'),
    ]

    METHOD_CHOICES = [
        ('stripe',   'Stripe'),
        ('platiro',  'Plati.ro'),
        ('manual',   'Transfer bancar'),
    ]

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='payment'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='manual')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processor_payment_id = models.CharField(max_length=128, blank=True, null=True)
    redirect_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Plată #{self.pk} – {self.get_status_display()} – {self.amount} RON"

    def get_absolute_url(self):
        return reverse('payments:payment_detail', args=[self.pk])
