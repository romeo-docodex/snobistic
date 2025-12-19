from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # /cos/  (presupunând că în urls.py principal ai ceva gen: path("cos/", include("cart.urls")))
    path('', views.cart_view, name='cart'),

    # /cos/adauga/<product_id>/
    path('adauga/<int:product_id>/', views.cart_add, name='add'),

    # /cos/mini-cos/  – offcanvas-ul pentru coș
    path('mini-cos/', views.cart_offcanvas_partial, name='offcanvas'),

    # /cos/finalizare-comanda/
    path('finalizare-comanda/', views.checkout_view, name='checkout'),

    # /cos/finalizare-comanda/succes/<order_id>/
    path('finalizare-comanda/succes/<int:order_id>/', views.checkout_success_view, name='checkout_success'),

    # /cos/finalizare-comanda/anulata/
    path('finalizare-comanda/anulata/', views.checkout_cancel_view, name='checkout_cancel'),
]
