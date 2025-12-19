# logistics/urls.py
from django.urls import path

from . import views

app_name = "logistics"

urlpatterns = [
    path("awb/<int:order_id>/", views.generate_awb_view, name="generate_awb"),
]
