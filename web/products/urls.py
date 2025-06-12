from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list_view, name='product_list'),
    path('adauga/store/', views.add_product_store_view, name='add_product_store'),
    path('adauga/licitație/', views.add_product_auction_view, name='add_product_auction'),
    path('certificat/<int:product_id>/', views.upload_proof_view, name='upload_proof'),
    path('raporteaza/<int:product_id>/', views.report_product_view, name='report_product'),

    # Shop Manager
    path('validare/', views.pending_products_view, name='pending_products'),
    path('validare/<int:product_id>/', views.validate_product_view, name='validate_product'),

    # Detalii produs (slug)
    path('<slug:slug>/', views.product_detail_view, name='product_detail'),
]
