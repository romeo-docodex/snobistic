# catalog/admin.py
from django.contrib import admin
from django.utils.html import format_html

from . import models


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "size_group")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_filter = ("size_group",)


@admin.register(models.Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "parent",
        "gender",
        "size_group",
        "measurement_profile",
        "is_non_returnable",
        "avg_weight_kg",
        "co2_avoided_kg",
        "trees_equivalent",
    )
    list_select_related = ("category", "parent")
    list_filter = (
        "category",
        "parent",
        "gender",
        "size_group",
        "measurement_profile",
        "is_non_returnable",
    )
    search_fields = ("name", "category__name", "parent__name")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category__name", "name")


@admin.register(models.Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "category_type", "is_sustainable")
    search_fields = ("name",)
    ordering = ("name",)
    list_filter = ("category_type", "is_sustainable")


@admin.register(models.Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("swatch", "name", "hex_code")
    search_fields = ("name", "hex_code")
    ordering = ("name",)

    def swatch(self, obj):
        if obj.hex_code:
            return format_html(
                '<span style="display:inline-block;width:16px;height:16px;'
                'border:1px solid #ddd;background:{}"></span>',
                obj.hex_code,
            )
        return "—"

    swatch.short_description = ""


@admin.register(models.Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "group", "is_fast_fashion", "is_visible_public")
    list_filter = ("group", "is_fast_fashion", "is_visible_public")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(models.Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(models.SustainabilityTag)
class SustainabilityTagAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "slug")
    search_fields = ("name", "key")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


class ProductImageInline(admin.TabularInline):
    model = models.ProductImage
    extra = 1
    fields = ("image", "alt_text", "position")
    ordering = ("position", "id")


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "thumb",
        "title",
        "sku",
        "owner",
        "category",
        "subcategory",
        "brand_display",
        "sale_type",
        "price",
        "display_size",
        "condition",
        "gender",
        "garment_type",
        "moderation_status",
        "is_active",
        "is_archived",
        "created_at",
    )
    list_filter = (
        "is_active",
        "is_archived",
        "category",
        "subcategory",
        "brand",
        "material",
        "size",
        "size_alpha",
        "size_fr",
        "size_it",
        "size_gb",
        "shoe_size_eu",
        "condition",
        "gender",
        "garment_type",
        "fit",
        "sale_type",
        "moderation_status",
        "sustainability_tags",
        "sustainability_none",
        "created_at",
    )
    search_fields = (
        "title",
        "sku",
        "description",
        "owner__email",
        "owner__first_name",
        "owner__last_name",
        "brand__name",
        "brand_other",
        "category__name",
        "subcategory__name",
        "real_color_name",
    )
    list_select_related = (
        "owner",
        "category",
        "subcategory",
        "brand",
        "material",
    )
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ("owner", "pickup_location")
    autocomplete_fields = ("category", "subcategory", "brand", "material", "base_color")
    readonly_fields = ("sku", "created_at", "updated_at")
    filter_horizontal = ("colors", "tags", "sustainability_tags")
    date_hierarchy = "created_at"
    actions = (
        "activate_products",
        "deactivate_products",
        "approve_products",
        "reject_products",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "owner",
                    "title",
                    "slug",
                    "description",
                    "category",
                    "subcategory",
                    "brand",
                    "brand_other",
                    "is_active",
                    "is_archived",
                )
            },
        ),
        ("Images", {"fields": ("main_image",)}),
        (
            "Pricing & SKU",
            {
                "fields": (
                    "sale_type",
                    "price",
                    "sku",
                    "size",
                    "size_alpha",
                    "shoe_size_eu",
                    "size_fr",
                    "size_it",
                    "size_gb",
                    "material",
                    "auction_start_price",
                    "auction_buy_now_price",
                    "auction_reserve_price",
                    "auction_end_at",
                )
            },
        ),
        (
            "Style & Attributes",
            {
                "fields": (
                    "condition",
                    "condition_notes",
                    "gender",
                    "garment_type",
                    "fit",
                    "base_color",
                    "real_color_name",
                    "colors",
                    "tags",
                )
            },
        ),
        (
            "Dimensions (text)",
            {
                "classes": ("collapse",),
                "fields": (
                    "shoulders",
                    "bust",
                    "waist",
                    "hips",
                    "length",
                    "sleeve",
                    "inseam",
                    "outseam",
                ),
            },
        ),
        (
            "Dimensions (cm) – îmbrăcăminte",
            {
                "classes": ("collapse",),
                "fields": (
                    "shoulders_cm",
                    "bust_cm",
                    "waist_cm",
                    "hips_cm",
                    "length_cm",
                    "sleeve_cm",
                    "inseam_cm",
                    "outseam_cm",
                ),
            },
        ),
        (
            "Dimensions (cm) – încălțăminte",
            {
                "classes": ("collapse",),
                "fields": (
                    "shoe_insole_length_cm",
                    "shoe_width_cm",
                    "shoe_heel_height_cm",
                    "shoe_total_height_cm",
                ),
            },
        ),
        (
            "Dimensions (cm) – genți",
            {
                "classes": ("collapse",),
                "fields": (
                    "bag_width_cm",
                    "bag_height_cm",
                    "bag_depth_cm",
                    "strap_length_cm",
                ),
            },
        ),
        (
            "Dimensions (cm) – curele",
            {
                "classes": ("collapse",),
                "fields": (
                    "belt_length_total_cm",
                    "belt_length_usable_cm",
                    "belt_width_cm",
                ),
            },
        ),
        (
            "Dimensions (cm) – bijuterii / accesorii",
            {
                "classes": ("collapse",),
                "fields": (
                    "jewelry_chain_length_cm",
                    "jewelry_drop_length_cm",
                    "jewelry_pendant_size_cm",
                ),
            },
        ),
        (
            "Inventory & Logistics",
            {
                "classes": ("collapse",),
                "fields": (
                    "weight_g",
                    "package_l_cm",
                    "package_w_cm",
                    "package_h_cm",
                    "pickup_location",
                    "package_size",
                ),
            },
        ),
        (
            "Sustenabilitate",
            {
                "fields": (
                    "sustainability_tags",
                    "sustainability_none",
                )
            },
        ),
        (
            "Moderation",
            {
                "fields": (
                    "moderation_status",
                    "moderation_notes",
                    "moderated_by",
                    "moderated_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def thumb(self, obj):
        if obj.main_image:
            return format_html(
                '<img src="{}" style="height:40px;width:auto;border-radius:4px;" />',
                obj.main_image.url,
            )
        return "—"

    thumb.short_description = "Img"

    def brand_display(self, obj):
        return obj.display_brand or "—"

    brand_display.short_description = "Brand"

    @admin.action(description="Activează produsele selectate")
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} produse activate.")

    @admin.action(description="Dezactivează produsele selectate")
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} produse dezactivate.")

    @admin.action(description="Aprobă (moderare) produsele selectate")
    def approve_products(self, request, queryset):
        updated = queryset.update(
            moderation_status="APPROVED", moderated_by=request.user
        )
        self.message_user(request, f"{updated} produse aprobate.")

    @admin.action(description="Respinge (moderare) produsele selectate")
    def reject_products(self, request, queryset):
        updated = queryset.update(
            moderation_status="REJECTED", moderated_by=request.user
        )
        self.message_user(request, f"{updated} produse respinse.")


@admin.register(models.Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    list_select_related = ("user", "product")
    search_fields = ("user__email", "product__title", "product__sku")
    autocomplete_fields = ("user", "product")
    ordering = ("-created_at",)
