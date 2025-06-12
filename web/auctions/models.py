from django.db import models
from django.conf import settings
from django.utils import timezone
from products.models import Product
from django.urls import reverse


class Auction(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='auction')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField()
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='won_auctions'
    )

    class Meta:
        ordering = ['-end_time']

    def __str__(self):
        return f"Licitație: {self.product.name}"

    def is_ongoing(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.is_active

    def highest_bid(self):
        return self.bids.order_by('-amount').first()
    
    @property
    def next_minimum(self):
        highest = self.highest_bid()
        return (highest.amount + 1) if highest else self.starting_price

    def get_absolute_url(self):
        return reverse('auctions:auction_detail', args=[self.product.slug])



class Bid(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-placed_at']
        unique_together = ('auction', 'bidder', 'amount')  # prevenim spam identic

    def __str__(self):
        return f"{self.bidder} - {self.amount} RON"

    def is_highest(self):
        return self.amount == self.auction.highest_bid().amount


class AuctionHistory(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='history')
    event = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"[{self.created_at}] {self.event}"
