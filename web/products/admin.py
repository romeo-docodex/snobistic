from django.contrib import admin
from .models import Brand, Category, Product, ProductImage, ProductReport, ProductAuditLog


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'country')
    search_fields = ('name',)
    list_filter = ('country',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'seller', 'listing_type', 'price_display',
        'stock', 'condition', 'is_active', 'is_published', 'is_approved', 'created_at'
    )
    list_filter = (
        'listing_type', 'condition', 'is_active',
        'is_published', 'is_approved', 'brand', 'category'
    )
    search_fields = ('name', 'seller__email', 'brand__name', 'category__name')
    readonly_fields = ('slug', 'created_at')
    fieldsets = (
        (None, {
            'fields': (
                'name', 'slug', 'seller', 'brand', 'category', 'description',
                'listing_type', 'condition', 'price', 'stock'
            )
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description'),
        }),
        ('Status & Dates', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_published', 'is_approved', 'created_at')
        }),
        ('Optional attributes', {
            'classes': ('collapse',),
            'fields': ('size', 'color', 'material', 'weight', 'authenticity_proof')
        }),
    )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_primary', 'alt_text')
    list_filter = ('is_primary',)
    search_fields = ('product__name', 'alt_text')


@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'reporter', 'created_at', 'is_resolved')
    list_filter = ('is_resolved',)
    search_fields = ('product__name', 'reporter__email', 'reason')


@admin.register(ProductAuditLog)
class ProductAuditLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'action', 'timestamp')
    search_fields = ('product__name', 'user__email', 'action')
    readonly_fields = ('timestamp',)
