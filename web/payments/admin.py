# payments/admin.py
from django.contrib import admin

from .models import Wallet, WalletTransaction, Payment, Refund


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


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance")
    search_fields = ("user__email", "user__first_name", "user__last_name")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "transaction_type",
        "amount",
        "method",
        "date",
        "balance_after",
    )
    list_filter = ("transaction_type", "method", "date")
    search_fields = ("user__email",)
    ordering = ("-date",)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "order",
        "user",
        "amount",
        "status",
        "to_wallet",
        "created_at",
    )
    list_filter = ("status", "to_wallet", "created_at")
    search_fields = ("payment__id", "order__id", "user__email")
    ordering = ("-created_at",)
