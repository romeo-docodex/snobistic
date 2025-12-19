# logistics/admin.py
from django.contrib import admin

from .models import Courier, ShippingRate, Shipment


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ("courier", "name", "base_price", "currency", "is_active")
    list_filter = ("courier", "is_active")
    search_fields = ("name", "courier__name")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "seller",
        "courier",
        "tracking_number",
        "status",
        "shipped_at",
        "delivered_at",
    )
    list_filter = ("courier", "status")
    search_fields = ("tracking_number", "order__id", "seller__email")
