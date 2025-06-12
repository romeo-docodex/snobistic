# web/accounts/urls.py
from django.urls import path
from .views import (
    AccountSignupView, activate_account,
    ResendActivationView, ReactivateAccountView,
    LoginView, logout_view, TwoFactorView,
    ProfileView, ChangePasswordView, ChangeEmailView,
    delete_address_view, set_default_address_view,
    DeleteAccountView,
    CustomPasswordResetView, CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView, CustomPasswordResetCompleteView,
)

app_name = "accounts"

urlpatterns = [
    path("register/",    AccountSignupView.as_view(),   name="register"),
    path("activate/<uidb64>/<token>/", activate_account,  name="activate"),
    path("resend-activation/",         ResendActivationView.as_view(),  name="resend_activation"),
    path("reactivate/",                ReactivateAccountView.as_view(), name="reactivate_account"),

    path("login/",   LoginView.as_view(),  name="login"),
    path("logout/",  logout_view,          name="logout"),

    path("2fa/",     TwoFactorView.as_view(), name="two_factor"),

    path("profile/",       ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("change-email/",  ChangeEmailView.as_view(),  name="change_email"),
    path("delete-account/", DeleteAccountView.as_view(), name="delete_account"),

    path("address/delete/<int:address_id>/",     delete_address_view,      name="delete_address"),
    path("address/set-default/<int:address_id>/", set_default_address_view, name="set_default_address"),

    path("password/reset/",       CustomPasswordResetView.as_view(),         name="password_reset"),
    path("password/reset/done/",  CustomPasswordResetDoneView.as_view(),     name="password_reset_done"),
    path("password/reset/confirm/<uidb64>/<token>/", CustomPasswordResetConfirmView.as_view(),  name="password_reset_confirm"),
    path("password/reset/complete/", CustomPasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
