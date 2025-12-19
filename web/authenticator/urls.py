from django.urls import path
from . import views

app_name = 'authenticator'

urlpatterns = [
    # Pagina principală de autentificare produs
    path('', views.authenticate_product_view, name='authenticate_product'),

    # Istoric verificări
    path('istoric/', views.authenticate_history_view, name='authenticate_history'),

    # Descărcare certificat
    path('descarca-certificat/<int:pk>/', views.download_certificate_view, name='download_certificate'),
]
