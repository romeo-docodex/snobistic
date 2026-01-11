# payments/urls.py
from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # STRIPE CHECKOUT pentru comenzi
    path("confirmare/<int:order_id>/", views.payment_confirm, name="payment_confirm"),
    path("succes/<int:order_id>/", views.payment_success, name="payment_success"),
    path("esec/<int:order_id>/", views.payment_failure, name="payment_failure"),

    # STRIPE WEBHOOK pentru payments (comenzi)
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
