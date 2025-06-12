from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # 1. Pagina de checkout (alegere metodă)
    path('checkout/<int:order_id>/', views.checkout_payment_view, name='payment_checkout'),

    # 2. Redirect către procesator (Stripe / Plati.ro / manual)
    path('redirect/<int:order_id>/<str:method>/', views.payment_redirect_view, name='payment_redirect'),

    # 3. Succes / Eșec
    path('success/', views.payment_success_view, name='payment_success'),
    path('fail/', views.payment_fail_view, name='payment_fail'),

    # 4. Webhook endpoint
    path('webhook/', views.payment_webhook_view, name='payment_webhook'),
]
