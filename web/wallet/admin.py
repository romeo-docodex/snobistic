from django.contrib import admin
from .models import Wallet, Transaction

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('balance', 'updated_at')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'get_user_email', 'type', 'amount', 'timestamp')
    list_filter = ('type', 'timestamp')
    search_fields = ('wallet__user__email', 'description')
    date_hierarchy = 'timestamp'

    def get_user_email(self, obj):
        return obj.wallet.user.email
    get_user_email.short_description = 'User'
