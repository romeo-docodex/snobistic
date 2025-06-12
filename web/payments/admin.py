from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'method', 'amount', 'status', 'created_at')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('user__email', 'processor_payment_id', 'order__id')
    date_hierarchy = 'created_at'
