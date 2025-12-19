from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Listă conversații: /mesaje/
    path('', views.conversation_list_view, name='conversation_list'),

    # Începe o conversație nouă: /mesaje/incepe/
    path('incepe/', views.start_conversation_view, name='start_conversation'),

    # Detalii conversație: /mesaje/123/
    path('<int:pk>/', views.conversation_detail_view, name='conversation_detail'),
]
