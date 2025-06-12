from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # User
    path('', views.user_ticket_list_view, name='ticket_list'),
    path('nou/', views.create_ticket_view, name='create_ticket'),
    path('ticket/<int:ticket_id>/', views.ticket_detail_view, name='ticket_detail'),

    # Admin / Staff
    path('admin/', views.admin_ticket_list_view, name='admin_ticket_list'),
    path('admin/<int:ticket_id>/', views.admin_ticket_detail_view, name='admin_ticket_detail'),
]
