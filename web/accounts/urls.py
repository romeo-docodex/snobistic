# accounts/urls.py
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Auth
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),  # ✅ POST-only enforced in view
    path("register/", views.RegisterView.as_view(), name="register"),
    path("registration-email-sent/", views.registration_email_sent, name="registration_email_sent"),
    path("activate/<uidb64>/<token>/", views.activate_account, name="activate"),
    path("resend-activation/", views.resend_activation, name="resend_activation"),

    # Social login helper
    path("oauth/", views.social_login_start, name="social_login_start"),

    # 2FA
    path("2fa/", views.TwoFactorView.as_view(), name="two_factor"),
    path("2fa/enable/", views.enable_2fa, name="enable_2fa"),
    path("2fa/setup/", views.two_factor_setup, name="two_factor_setup"),
    path("2fa/setup/verify/", views.two_factor_setup_verify, name="two_factor_setup_verify"),
    path("2fa/backup/regenerate/", views.regenerate_backup_codes, name="regenerate_backup_codes"),
    path("2fa/disable/", views.disable_2fa, name="disable_2fa"),
    path("2fa/enable-email/", views.enable_2fa_email, name="enable_2fa_email"),
    path("2fa/enable-sms/", views.enable_2fa_sms, name="enable_2fa_sms"),
    path("trusted-devices/<int:pk>/revoke/", views.revoke_trusted_device, name="revoke_trusted_device"),

    # Password reset/change
    path("password/reset/", views.CustomPasswordResetView.as_view(), name="password_reset"),
    path("password/reset/done/", views.CustomPasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", views.CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/complete/", views.CustomPasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("password/change/", views.CustomPasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/", views.CustomPasswordChangeDoneView.as_view(), name="password_change_done"),

    # Profile
    path("profile/", views.profile, name="profile"),
    path("profile/personal/", views.profile_personal, name="profile_personal"),

    # ✅ Alias to stop 404s (remove after templates are migrated)
    path("profile/data/", views.profile_personal, name="profile_data"),

    path("profile/security/", views.profile_security, name="profile_security"),
    path("profile/dimensions/", views.profile_dimensions, name="profile_dimensions"),

    # Addresses
    path("addresses/", views.address_list, name="address_list"),
    path("addresses/add/", views.address_form, name="address_add"),
    path("addresses/<int:pk>/edit/", views.address_form, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),

    # Seller
    path("seller/settings/", views.seller_settings, name="seller_settings"),
    path("seller/locations/add/", views.seller_location_add, name="seller_location_add"),
    path("seller/locations/<int:pk>/delete/", views.seller_location_delete, name="seller_location_delete"),
    path("seller/locations/<int:pk>/default/", views.seller_location_make_default, name="seller_location_make_default"),

    # KYC user
    path("kyc/", views.kyc_center, name="kyc_center"),
    path("kyc/documents/<int:pk>/delete/", views.kyc_document_delete, name="kyc_document_delete"),

    # KYC staff
    path("staff/kyc/", views.staff_kyc_queue, name="staff_kyc_queue"),
    path("staff/kyc/<int:pk>/", views.staff_kyc_review, name="staff_kyc_review"),
    path("staff/kyc/<int:pk>/approve/", views.staff_kyc_approve, name="staff_kyc_approve"),
    path("staff/kyc/<int:pk>/reject/", views.staff_kyc_reject, name="staff_kyc_reject"),

    # Roles
    path("roles/", views.roles_center, name="roles_center"),
    path("roles/upgrade-to-seller/", views.upgrade_to_seller, name="upgrade_to_seller"),
    path("roles/downgrade/", views.downgrade_roles, name="downgrade_roles"),
    path("roles/toggle-seller-can-buy/", views.toggle_seller_can_buy, name="toggle_seller_can_buy"),

    # Email change
    path("email/change/request/", views.email_change_request, name="email_change_request"),
    path("email/change/confirm/<uidb64>/<token>/", views.email_change_confirm, name="email_change_confirm"),

    # Sessions + GDPR
    path("sessions/", views.sessions_center, name="sessions_center"),
    path("sessions/logout-all/", views.logout_all_sessions, name="logout_all_sessions"),
    path("gdpr/export/", views.gdpr_export, name="gdpr_export"),

    # Delete account
    path("delete/request/", views.delete_account_request, name="delete_account_request"),
    path("delete/confirm/", views.delete_account_confirm, name="delete_account_confirm"),
]
