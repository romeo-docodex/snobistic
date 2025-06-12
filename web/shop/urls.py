from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('catalog/', views.catalog_view, name='catalog'),
    path('favorites/', views.favorites_view, name='favorites'),
    path('favorites/add/<int:product_id>/', views.add_to_favorites, name='add_to_favorites'),
    path('favorites/remove/<int:product_id>/', views.remove_from_favorites, name='remove_from_favorites'),
]
