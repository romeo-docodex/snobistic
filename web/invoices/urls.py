# invoices/urls.py
from django.urls import path
from . import views

app_name = "invoices"

urlpatterns = [
    # listări
    path("", views.invoice_list_my_view, name="my_invoices"),
    path("comision/", views.invoice_list_commission_view, name="commission_invoices"),

    # detail + pdf
    path("<int:pk>/", views.invoice_detail_view, name="invoice_detail"),
    path("<int:pk>/descarcare/", views.invoice_pdf_view, name="invoice_download"),

    # workflow
    path("<int:pk>/emite/", views.invoice_issue_view, name="invoice_issue"),
    path("<int:pk>/anuleaza/", views.invoice_cancel_view, name="invoice_cancel"),
    path("<int:pk>/storno/", views.invoice_credit_note_create_view, name="invoice_credit_note"),
]
