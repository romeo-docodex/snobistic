# wallet/admin.py
from django.contrib import admin

from .models import Wallet, WalletTransaction, WithdrawalRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "currency", "updated_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_filter = ("currency",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "tx_type", "direction", "amount", "method", "external_id", "created_at")
    list_filter = ("tx_type", "direction", "method", "created_at")
    search_fields = ("wallet__user__email", "external_id")
    ordering = ("-created_at",)


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "amount", "iban", "status", "created_at", "processed_at")
    list_filter = ("status", "created_at")
    search_fields = ("wallet__user__email", "iban")
    ordering = ("-created_at",)
