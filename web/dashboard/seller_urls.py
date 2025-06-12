from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.seller_dashboard_view, name='seller_dashboard'),
]
