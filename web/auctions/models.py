from django.db import models
from django.conf import settings
from django.utils import timezone
from catalog.models import Product, Material  # <- use Product sizes & real Material

User = settings.AUTH_USER_MODEL


class Auction(models.Model):
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='auction',
        help_text="Produsul scos la licitație"
    )
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_auctions'
    )
    category = models.ForeignKey('catalog.Category', on_delete=models.PROTECT)

    # keep this aligned with Product.SIZE_CHOICES
    size = models.CharField(max_length=20, blank=True, choices=Product.SIZE_CHOICES)

    dimensions = models.JSONField(blank=True, null=True)

    # use normalized materials
    materials = models.ManyToManyField(Material, blank=True, related_name='auctions')

    description = models.TextField(blank=True)

    start_price = models.DecimalField(max_digits=10, decimal_places=2)
    min_price   = models.DecimalField(max_digits=10, decimal_places=2, help_text="Rezervă (preț minim acceptat)")
    start_time  = models.DateTimeField(default=timezone.now)
    duration_days = models.PositiveIntegerField(help_text="Durata licitației în zile")
    end_time    = models.DateTimeField(blank=True, null=True)
    is_active   = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_time']

    def save(self, *args, **kwargs):
        # calculează end_time și la create, nu doar la update
        if not self.end_time:
            base = self.start_time or timezone.now()
            self.end_time = base + timezone.timedelta(days=self.duration_days)
        super().save(*args, **kwargs)

    def current_price(self):
        last_bid = self.bids.order_by('-amount', '-placed_at').first()
        return last_bid.amount if last_bid else self.start_price

    def time_left(self):
        if not self.end_time:
            return None
        return max(self.end_time - timezone.now(), timezone.timedelta())


    def __str__(self):
        return f"Licitație {self.product.title} ({self.pk})"


class AuctionImage(models.Model):
    auction = models.ForeignKey('auctions.Auction', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='auctions/images/')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Imagine pentru {self.auction}"


class Bid(models.Model):
    auction = models.ForeignKey('auctions.Auction', on_delete=models.CASCADE, related_name='bids')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-placed_at']

    def __str__(self):
        return f"{self.user} → {self.amount} RON"
