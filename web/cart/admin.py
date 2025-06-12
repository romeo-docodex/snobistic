from django.contrib import admin
from .models import CartItem

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'product', 'quantity', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__email', 'session_key', 'product__name')
