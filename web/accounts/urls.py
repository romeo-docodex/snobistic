# accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ============================
    # Autentificare & înregistrare
    # ============================
    path('autentificare/', views.LoginView.as_view(), name='login'),
    path('deconectare/', views.logout_view, name='logout'),
    path('inregistrare/', views.RegisterView.as_view(), name='register'),
    path('inregistrare/email-trimis/', views.registration_email_sent, name='registration_email_sent'),
    path('activare-cont/<uidb64>/<token>/', views.activate_account, name='activate'),
    path('activare/retrimitere/', views.resend_activation, name='resend_activation'),

    # ============================
    # 2FA – flux principal
    # ============================
    path('autentificare-2-factor/', views.TwoFactorView.as_view(), name='two_factor'),
    path('autentificare-2-factor/configurare/', views.two_factor_setup, name='two_factor_setup'),
    path('autentificare-2-factor/configurare/verificare/', views.two_factor_setup_verify, name='two_factor_setup_verify'),
    path('profil/2fa/coduri-backup/regenerare/', views.regenerate_backup_codes, name='regenerate_backup_codes'),

    # ============================
    # Resetare / schimbare parolă
    # ============================
    path('parola/resetare/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('parola/resetare/trimis/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('parola/resetare/confirmare/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('parola/resetare/finalizata/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('parola/modificare/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('parola/modificare/finalizata/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),

    # ============================
    # Profil – pagini principale
    # ============================
    path('profil/', views.profile, name='profile'),
    path('profil/date-personale/', views.profile_data, name='profile_data'),
    path('profil/securitate/', views.profile_security, name='profile_security'),

    # ============================
    # Profil – adrese
    # ============================
    path('profil/adrese/', views.address_list, name='address_list'),
    path('profil/adresa/adaugare/', views.address_form, name='address_form'),
    path('profil/adresa/<int:pk>/editare/', views.address_form, name='address_form'),
    path('profil/adresa/<int:pk>/stergere/', views.address_delete, name='address_delete'),

    # ============================
    # Profil – 2FA on/off
    # ============================
    path('profil/2fa/activare/', views.enable_2fa,  name='enable_2fa'),
    path('profil/2fa/dezactivare/', views.disable_2fa, name='disable_2fa'),

    # ============================
    # Profil – măsurători
    # ============================
    path('profil/dimensiuni/', views.profile_dimensions, name='profile_dimensions'),

    # ============================
    # 2FA – email, SMS + dispozitive de încredere
    # ============================
    path('profil/2fa/activare-email/', views.enable_2fa_email, name='enable_2fa_email'),
    path('profil/2fa/activare-sms/', views.enable_2fa_sms, name='enable_2fa_sms'),
    path('profil/securitate/dispozitiv/<int:pk>/revocare/', views.revoke_trusted_device, name='revoke_trusted_device'),

    # ============================
    # Seller – setări + locații
    # ============================
    path('profil/vanzator/', views.seller_settings, name='seller_settings'),
    path('profil/vanzator/locatie/adaugare/', views.seller_location_add, name='seller_location_add'),
    path('profil/vanzator/locatie/<int:pk>/stergere/', views.seller_location_delete, name='seller_location_delete'),
    path('profil/vanzator/locatie/<int:pk>/implicita/', views.seller_location_make_default, name='seller_location_default'),

    # ============================
    # KYC – documente utilizator
    # ============================
    path('profil/kyc/', views.kyc_center, name='kyc_center'),
    path('profil/kyc/document/<int:pk>/stergere/', views.kyc_document_delete, name='kyc_document_delete'),

    # ============================
    # Ștergere cont
    # ============================
    path('profil/stergere/', views.delete_account_request, name='delete_account_request'),
    path('profil/stergere/confirmare/', views.delete_account_confirm, name='delete_account_confirm'),
]
