from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserProfile, UserAddress, EmailToken


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_company', 'verified_email', 'is_active')
    list_filter = ('user_type', 'is_company', 'verified_email', 'is_active')
    search_fields = ('email', 'username', 'phone')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informații suplimentare', {
            'fields': (
                'phone', 'birth_date', 'user_type', 'is_company', 'vat_payer',
                'two_fa_enabled', 'verified_email'
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'phone', 'password1', 'password2',
                'user_type', 'is_company', 'vat_payer'
            ),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'iban', 'avatar')
    search_fields = ('user__username', 'user__email')


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_type', 'city', 'is_default')
    list_filter = ('address_type', 'country', 'is_default')
    search_fields = ('user__email', 'city', 'postal_code')


@admin.register(EmailToken)
class EmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'token', 'created_at', 'used')
    list_filter = ('purpose', 'used', 'created_at')
    search_fields = ('user__email', 'token')
