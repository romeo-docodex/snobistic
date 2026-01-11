# authenticator/urls.py
from django.urls import path

from . import views

app_name = "authenticator"

urlpatterns = [
    # Pagina principală de autentificare produs (generică)
    path("", views.authenticate_product_view, name="authenticate_product"),

    # Autentificare pornită dintr-un produs Snobistic
    path("produs/<slug:slug>/", views.authenticate_product_view, name="authenticate_product_for_product"),

    # Istoric verificări (logged in)
    path("istoric/", views.authenticate_history_view, name="authenticate_history"),

    # Guest status link
    path("status/<uuid:token>/", views.authenticate_status_view, name="authenticate_status"),

    # Download certificat (logged in)
    path("descarca-certificat/<int:pk>/", views.download_certificate_view, name="download_certificate"),

    # Download certificat (guest via token)
    path("status/<uuid:token>/certificat/", views.download_certificate_by_token_view, name="download_certificate_token"),

    # Webhook provider -> rezultat
    path("webhook/<str:provider>/", views.webhook_view, name="webhook"),
]
