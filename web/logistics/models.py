# logistics/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models


class Courier(models.Model):
    """
    Poți avea mai mulți curieri (FAN, Sameday etc.),
    dar în setup-ul cu Curiera, de obicei vei avea un singur row: 'Curiera'.
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    tracking_url_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Ex: https://tracking.couriera.ro/{tracking_number}",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_tracking_url(self, tracking_number: str) -> str:
        if self.tracking_url_template and tracking_number:
            return self.tracking_url_template.replace(
                "{tracking_number}", tracking_number
            )
        return ""


class ShippingRate(models.Model):
    """
    Poți păstra tarifele interne, dar pentru Curiera, de obicei costul
    vine din API-ul lor. Modelul rămâne pentru viitor/extinderi.
    """
    courier = models.ForeignKey(
        Courier,
        on_delete=models.CASCADE,
        related_name="rates",
    )
    name = models.CharField(
        max_length=100,
        help_text="Ex: Național standard, Easybox, Local etc.",
    )
    min_weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    max_weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    # NOI – durată estimată pentru acest serviciu
    delivery_days_min = models.PositiveSmallIntegerField(
        default=1,
        help_text="Număr minim de zile estimat de livrare pentru acest serviciu."
    )
    delivery_days_max = models.PositiveSmallIntegerField(
        default=3,
        help_text="Număr maxim de zile estimat de livrare pentru acest serviciu."
    )

    currency = models.CharField(max_length=10, default="RON")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["courier__name", "base_price"]

    def __str__(self):
        return f"{self.courier.name} – {self.name} ({self.base_price} {self.currency})"


class Shipment(models.Model):
    """
    AWB / expediție legată de o comandă.
    MVP: 1 comandă = 1 shipment.
    Integrarea cu Curiera se face prin câmpurile external_id, tracking_url, label_url etc.
    """

    class Provider(models.TextChoices):
        CURIERA = "curiera", "Curiera"
        MANUAL = "manual", "Introducere manuală"

    class Status(models.TextChoices):
        PENDING = "pending", "În pregătire"
        LABEL_GENERATED = "label_generated", "AWB generat"
        HANDED_TO_COURIER = "handed", "Predat curierului"
        IN_TRANSIT = "in_transit", "În tranzit"
        DELIVERED = "delivered", "Livrat"
        RETURNED = "returned", "Returnat"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="shipment",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shipments",
        help_text="Sellerul care trimite coletul.",
    )

    # Curierul agregator (în cazul nostru: Curiera)
    courier = models.ForeignKey(
        Courier,
        on_delete=models.PROTECT,
        related_name="shipments",
    )

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.CURIERA,
        db_index=True,
        help_text="De unde vine AWB-ul (Curiera sau manual).",
    )

    # Date AWB
    tracking_number = models.CharField(
        max_length=100,
        help_text="Numărul AWB (de la Curiera).",
    )

    external_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID-ul expedierii în API-ul Curiera.",
    )

    tracking_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Link de tracking direct (dacă Curiera oferă unul).",
    )

    label_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL către PDF AWB (dacă este hosted la Curiera).",
    )

    # Opțiuni de livrare
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="Greutate estimată colet (pentru tarife Curiera).",
    )
    service_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Ex: Standard, Easybox, SameDay etc. – cum le mapezi din Curiera.",
    )

    cash_on_delivery = models.BooleanField(
        default=False,
        help_text="Dacă se folosește ramburs (COD).",
    )
    cod_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Valoare ramburs (dacă cash_on_delivery=True).",
    )

    # Fișiere uploadate local (poze + AWB PDF dacă îl salvezi)
    label_pdf = models.FileField(
        upload_to="awb_labels/",
        blank=True,
        help_text="PDF AWB salvat local (dacă alegi să îl descarci și să îl salvezi).",
    )
    package_photo = models.ImageField(
        upload_to="shipments/package/",
        blank=True,
        help_text="Poză articol.",
    )
    parcel_photo = models.ImageField(
        upload_to="shipments/parcel/",
        blank=True,
        help_text="Poză colet închis.",
    )

    # Statusuri & timestamps
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LABEL_GENERATED,
        db_index=True,
    )

    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Când a fost predat curierului.",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Când a fost livrat.",
    )

    last_update = models.DateTimeField(
        auto_now=True,
        help_text="Ultima actualizare de status.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AWB {self.tracking_number} – Comanda #{self.order_id}"

    @property
    def effective_tracking_url(self) -> str:
        """
        Dacă ai un tracking_url direct de la Curiera, îl folosești.
        Altfel, cazi înapoi la Courier.tracking_url_template.
        """
        if self.tracking_url:
            return self.tracking_url
        return self.courier.get_tracking_url(self.tracking_number)
