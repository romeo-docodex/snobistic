# invoices/admin.py
from django.contrib import admin

from .models import Invoice


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
