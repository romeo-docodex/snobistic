# cart/urls.py
from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_view, name="cart"),
    path("adauga/<int:product_id>/", views.cart_add, name="add"),

    # ✅ endpoint curat pentru remove
    path("sterge/<int:item_id>/", views.cart_remove, name="remove"),

    # offcanvas partial
    path("mini-cos/", views.cart_offcanvas_partial, name="offcanvas"),

    # checkout
    path("finalizare-comanda/", views.checkout_view, name="checkout"),
    path("finalizare-comanda/succes/<int:order_id>/", views.checkout_success_view, name="checkout_success"),
    path("finalizare-comanda/anulata/", views.checkout_cancel_view, name="checkout_cancel"),
]
