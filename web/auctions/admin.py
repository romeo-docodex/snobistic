# auctions/admin.py
from django.contrib import admin

from .models import Auction, AuctionImage, AuctionOrder, AuctionReturnRequest, Bid


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "creator",
        "status",
        "start_price",
        "reserve_price",
        "current_price",
        "start_time",
        "end_time",
        "winner",
        "payment_due_at",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("product__title", "creator__email", "creator__username")
    raw_id_fields = ("product", "creator", "winner", "winning_bid")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("id", "auction", "user", "amount", "placed_at")
    list_filter = ("placed_at",)
    search_fields = ("auction__product__title", "user__email", "user__username")
    raw_id_fields = ("auction", "user")


@admin.register(AuctionImage)
class AuctionImageAdmin(admin.ModelAdmin):
    list_display = ("id", "auction", "created_at")
    raw_id_fields = ("auction",)


@admin.register(AuctionOrder)
class AuctionOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "auction", "buyer", "amount", "status", "payment_due_at", "created_at", "paid_at")
    list_filter = ("status", "created_at")
    raw_id_fields = ("auction", "buyer")


@admin.register(AuctionReturnRequest)
class AuctionReturnRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "reason", "status", "requested_at", "decided_at")
    list_filter = ("status", "reason", "requested_at")
    raw_id_fields = ("order",)
