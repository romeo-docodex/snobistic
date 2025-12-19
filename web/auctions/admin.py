# auctions/admin.py
from django.contrib import admin
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Max, Count

from .models import Auction, AuctionImage, Bid


# ── Inlines ────────────────────────────────────────────────────────────────────
class AuctionImageInline(admin.TabularInline):
    model = AuctionImage
    extra = 0
    fields = ("image", "preview")
    readonly_fields = ("preview",)

    @admin.display(description="Preview")
    def preview(self, obj):
        if getattr(obj, "image", None):
            return format_html(
                '<img src="{}" style="height:80px;object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    fields = ("user", "amount", "placed_at")
    readonly_fields = ("placed_at",)
    autocomplete_fields = ("user",)
    ordering = ("-placed_at",)


# ── Filters ────────────────────────────────────────────────────────────────────
class StateFilter(admin.SimpleListFilter):
    title = "Stare"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return (
            ("active", "Active"),
            ("ended", "Încheiate"),
            ("upcoming", "Viitoare"),
        )

    def queryset(self, request, qs):
        now = timezone.now()
        val = self.value()
        if val == "active":
            return qs.filter(is_active=True, end_time__gt=now, start_time__lte=now)
        if val == "ended":
            return qs.filter(end_time__lte=now)
        if val == "upcoming":
            return qs.filter(start_time__gt=now)
        return qs


# ── Admins ─────────────────────────────────────────────────────────────────────
@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    inlines = [AuctionImageInline, BidInline]

    list_display = (
        "id",
        "product_title",
        "creator",
        "category",
        "size",
        "start_price",
        "current_price_admin",
        "min_price",
        "bids_count_admin",
        "is_active",
        "ends_at",
        "time_left_admin",
    )
    list_filter = (
        StateFilter,
        "is_active",
        "category",
        "size",
        "start_time",
        "end_time",
    )
    search_fields = ("product__title", "product__sku", "creator__email", "creator__username")
    list_select_related = ("product", "category", "creator")
    date_hierarchy = "start_time"
    ordering = ("-start_time",)

    # If you have Material admin with search_fields, this enables autocomplete
    autocomplete_fields = ("product", "category", "creator", "materials")

    readonly_fields = ("computed_current_price", "product_link", "ends_at_readonly")
    fieldsets = (
        ("Produs", {"fields": ("product", "product_link", "category", "creator")}),
        ("Detalii", {"fields": ("size", "dimensions", "materials", "description")}),
        (
            "Setări licitație",
            {
                "fields": (
                    "start_price",
                    "min_price",
                    "start_time",
                    "duration_days",
                    "end_time",
                    "is_active",
                    "computed_current_price",
                    "ends_at_readonly",
                )
            },
        ),
    )

    actions = ["action_close_now", "action_open", "action_recalc_end", "action_extend_1d", "action_extend_7d"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # annotate highest bid and bid count to avoid N+1 in changelist
        return qs.annotate(_max_bid=Max("bids__amount"), _bids_count=Count("bids"))

    @admin.display(description="Produs", ordering="product__title")
    def product_title(self, obj):
        return obj.product.title

    @admin.display(description="Preț curent", ordering="_max_bid")
    def current_price_admin(self, obj):
        cur = obj._max_bid if obj._max_bid is not None else obj.start_price
        return f"{cur} RON"

    @admin.display(description="Oferte", ordering="_bids_count")
    def bids_count_admin(self, obj):
        return obj._bids_count

    @admin.display(description="Se termină")
    def ends_at(self, obj):
        return obj.end_time

    @admin.display(description="Timp rămas")
    def time_left_admin(self, obj):
        delta = obj.time_left()
        if not delta or delta.total_seconds() <= 0:
            return "—"
        total = int(delta.total_seconds())
        days, rem = divmod(total, 86400)
        hrs, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}z")
        if hrs:
            parts.append(f"{hrs}h")
        parts.append(f"{mins}m")
        return " ".join(parts)

    @admin.display(description="Legătură produs")
    def product_link(self, obj):
        try:
            admin_url = reverse("admin:catalog_product_change", args=[obj.product_id])
            public_url = obj.product.get_absolute_url()
            return format_html('<a href="{}">Admin</a> · <a href="{}" target="_blank">Public</a>', admin_url, public_url)
        except Exception:
            return "-"

    @admin.display(description="Preț curent (calc.)")
    def computed_current_price(self, obj):
        return self.current_price_admin(obj)

    @admin.display(description="Se încheie (RO)")
    def ends_at_readonly(self, obj):
        return obj.end_time

    # ── Actions ────────────────────────────────────────────────────────────────
    @admin.action(description="Închide acum licitațiile selectate")
    def action_close_now(self, request, queryset):
        updated = queryset.update(is_active=False, end_time=timezone.now())
        self.message_user(request, f"Închise {updated} licitații.")

    @admin.action(description="Activează licitațiile selectate")
    def action_open(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activate {updated} licitații.")

    @admin.action(description="Recalculează data de final (start_time + zile)")
    def action_recalc_end(self, request, queryset):
        count = 0
        for a in queryset:
            a.end_time = (a.start_time or timezone.now()) + timezone.timedelta(days=a.duration_days)
            a.save(update_fields=["end_time"])
            count += 1
        self.message_user(request, f"Recalculat end_time pentru {count} licitații.")

    @admin.action(description="Prelungește cu +1 zi")
    def action_extend_1d(self, request, queryset):
        for a in queryset:
            a.end_time = (a.end_time or timezone.now()) + timezone.timedelta(days=1)
            a.save(update_fields=["end_time"])
        self.message_user(request, "Prelungite cu 1 zi.")

    @admin.action(description="Prelungește cu +7 zile")
    def action_extend_7d(self, request, queryset):
        for a in queryset:
            a.end_time = (a.end_time or timezone.now()) + timezone.timedelta(days=7)
            a.save(update_fields=["end_time"])
        self.message_user(request, "Prelungite cu 7 zile.")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("id", "auction_link", "user", "amount", "placed_at")
    list_filter = ("placed_at",)
    search_fields = (
        "auction__product__title",
        "auction__product__sku",
        "user__email",
        "user__username",
    )
    autocomplete_fields = ("auction", "user")
    date_hierarchy = "placed_at"
    list_select_related = ("auction__product", "user")
    ordering = ("-placed_at",)

    @admin.display(description="Licitație", ordering="auction__product__title")
    def auction_link(self, obj):
        url = reverse("admin:auctions_auction_change", args=[obj.auction_id])
        return format_html('<a href="{}">#{}</a> — {}', url, obj.auction_id, obj.auction.product.title)


@admin.register(AuctionImage)
class AuctionImageAdmin(admin.ModelAdmin):
    list_display = ("id", "auction", "thumb")
    search_fields = ("auction__product__title",)
    autocomplete_fields = ("auction",)
    readonly_fields = ("thumb",)

    @admin.display(description="Previzualizare")
    def thumb(self, obj):
        if getattr(obj, "image", None):
            return format_html(
                '<img src="{}" style="height:70px;border-radius:4px;object-fit:cover;" />',
                obj.image.url,
            )
        return "—"
