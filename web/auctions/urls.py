from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    # Listare licitații
    path('', views.auction_list_view, name='auction_list'),

    # Detalii licitație (URL prietenos pe slug-ul produsului)
    path('<slug:product_slug>/', views.auction_detail_view, name='auction_detail'),

    # Plasare ofertă
    path('<slug:product_slug>/place-bid/', views.place_bid_view, name='place_bid'),

    # Închidere manuală licitație (staff/shopmanager)
    path('<slug:product_slug>/close/', views.close_auction_view, name='close_auction'),
]
