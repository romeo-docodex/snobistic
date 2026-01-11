# invoices/models.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


MONEY_Q = Decimal("0.01")


def money(x: Decimal) -> Decimal:
    if x is None:
        return Decimal("0.00")
    if not isinstance(x, Decimal):
        x = Decimal(str(x))
    return x.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _full_name_or_email(u) -> str:
    if not u:
        return ""
    try:
        name = (u.get_full_name() or "").strip()
    except Exception:
        name = ""
    return name or getattr(u, "email", "") or str(getattr(u, "pk", ""))


class Invoice(models.Model):
    """
    Workflow:
      - Draft: se poate edita (linii, snapshot se completează), NU are issued_at obligatoriu.
      - Issued: issued_at setat explicit la emitere; linii blocate.
      - Cancelled: marcaj intern; în practică storno/credit note e documentul contabil de corecție.
    """

    class Type(models.TextChoices):
        PRODUCT = "product", "Produs"
        SHIPPING = "shipping", "Transport"
        COMMISSION = "commission", "Comision platformă"
        RETURN = "return", "Retur"  # recomandat: mapat la CREDIT NOTE când e corecție

    class Document(models.TextChoices):
        INVOICE = "invoice", "Factura"
        CREDIT_NOTE = "credit_note", "Storno / Credit note"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Emisă"
        CANCELLED = "cancelled", "Anulată"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    # număr factură: generat la emitere (NU la creare)
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="Număr document (ex: SNB-20250111-000123). Se generează la emitere.",
    )

    document_type = models.CharField(
        max_length=20,
        choices=Document.choices,
        default=Document.INVOICE,
        db_index=True,
    )

    # dacă e CREDIT_NOTE => indică factura inițială
    original_invoice = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_notes",
        help_text="Factura inițială (doar pentru storno/credit note).",
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

    currency = models.CharField(max_length=10, default="RON")

    # totaluri derivate din linii
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("19.00"))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # ✅ IMPORTANT: issued_at NU e auto_now_add; îl setăm la emitere
    issued_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/ora emiterii (setată la emitere, nu la creare).",
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    # anulare
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_invoices",
    )
    cancel_reason = models.TextField(blank=True, default="")

    # =========================
    # SNAPSHOT FISCAL
    # =========================
    issuer_name = models.CharField(max_length=255, null=True, blank=True)
    issuer_vat = models.CharField(max_length=64, null=True, blank=True)
    issuer_reg_no = models.CharField(max_length=64, null=True, blank=True)
    issuer_address = models.CharField(max_length=255, null=True, blank=True)
    issuer_city = models.CharField(max_length=120, null=True, blank=True)
    issuer_country = models.CharField(max_length=120, null=True, blank=True, default="RO")
    issuer_iban = models.CharField(max_length=64, null=True, blank=True)
    issuer_bank = models.CharField(max_length=120, null=True, blank=True)
    issuer_email = models.EmailField(null=True, blank=True)
    issuer_phone = models.CharField(max_length=40, null=True, blank=True)

    bill_to_name = models.CharField(max_length=255, null=True, blank=True)
    bill_to_email = models.EmailField(null=True, blank=True)
    bill_to_vat = models.CharField(max_length=64, null=True, blank=True)
    bill_to_reg_no = models.CharField(max_length=64, null=True, blank=True)
    bill_to_address = models.CharField(max_length=255, null=True, blank=True)
    bill_to_city = models.CharField(max_length=120, null=True, blank=True)
    bill_to_country = models.CharField(max_length=120, null=True, blank=True, default="RO")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at", "-created_at"]
        indexes = [
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["invoice_type"]),
            models.Index(fields=["document_type"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        num = self.invoice_number or f"#{self.pk}"
        return f"{self.get_document_type_display()} {num} – {self.total_amount} {self.currency}"

    # -------------------------
    # Snapshot helpers
    # -------------------------
    def _platform_defaults(self) -> dict:
        return {
            "issuer_name": getattr(settings, "SNOBISTIC_COMPANY_NAME", "Snobistic Platform"),
            "issuer_vat": getattr(settings, "SNOBISTIC_COMPANY_VAT", "RO00000000"),
            "issuer_reg_no": getattr(settings, "SNOBISTIC_COMPANY_REG_NO", ""),
            "issuer_address": getattr(settings, "SNOBISTIC_COMPANY_ADDRESS", ""),
            "issuer_city": getattr(settings, "SNOBISTIC_COMPANY_CITY", ""),
            "issuer_country": getattr(settings, "SNOBISTIC_COMPANY_COUNTRY", "RO"),
            "issuer_iban": getattr(settings, "SNOBISTIC_COMPANY_IBAN", ""),
            "issuer_bank": getattr(settings, "SNOBISTIC_COMPANY_BANK", ""),
            "issuer_email": getattr(settings, "SNOBISTIC_COMPANY_EMAIL", ""),
            "issuer_phone": getattr(settings, "SNOBISTIC_COMPANY_PHONE", ""),
        }

    def _snapshot_from_user(self, user) -> dict:
        return {
            "name": _full_name_or_email(user),
            "email": getattr(user, "email", "") if user else "",
            "vat": "",
            "reg_no": "",
            "address": "",
            "city": "",
            "country": "RO",
        }

    def ensure_snapshot(self):
        """
        Îngheață datele (dacă lipsesc). Nu rescrie dacă există deja.
        """
        platform = self._platform_defaults()

        use_seller_as_issuer = (self.invoice_type == self.Type.PRODUCT) and bool(self.seller_id)

        if use_seller_as_issuer and not self.issuer_name:
            s = self._snapshot_from_user(self.seller)
            self.issuer_name = s["name"]
            self.issuer_email = s["email"] or None
            self.issuer_country = s["country"]
        else:
            for k, v in platform.items():
                if getattr(self, k) in (None, ""):
                    setattr(self, k, v or None)

        bill_to_user = self.buyer
        if self.invoice_type == self.Type.COMMISSION and self.seller_id:
            bill_to_user = self.seller

        if not self.bill_to_name:
            b = self._snapshot_from_user(bill_to_user)
            self.bill_to_name = b["name"]
            self.bill_to_email = b["email"] or None
            self.bill_to_country = b["country"]

    # -------------------------
    # Totals from lines
    # -------------------------
    def recalculate_totals_from_lines(self, save: bool = True) -> None:
        agg = self.lines.aggregate(
            net=Sum("net_amount"),
            vat=Sum("vat_amount"),
            total=Sum("total_amount"),
        )
        self.net_amount = money(agg["net"] or Decimal("0.00"))
        self.vat_amount = money(agg["vat"] or Decimal("0.00"))
        self.total_amount = money(agg["total"] or Decimal("0.00"))

        if save:
            Invoice.objects.filter(pk=self.pk).update(
                net_amount=self.net_amount,
                vat_amount=self.vat_amount,
                total_amount=self.total_amount,
            )

    @property
    def has_lines(self) -> bool:
        return self.lines.exists()

    @property
    def is_paid(self) -> bool:
        return self.paid_at is not None

    @property
    def is_credit_note(self) -> bool:
        return self.document_type == self.Document.CREDIT_NOTE

    # -------------------------
    # Workflow
    # -------------------------
    def can_issue(self) -> bool:
        return self.status == self.Status.DRAFT

    def can_cancel(self) -> bool:
        return self.status == self.Status.ISSUED

    def _generate_number(self) -> str:
        stamp = (self.issued_at or timezone.now()).strftime("%Y%m%d")
        return f"SNB-{stamp}-{self.pk:06d}"

    def clean(self):
        # CREDIT_NOTE trebuie să aibă original_invoice
        if self.document_type == self.Document.CREDIT_NOTE and not self.original_invoice_id:
            raise ValidationError({"original_invoice": "Credit note trebuie să aibă factura inițială setată."})

        # ISSUED trebuie să aibă issued_at
        if self.status == self.Status.ISSUED and not self.issued_at:
            raise ValidationError({"issued_at": "Factura emisă trebuie să aibă issued_at setat."})

        # DRAFT nu ar trebui să aibă invoice_number obligatoriu, dar dacă are e OK (ex: import)
        super().clean()

    @transaction.atomic
    def issue(self, by_user=None) -> None:
        """
        DRAFT -> ISSUED:
          - issued_at = now
          - status = ISSUED
          - generează invoice_number dacă lipsește
          - blochează implicit editarea liniilor (prin InvoiceLine.save/delete)
        """
        if not self.can_issue():
            raise ValidationError("Doar facturile DRAFT pot fi emise.")

        if not self.has_lines:
            raise ValidationError("Nu poți emite o factură fără linii (InvoiceLine).")

        self.ensure_snapshot()
        self.issued_at = timezone.now()
        self.status = self.Status.ISSUED

        # persist issued_at/status înainte de număr (ca să avem pk)
        self.save(update_fields=["issued_at", "status", "updated_at"])

        if not self.invoice_number:
            self.invoice_number = self._generate_number()
            self.save(update_fields=["invoice_number", "updated_at"])

        # recalc totals (safe)
        self.recalculate_totals_from_lines(save=True)

    @transaction.atomic
    def cancel(self, by_user=None, reason: str = "") -> None:
        """
        ISSUED -> CANCELLED (marcaj intern).
        În real life, storno/credit note e documentul contabil de corecție.
        """
        if not self.can_cancel():
            raise ValidationError("Doar facturile EMISE pot fi anulate.")

        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancelled_by = by_user if by_user and getattr(by_user, "is_authenticated", False) else None
        self.cancel_reason = (reason or "").strip()

        self.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancel_reason", "updated_at"])

    @transaction.atomic
    def create_credit_note(self, by_user=None, reason: str = "") -> "Invoice":
        """
        Creează un CREDIT NOTE (storno) legat de factura curentă, cu linii inverse (valori negative).
        În mod implicit îl emitem imediat (status ISSUED, issued_at=now).
        """
        if self.status != self.Status.ISSUED:
            raise ValidationError("Poți crea storno doar pentru o factură emisă.")

        # copie snapshot “înghețat” + părți + currency + tip
        cn = Invoice(
            order=self.order,
            invoice_type=self.invoice_type,          # poți seta RETURN dacă vrei semantic distinct
            document_type=self.Document.CREDIT_NOTE,
            original_invoice=self,
            buyer=self.buyer,
            seller=self.seller,
            currency=self.currency,
            status=self.Status.DRAFT,
        )

        # copy snapshot fields (issuer/bill_to)
        snapshot_fields = [
            "issuer_name", "issuer_vat", "issuer_reg_no", "issuer_address", "issuer_city", "issuer_country",
            "issuer_iban", "issuer_bank", "issuer_email", "issuer_phone",
            "bill_to_name", "bill_to_email", "bill_to_vat", "bill_to_reg_no", "bill_to_address", "bill_to_city",
            "bill_to_country",
        ]
        for f in snapshot_fields:
            setattr(cn, f, getattr(self, f))

        cn.save()

        # copy lines reversed (negative unit_net)
        # păstrăm qty pozitiv și unit_net negativ (rezultă net/vat/total negative)
        for i, line in enumerate(self.lines.order_by("position", "id"), start=1):
            cn.lines.create(
                position=i,
                kind=line.kind,
                description=f"STORNO: {line.description}",
                quantity=line.quantity,
                sku=line.sku,
                product_id=line.product_id,
                order_item_id=line.order_item_id,
                currency=line.currency or cn.currency,
                unit_net_amount=money(Decimal("0.00") - (line.unit_net_amount or Decimal("0.00"))),
                vat_percent=line.vat_percent,
            )

        # note intern în reason (opțional)
        if reason:
            cn.cancel_reason = (reason or "").strip()
            cn.save(update_fields=["cancel_reason"])

        # emitere imediată
        cn.issue(by_user=by_user)
        return cn

    def save(self, *args, **kwargs):
        # normalize invoice_number blank -> None
        if self.invoice_number is not None and not str(self.invoice_number).strip():
            self.invoice_number = None

        # snapshot se poate completa și în draft, dar NU rescriem dacă există
        self.ensure_snapshot()

        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    class Kind(models.TextChoices):
        PRODUCT = "product", "Produs"
        SHIPPING = "shipping", "Transport"
        COMMISSION = "commission", "Comision"
        BUYER_PROTECTION = "buyer_protection", "Buyer protection"
        DISCOUNT = "discount", "Discount"
        ADJUSTMENT = "adjustment", "Ajustare"
        OTHER = "other", "Altele"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.CASCADE,
        related_name="lines",
    )

    position = models.PositiveIntegerField(default=1)
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.OTHER, db_index=True)

    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))

    sku = models.CharField(max_length=64, null=True, blank=True)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_lines",
    )
    order_item_id = models.PositiveIntegerField(null=True, blank=True)

    currency = models.CharField(max_length=10, default="RON")

    unit_net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("19.00"))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["invoice", "position"]),
            models.Index(fields=["kind"]),
            models.Index(fields=["product"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "position"], name="uniq_invoice_line_position"),
        ]

    def __str__(self) -> str:
        return f"InvoiceLine #{self.invoice_id}:{self.position} {self.description}"

    def recalc_amounts(self) -> None:
        qty = Decimal(str(self.quantity or Decimal("0.00")))
        unit = Decimal(str(self.unit_net_amount or Decimal("0.00")))
        vat_p = Decimal(str(self.vat_percent or Decimal("0.00")))

        net = money(qty * unit)
        vat = money((net * vat_p) / Decimal("100"))
        total = money(net + vat)

        self.net_amount = net
        self.vat_amount = vat
        self.total_amount = total

    def _assert_editable(self):
        if self.invoice.status != Invoice.Status.DRAFT:
            raise ValidationError("Nu poți modifica linii pe o factură emisă/anulată. Editează doar în DRAFT.")

    def save(self, *args, **kwargs):
        # blocare modificări după emitere
        self._assert_editable()

        if not self.currency:
            self.currency = getattr(self.invoice, "currency", "RON")

        self.recalc_amounts()

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.invoice.recalculate_totals_from_lines(save=True)

    def delete(self, *args, **kwargs):
        self._assert_editable()
        with transaction.atomic():
            inv = self.invoice
            super().delete(*args, **kwargs)
            inv.recalculate_totals_from_lines(save=True)
