from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('', views.wallet_overview_view, name='wallet_overview'),
    path('istoric/', views.transaction_history_view, name='transaction_history'),
    path('alimentare/', views.topup_view, name='wallet_topup'),
    path('retragere/', views.payout_view, name='wallet_payout'),
]
