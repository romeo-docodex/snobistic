from django.contrib import admin
from .models import Auction, Bid, AuctionHistory

@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('product', 'start_time', 'end_time', 'is_active', 'winner')
    list_filter  = ('is_active',)
    search_fields = ('product__name',)

@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('auction', 'bidder', 'amount', 'placed_at')
    list_filter = ('placed_at',)
    search_fields = ('bidder__email',)

@admin.register(AuctionHistory)
class AuctionHistoryAdmin(admin.ModelAdmin):
    list_display = ('auction', 'event', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('event',)
