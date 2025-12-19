# payments/urls.py
from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # WALLET – portofel
    # /plati/portofel/alimentare/
    path("portofel/alimentare/", views.wallet_topup, name="wallet_topup"),

    # /plati/portofel/alimentare/succes/
    path(
        "portofel/alimentare/succes/",
        views.wallet_topup_success,
        name="wallet_topup_success",
    ),

    # /plati/portofel/alimentare/anulare/
    path(
        "portofel/alimentare/anulare/",
        views.wallet_topup_cancel,
        name="wallet_topup_cancel",
    ),

    # /plati/portofel/retragere/
    path("portofel/retragere/", views.wallet_withdraw, name="wallet_withdraw"),

    # STRIPE CHECKOUT pentru comenzi
    # /plati/confirmare/<order_id>/
    path("confirmare/<int:order_id>/", views.payment_confirm, name="payment_confirm"),

    # /plati/succes/<order_id>/
    path("succes/<int:order_id>/", views.payment_success, name="payment_success"),

    # /plati/esec/<order_id>/
    path("esec/<int:order_id>/", views.payment_failure, name="payment_failure"),

    # STRIPE WEBHOOK – îl lăsăm standard
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
