# orders/models.py
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property


from accounts.models import Address


def _pct(amount: Decimal, percent: Decimal) -> Decimal:
    """
    Calculează percent (%) din amount, rotunjit la 2 zecimale.
    """
    if amount is None:
        amount = Decimal("0.00")
    return (amount * percent / Decimal("100")).quantize(
        Decimal("0.01",
        ),
        rounding=ROUND_HALF_UP,
    )


class Order(models.Model):
    TYPE_STANDARD = "standard"
    TYPE_AUCTION_WIN = "auction_win"
    TYPE_CHOICES = [
        (TYPE_STANDARD, "Comandă magazin"),
        (TYPE_AUCTION_WIN, "Comandă licitație"),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "În așteptare"),
        (PAYMENT_PAID, "Plătită"),
    ]

    SHIPPING_PENDING = "pending"
    SHIPPING_SHIPPED = "shipped"
    SHIPPING_CANCELLED = "cancelled"
    SHIPPING_STATUS_CHOICES = [
        (SHIPPING_PENDING, "Neexpediată"),
        (SHIPPING_SHIPPED, "Expediată"),
        (SHIPPING_CANCELLED, "Anulată"),
    ]

    ESCROW_PENDING = "pending"
    ESCROW_HELD = "held"
    ESCROW_RELEASED = "released"
    ESCROW_DISPUTED = "disputed"
    ESCROW_STATUS_CHOICES = [
        (ESCROW_PENDING, "În așteptare plată"),
        (ESCROW_HELD, "Fonduri în escrow"),
        (ESCROW_RELEASED, "Escrow eliberat"),
        (ESCROW_DISPUTED, "Escrow în dispută"),
    ]

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

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )
    shipping_status = models.CharField(
        max_length=20,
        choices=SHIPPING_STATUS_CHOICES,
        default=SHIPPING_PENDING,
    )
    escrow_status = models.CharField(
        max_length=20,
        choices=ESCROW_STATUS_CHOICES,
        default=ESCROW_PENDING,
    )

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

    # cost transport
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # NOI – durata estimată de livrare
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comanda #{self.pk} de {self.buyer}"

    # -------------------
    # Config percent
    # -------------------
    @property
    def buyer_protection_percent(self) -> Decimal:
        return Decimal(
            getattr(settings, "SNOBISTIC_BUYER_PROTECTION_PERCENT", "5.0")
        )

    @property
    def seller_commission_percent(self) -> Decimal:
        return Decimal(
            getattr(settings, "SNOBISTIC_SELLER_COMMISSION_PERCENT", "9.0")
        )

    # -------------------
    # Helpers payment/escrow
    # -------------------
    @cached_property
    def latest_payment(self):
        return self.payments.order_by("-created_at").first()

    @property
    def payment_status_label(self) -> str:
        if self.latest_payment:
            return self.latest_payment.get_status_display()
        return self.get_payment_status_display()

    @property
    def escrow_status_label(self) -> str:
        return self.get_escrow_status_display()

    @property
    def has_pending_return(self) -> bool:
        """
        True dacă există cel puțin un ReturnRequest PENDING.
        Folosit pentru a bloca eliberarea escrow-ului.
        """
        return self.return_requests.filter(
            status=ReturnRequest.STATUS_PENDING
        ).exists()

    def get_payment_url(self):
        """
        URL-ul către inițierea plății online (Stripe).
        """
        return reverse("payments:payment_confirm", args=[self.id])

    def mark_as_paid(self):
        """
        Marcată ca plătită după confirmarea procesatorului de plăți.
        În acest moment banii se consideră blocați în escrow.
        """
        self.payment_status = self.PAYMENT_PAID
        self.escrow_status = self.ESCROW_HELD
        self.save(update_fields=["payment_status", "escrow_status"])

    def _payout_sellers_from_escrow(self):
        """
        Distribuie banii net (după comision) din escrow către wallet-urile sellerilor.
        Aici NU se fac verificări de business (retur, dispute) – acestea se fac
        în release_escrow().
        """
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
        """
        Eliberează fondurile din escrow și plătește sellerii în Wallet.

        Reguli standard (force=False):
        - escrow_status trebuie să fie HELD
        - comanda trebuie să fie marcată ca SHIPPED
        - nu trebuie să existe ReturnRequest PENDING

        force=True se poate folosi doar din procese administrative
        foarte controlate (ex: migrare, corecție manuală).
        """
        if self.escrow_status != self.ESCROW_HELD:
            return

        if not force:
            if self.shipping_status != self.SHIPPING_SHIPPED:
                return
            if self.has_pending_return:
                return

        self._payout_sellers_from_escrow()
        self.escrow_status = self.ESCROW_RELEASED
        self.save(update_fields=["escrow_status"])

    def mark_escrow_disputed(self):
        """
        Marchează escrow-ul ca fiind în dispută. Se apelează când există
        retur / dispută deschisă de buyer.
        """
        if self.escrow_status in (self.ESCROW_HELD, self.ESCROW_PENDING):
            self.escrow_status = self.ESCROW_DISPUTED
            self.save(update_fields=["escrow_status"])

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
        """
        Creează o comandă din conținutul `cart`, setează adresa și metoda de transport,
        calculează subtotal, buyer protection, comision, total, apoi golește coșul.

        shipping_cost, shipping_days_min/max vin din calculatorul de logistică.
        """
        if order_type is None:
            order_type = cls.TYPE_STANDARD

        if shipping_cost is None:
            shipping_cost = Decimal("0.00")

        order = cls.objects.create(
            buyer=cart.user,
            address=address,
            shipping_method=shipping_method,
            order_type=order_type,
        )

        subtotal = Decimal("0.00")

        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price=cart_item.product.price,
            )
            subtotal += cart_item.product.price * cart_item.quantity

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

        order.save(
            update_fields=[
                "subtotal",
                "buyer_protection_fee_amount",
                "shipping_cost",
                "seller_commission_amount",
                "total",
                "shipping_days_min",
                "shipping_days_max",
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
    STATUS_CHOICES = [
        (STATUS_PENDING, "În așteptare"),
        (STATUS_APPROVED, "Aprobat"),
        (STATUS_REJECTED, "Respins"),
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
