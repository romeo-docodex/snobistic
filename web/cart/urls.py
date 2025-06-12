from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path('', views.cart_detail_view, name='cart_detail'),
    path('adauga/', views.add_to_cart_view, name='add_to_cart'),
    path('actualizeaza/<int:item_id>/', views.update_cart_item_view, name='update_cart_item'),
    path('sterge/<int:item_id>/', views.remove_cart_item_view, name='remove_cart_item'),
]
