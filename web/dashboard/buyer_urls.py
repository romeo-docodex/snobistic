from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.buyer_dashboard_view, name='buyer_dashboard'),
]
