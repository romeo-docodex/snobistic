# authenticator/admin.py
from django.contrib import admin

from .models import AuthRequest, AuthImage, ProductAuthentication


class AuthImageInline(admin.TabularInline):
    model = AuthImage
    extra = 0
    fields = ("image", "position", "uploaded_at")
    readonly_fields = ("uploaded_at",)


@admin.register(AuthRequest)
class AuthRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "submitted_at",
        "status",
        "verdict",
        "provider",
        "provider_reference",
        "user",
        "email",
        "product",
    )
    list_filter = ("status", "verdict", "provider")
    search_fields = ("id", "provider_reference", "email", "user__email", "product__slug", "product__sku")
    inlines = [AuthImageInline]
    readonly_fields = ("public_token", "submitted_at", "sent_at", "decided_at")
    actions = ["mark_authentic", "mark_fake", "mark_inconclusive"]

    def _apply_manual(self, request, qs, verdict):
        from authenticator.services.provider_client import apply_result_to_product

        for req in qs:
            req.finalize(verdict=verdict, payload=req.provider_payload or {"manual": True})
            req.save()
            apply_result_to_product(req)

    @admin.action(description="Setează verdict: Autentic (manual)")
    def mark_authentic(self, request, queryset):
        self._apply_manual(request, queryset, AuthRequest.Verdict.AUTHENTIC)

    @admin.action(description="Setează verdict: Neautentic (manual)")
    def mark_fake(self, request, queryset):
        self._apply_manual(request, queryset, AuthRequest.Verdict.FAKE)

    @admin.action(description="Setează verdict: Neconcludent (manual)")
    def mark_inconclusive(self, request, queryset):
        self._apply_manual(request, queryset, AuthRequest.Verdict.INCONCLUSIVE)


@admin.register(ProductAuthentication)
class ProductAuthenticationAdmin(admin.ModelAdmin):
    list_display = ("product", "is_verified", "verdict", "provider", "verified_at")
    list_filter = ("is_verified", "verdict", "provider")
    search_fields = ("product__slug", "product__sku", "product__title", "provider_reference")
