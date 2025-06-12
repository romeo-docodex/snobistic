# shop/admin.py

from django.contrib import admin
from .models import Favorite, ProductAuthenticationRequest

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'product__name')
    date_hierarchy = 'created_at'


@admin.register(ProductAuthenticationRequest)
class ProductAuthenticationRequestAdmin(admin.ModelAdmin):
    list_display    = ('id', 'who', 'processed', 'created_at')
    list_filter     = ('processed', 'created_at')
    search_fields   = ('email', 'user__email')
    readonly_fields = ('created_at',)
    ordering        = ('-created_at',)

    def who(self, obj):
        return obj.user.email if obj.user else obj.email
    who.short_description = 'Solicitant'

    actions = ['mark_processed']

    def mark_processed(self, request, queryset):
        updated = queryset.update(processed=True)
        self.message_user(request, f"{updated} cereri marcate ca procesate.")
    mark_processed.short_description = "Marchează ca procesate"
