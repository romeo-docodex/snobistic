# payments/admin.py
from django.contrib import admin

from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "user",
        "provider",
        "amount",
        "currency",
        "status",
        "created_at",
    )
    list_filter = ("provider", "status", "currency", "created_at")
    search_fields = (
        "order__id",
        "user__email",
        "stripe_session_id",
        "stripe_payment_intent_id",
    )
    ordering = ("-created_at",)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "order",
        "user",
        "amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("payment__id", "order__id", "user__email")
    ordering = ("-created_at",)
