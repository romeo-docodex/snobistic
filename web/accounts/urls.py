from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate'),
    path('resend-activation/', views.resend_activation_view, name='resend_activation'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('2fa/', views.two_factor_view, name='two_factor'),

    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('change-email/', views.change_email_view, name='change_email'),
    path('delete-account/', views.account_deletion_view, name='delete_account'),

    path('address/delete/<int:address_id>/', views.delete_address_view, name='delete_address'),
    path('address/set-default/<int:address_id>/', views.set_default_address_view, name='set_default_address'),

    # Reset parolă
    path('reset-password/', auth_views.PasswordResetView.as_view(
        template_name='accounts/passwords/password_reset_form.html',
        email_template_name='accounts/passwords/password_reset_email.html',
        subject_template_name='accounts/passwords/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done')
    ), name='password_reset'),
    path('reset-password/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/passwords/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/passwords/password_reset_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete')
    ), name='password_reset_confirm'),
    path('reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/passwords/password_reset_complete.html'
    ), name='password_reset_complete'),
]
