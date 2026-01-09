# cart/admin.py
from django.contrib import admin
from .models import Cart, CartItem, Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount",
        "is_active",
        "valid_from",
        "expires_at",
        "usage_limit",
        "used_count",
        "min_order_amount",
        "max_discount_amount",
        "created_at",
    )
    list_filter = ("is_active", "created_at", "expires_at")
    search_fields = ("code",)
    ordering = ("-created_at",)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "session_key", "coupon", "created_at", "updated_at")
    search_fields = ("user__email", "session_key")
    list_filter = ("created_at", "updated_at", "coupon")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "added_at")
    search_fields = ("cart__user__email", "cart__session_key", "product__title")
    list_filter = ("added_at",)
    list_select_related = ("cart", "product")
