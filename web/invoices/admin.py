# invoices/admin.py
from django.contrib import admin

from .models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = (
        "position",
        "kind",
        "description",
        "quantity",
        "unit_net_amount",
        "vat_percent",
        "net_amount",
        "vat_amount",
        "total_amount",
        "currency",
        "sku",
        "product",
        "order_item_id",
    )
    readonly_fields = ("net_amount", "vat_amount", "total_amount")
    ordering = ("position", "id")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "order",
        "invoice_type",
        "buyer",
        "seller",
        "total_amount",
        "currency",
        "status",
        "issued_at",
    )
    list_filter = ("invoice_type", "status", "currency", "issued_at")
    search_fields = ("invoice_number", "order__id", "buyer__email", "seller__email")
    inlines = (InvoiceLineInline,)

    readonly_fields = (
        "invoice_number",
        "created_at",
        "updated_at",
        # snapshot
        "issuer_name",
        "issuer_vat",
        "issuer_reg_no",
        "issuer_address",
        "issuer_city",
        "issuer_country",
        "issuer_iban",
        "issuer_bank",
        "issuer_email",
        "issuer_phone",
        "bill_to_name",
        "bill_to_email",
        "bill_to_vat",
        "bill_to_reg_no",
        "bill_to_address",
        "bill_to_city",
        "bill_to_country",
    )


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("invoice", "position", "kind", "description", "total_amount", "currency")
    list_filter = ("kind", "currency")
    search_fields = ("description", "sku", "invoice__invoice_number")
    ordering = ("-id",)
