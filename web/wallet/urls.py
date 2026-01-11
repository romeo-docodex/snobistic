# wallet/urls.py
from django.urls import path

from . import views

app_name = "wallet"

urlpatterns = [
    path("", views.wallet_home, name="home"),
    path("tranzactii/", views.wallet_transactions, name="transactions"),

    path("alimentare/", views.wallet_topup, name="topup"),
    path("alimentare/succes/", views.wallet_topup_success, name="topup_success"),
    path("alimentare/anulare/", views.wallet_topup_cancel, name="topup_cancel"),

    path("retragere/", views.wallet_withdraw, name="withdraw"),

    # webhook dedicat wallet
    path("stripe/webhook/", views.stripe_webhook_wallet, name="stripe_webhook"),
]
