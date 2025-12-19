from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Listă comenzi: /comenzi/
    path('', views.order_list_view, name='order_list'),

    # Detaliu comandă: /comenzi/123/
    path('<int:pk>/', views.order_detail_view, name='order_detail'),

    # Export comenzi: /comenzi/exporta/
    path('exporta/', views.order_export_view, name='order_export'),

    # Retururi: /comenzi/retururi/
    path('retururi/', views.return_list_view, name='return_list'),

    # Cerere retur pentru o comandă: /comenzi/123/retur/
    path('<int:pk>/retur/', views.order_return_request_view, name='order_return_request'),

    # Factură: /comenzi/factura/<order_id>/<kind>/
    path(
        'factura/<int:order_id>/<str:kind>/',
        views.invoice_view,
        name='invoice',
    ),
]
