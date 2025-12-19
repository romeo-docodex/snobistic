# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import (
    CustomUser,
    Profile,
    SellerProfile,
    Address,
    SellerLocation,
    AccountEvent,
    TrustedDevice,
    KycDocument,
)
from .forms import RegisterForm, CustomUserChangeForm


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name = _("Profil utilizator")
    verbose_name_plural = _("Profile utilizator")
    fk_name = "user"
    fieldsets = (
        (_("Date personale & contact"), {
            "fields": (
                "avatar",
                "phone",
                "date_of_birth",
            )
        }),
        (_("Persoană fizică / juridică"), {
            "fields": (
                "is_company",
                "company_vat",
                "company_name",
                "company_reg_number",
                "company_website",
                "company_phone",
                "company_contact_person",
            )
        }),
        (_("Roluri & drepturi cumpărare"), {
            "fields": (
                "role_buyer",
                "role_seller",
                "seller_can_buy",
            )
        }),
        (_("Comunicare & marketing"), {
            "fields": (
                "newsletter",
                "marketing",
                "sms_notifications",
            )
        }),
        (_("Securitate & KYC"), {
            "fields": (
                "two_factor_enabled",
                "two_factor_method",
                "kyc_status",
                "kyc_approved_at",
                "buyer_trust_score",
            )
        }),
    )
    readonly_fields = ("kyc_approved_at",)


class SellerInline(admin.StackedInline):
    model = SellerProfile
    can_delete = False
    verbose_name = _("Profil vânzător")
    verbose_name_plural = _("Profile vânzător")
    fk_name = "user"
    fieldsets = (
        (_("Identitate vânzător"), {
            "fields": (
                "seller_type",
                "seller_level",
                "iban",
            )
        }),
        (_("Scor & comision"), {
            "fields": (
                "seller_trust_score",
                "seller_commission_rate",
                "lifetime_sales_net",
            )
        }),
        (_("Setări livrare & ramburs"), {
            "fields": (
                "accept_cod",
                "allow_local_pickup",
                "local_delivery_radius_km",
                "max_cod_value",
            )
        }),
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
    form = CustomUserChangeForm         # de editare
    add_form = RegisterForm             # de creare

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "is_seller",
        "referral_code",
        "referred_by",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_seller",
        "is_superuser",
        "groups",
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Date personale"), {
            "fields": ("first_name", "last_name"),
        }),
        (_("Program recomandări"), {
            "fields": ("referral_code", "referred_by"),
        }),
        (_("Permisiuni"), {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "is_seller",
                "groups",
                "user_permissions",
            ),
        }),
        (_("Date importante"), {
            "fields": ("last_login", "date_joined"),
        }),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "first_name",
                "last_name",
                "password1",
                "password2",
                "role",  # role vine din RegisterForm
            ),
        }),
    )

    search_fields = ("email", "first_name", "last_name", "referral_code")
    ordering = ("email",)

    def get_inline_instances(self, request, obj=None):
        """
        - la creare (obj is None) nu arătăm inline-uri
        - la editare: mereu ProfileInline,
          iar SellerInline + SellerLocationInline doar dacă e vânzător
        """
        if obj is None:
            return []

        inline_instances = [ProfileInline(self.model, self.admin_site)]

        if obj.is_seller:
            inline_instances.append(SellerInline(self.model, self.admin_site))
            inline_instances.append(SellerLocationInline(self.model, self.admin_site))

        return inline_instances


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "street_address",
        "city",
        "region",
        "postal_code",
        "country",
        "is_billing",
        "is_default_shipping",
        "is_default_billing",
    )
    list_filter = (
        "country",
        "is_billing",
        "is_default_shipping",
        "is_default_billing",
    )
    search_fields = (
        "user__email",
        "street_address",
        "city",
        "region",
        "postal_code",
    )
    raw_id_fields = ("user",)
    ordering = ("user__email", "city")


@admin.register(SellerLocation)
class SellerLocationAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "label", "is_default")
    list_filter = ("is_default",)
    search_fields = ("user__email", "code", "label")
    raw_id_fields = ("user",)


@admin.register(AccountEvent)
class AccountEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "ip", "created_at")
    list_filter = ("event", "created_at")
    search_fields = ("user__email", "ip", "user_agent")
    raw_id_fields = ("user",)
    readonly_fields = ("user", "event", "ip", "user_agent", "created_at")
    ordering = ("-created_at",)


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "ip", "created_at", "last_used_at", "expires_at")
    list_filter = ("expires_at",)
    search_fields = ("user__email", "label", "ip")
    raw_id_fields = ("user",)
    readonly_fields = ("token_hash",)


@admin.register(KycDocument)
class KycDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "document_type",
        "status",
        "is_primary",
        "reference_code",
        "created_at",
        "reviewed_at",
        "expires_at",
    )
    list_filter = ("status", "document_type", "is_primary", "created_at")
    search_fields = ("user__email", "reference_code")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)
