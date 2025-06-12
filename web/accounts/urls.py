# accounts/urls.py

from django.urls import path
from .views import (
    AccountSignupView, activate_account, ResendActivationView,
    LoginView, logout_view, TwoFactorView,
    ProfileView, ChangePasswordView, DeleteAccountView,
    delete_address_view, set_default_address_view,
    CustomPasswordResetView, CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView, CustomPasswordResetCompleteView,
)

app_name = "accounts"

urlpatterns = [
    # 🔐 Register & activate
    path("register/", AccountSignupView.as_view(), name="register"),
    path("activate/<uidb64>/<token>/", activate_account, name="activate"),
    path("resend-activation/", ResendActivationView.as_view(), name="resend_activation"),

    # 🔐 Login / Logout
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),

    # 🔒 2FA
    path("2fa/", TwoFactorView.as_view(), name="two_factor"),

    # 👤 Profil
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("delete-account/", DeleteAccountView.as_view(), name="delete_account"),

    # 📍 Adrese
    path("address/delete/<int:address_id>/", delete_address_view, name="delete_address"),
    path("address/set-default/<int:address_id>/", set_default_address_view, name="set_default_address"),

    # 🔁 Reset parola
    path("password/reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path("password/reset/done/", CustomPasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/confirm/<uidb64>/<token>/", CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/complete/", CustomPasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
