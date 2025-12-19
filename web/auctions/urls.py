# auctions/urls.py
from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    # Listă licitații: /licitatii/
    path('', views.auction_list_view, name='auction_list'),

    # Detalii licitație: /licitatii/detalii/123/
    path('detalii/<int:pk>/', views.auction_detail_view, name='auction_detail'),

    # Plasare bid: /licitatii/detalii/123/liciteaza/
    path('detalii/<int:pk>/liciteaza/', views.place_bid_view, name='place_bid'),

    # Închidere licitație (owner): /licitatii/<slug-produs>/inchide/
    path('<slug:product_slug>/inchide/', views.close_auction_view, name='close_auction'),

    # ► PRODUS NOU pentru licitație (Step 0)
    # /licitatii/start/produs-nou/
    path('start/produs-nou/', views.auction_start_new_product, name='start_new_auction'),

    # ► licitație pe PRODUS EXISTENT (owner-only)
    # /licitatii/creare/<slug-produs>/
    path('creare/<slug:product_slug>/', views.auction_step1_metadata, name='create_auction'),

    # Pașii 2–5 ai licitației:
    # /licitatii/creare/pasul-2/123/
    path('creare/pasul-2/<int:pk>/', views.auction_step2_size, name='step2_size'),
    # /licitatii/creare/pasul-3/123/
    path('creare/pasul-3/<int:pk>/', views.auction_step3_dimensions, name='step3_dimensions'),
    # /licitatii/creare/pasul-4/123/
    path('creare/pasul-4/<int:pk>/', views.auction_step4_materials_description, name='step4_materials_description'),
    # /licitatii/creare/pasul-5/123/
    path('creare/pasul-5/<int:pk>/', views.auction_step5_auction_settings, name='step5_auction_settings'),
]
