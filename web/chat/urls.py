from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('start/<int:user_id>/', views.start_chat_view, name='start_chat'),
    path('session/<int:session_id>/', views.chat_session_view, name='chat_session'),
]
