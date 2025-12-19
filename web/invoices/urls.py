# invoices/urls.py
from django.urls import path

from . import views

app_name = "invoices"

urlpatterns = [
    # /facturi/<pk>/  (presupunând că în urls.py principal vei avea ceva gen: path("facturi/", include("invoices.urls")))
    path("<int:pk>/", views.invoice_detail_view, name="invoice_detail"),

    # /facturi/<pk>/descarcare/
    path("<int:pk>/descarcare/", views.invoice_pdf_view, name="invoice_download"),
]
