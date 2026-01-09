# accounts/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from .forms import CustomUserChangeForm
from .models import (
    AccountEvent,
    Address,
    CustomUser,
    KycDocument,
    Profile,
    SellerLocation,
    SellerProfile,
    TrustedDevice,
)


class AdminUserCreationForm(UserCreationForm):
    """
    Minimal, safe admin create form.
    """

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "is_active", "is_staff", "is_seller")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ lock legacy seller flag (truth is Profile.role_seller)
        if "is_seller" in self.fields:
            self.fields["is_seller"].disabled = True
            self.fields["is_seller"].help_text = _("Derivat din Profile.role_seller (read-only).")


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name = _("Profil utilizator")
    verbose_name_plural = _("Profile utilizator")
    fk_name = "user"
    fieldsets = (
        (_("Date personale & contact"), {"fields": ("avatar", "phone", "date_of_birth")}),
        (
            _("Persoană fizică / juridică"),
            {
                "fields": (
                    "is_company",
                    "company_vat",
                    "company_name",
                    "company_reg_number",
                    "company_website",
                    "company_phone",
                    "company_contact_person",
                )
            },
        ),
        (_("Roluri & cumpărare"), {"fields": ("role_buyer", "role_seller", "seller_can_buy")}),
        (_("Comunicare & marketing"), {"fields": ("newsletter", "marketing", "sms_notifications")}),
        (
            _("Securitate & KYC"),
            {
                "fields": (
                    "two_factor_enabled",
                    "two_factor_method",
                    "kyc_status",
                    "kyc_approved_at",
                    "buyer_trust_score",
                )
            },
        ),
    )
    readonly_fields = ("kyc_approved_at",)


class SellerInline(admin.StackedInline):
    model = SellerProfile
    can_delete = False
    verbose_name = _("Profil vânzător")
    verbose_name_plural = _("Profile vânzător")
    fk_name = "user"
    fieldsets = (
        (_("Identitate vânzător"), {"fields": ("seller_type", "seller_level", "iban")}),
        (_("Scor & comision"), {"fields": ("seller_trust_score", "seller_commission_rate", "lifetime_sales_net")}),
        (
            _("Setări livrare & ramburs"),
            {"fields": ("accept_cod", "allow_local_pickup", "local_delivery_radius_km", "max_cod_value")},
        ),
    )


class SellerLocationInline(admin.TabularInline):
    model = SellerLocation
    fk_name = "user"
    extra = 0
    fields = ("code", "label", "is_default")
    verbose_name = _("Locație vânzător")
    verbose_name_plural = _("Locații vânzător")


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = AdminUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    ordering = ("-date_joined",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff", "is_seller_truth")
    list_filter = ("is_active", "is_staff", "profile__role_seller", "profile__kyc_status")
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_seller", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_seller",
                ),
            },
        ),
    )

    readonly_fields = ("last_login", "date_joined", "is_seller")

    inlines = (ProfileInline, SellerInline, SellerLocationInline)

    def is_seller_truth(self, obj: CustomUser) -> bool:
        prof = getattr(obj, "profile", None)
        if prof is not None:
            return bool(getattr(prof, "role_seller", False))
        return bool(getattr(obj, "is_seller", False))

    is_seller_truth.boolean = True
    is_seller_truth.short_description = "Seller (truth)"


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "country", "is_default_shipping", "is_default_billing", "updated_at")
    search_fields = ("user__email", "city", "street_address")
    list_filter = ("country", "is_default_shipping", "is_default_billing")


@admin.register(AccountEvent)
class AccountEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "ip", "created_at")
    search_fields = ("user__email", "event", "ip")
    list_filter = ("event",)


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "ip", "created_at", "last_used_at", "expires_at")
    search_fields = ("user__email", "label", "ip")
    list_filter = ("expires_at",)


@admin.register(KycDocument)
class KycDocumentAdmin(admin.ModelAdmin):
    list_display = ("user", "document_type", "status", "created_at", "reviewed_at", "reviewed_by")
    search_fields = ("user__email", "reference_code")
    list_filter = ("status", "document_type")
