# invoices/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models


class Invoice(models.Model):
    class Type(models.TextChoices):
        PRODUCT = "product", "Produs"
        SHIPPING = "shipping", "Transport"
        COMMISSION = "commission", "Comision platformă"
        RETURN = "return", "Retur"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Emisă"
        CANCELLED = "cancelled", "Anulată"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Număr factură (ex: SNB-2025-000123).",
    )

    invoice_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        db_index=True,
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="buyer_invoices",
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="seller_invoices",
        null=True,
        blank=True,
        help_text="Vânzătorul principal pentru această factură (dacă e cazul).",
    )

    currency = models.CharField(
        max_length=10,
        default="RON",
    )

    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Baza de calcul (fără TVA).",
    )

    vat_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("19.00"),
        help_text="TVA în procente (ex: 19.00).",
    )

    vat_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Valoare TVA.",
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total cu TVA.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ISSUED,
        db_index=True,
    )

    issued_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data/ora emiterii facturii.",
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/ora plății facturii (dacă urmărim separat).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["invoice_type"]),
        ]

    def __str__(self) -> str:
        return f"Factura {self.invoice_number or self.pk} – {self.total_amount} {self.currency}"

    def save(self, *args, **kwargs):
        """
        Dacă nu are încă număr de factură, generăm unul simplu:
        SNB-YYYYMMDD-<id>
        """
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.invoice_number:
            from django.utils import timezone

            today = timezone.now().strftime("%Y%m%d")
            self.invoice_number = f"SNB-{today}-{self.pk:06d}"
            super().save(update_fields=["invoice_number"])

    @property
    def is_paid(self) -> bool:
        return self.paid_at is not None
