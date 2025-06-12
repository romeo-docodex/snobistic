# shop/admin.py
from django.contrib import admin
from .models import Favorite, ProductAuthenticationRequest


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('user__email', 'product__name')


@admin.register(ProductAuthenticationRequest)
class ProductAuthenticationRequestAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'processed', 'created_at')
    list_filter = ('processed', 'created_at')
    search_fields = ('user__email', 'email')
    readonly_fields = ('certificate_url',)
