from django.contrib import admin
from .models import (
    Brand, Category, Product, ProductImage,
    ProductReport, ProductAuditLog
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'country')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.action(description="Marchează ca aprobat")
def mark_as_approved(modeladmin, request, queryset):
    queryset.update(is_approved=True)


@admin.action(description="Publică produsele")
def mark_as_published(modeladmin, request, queryset):
    queryset.update(is_published=True)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'seller', 'listing_type', 'price', 'condition',
        'is_approved', 'is_published', 'created_at'
    )
    list_filter = (
        'listing_type', 'condition', 'is_approved', 'is_published',
        'brand', 'category'
    )
    search_fields = ('name', 'description', 'seller__email')
    inlines = [ProductImageInline]
    readonly_fields = ('slug', 'created_at')
    actions = [mark_as_approved, mark_as_published]


@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'reporter', 'created_at', 'is_resolved')
    list_filter = ('is_resolved',)
    search_fields = ('product__name', 'reporter__email', 'reason')


@admin.register(ProductAuditLog)
class ProductAuditLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'action', 'timestamp')
    list_filter = ('action',)
    search_fields = ('product__name', 'user__email', 'action')
