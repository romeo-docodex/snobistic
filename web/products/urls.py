from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Catalog & Filtrare
    path('', views.product_list_view, name='product_list'),

    # Shop-manager
    path('pending/', views.pending_products_view, name='pending_products'),
    path('pending/<int:product_id>/', views.validate_product_view, name='validate_product'),

    # Adaugă produs
    path('adauga/store/', views.add_product_store_view, name='add_product_store'),
    path('adauga/licitatie/', views.add_product_auction_view, name='add_product_auction'),

    # Încărcare dovadă
    path('certificat/<int:product_id>/', views.upload_proof_view, name='upload_proof'),

    # Raportare
    path('raporteaza/<int:product_id>/', views.report_product_view, name='report_product'),

    # Detalii
    path('<slug:slug>/', views.product_detail_view, name='product_detail'),
]
