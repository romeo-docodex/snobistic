from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.shopmanager_dashboard_view, name='shopmanager_dashboard'),
]
