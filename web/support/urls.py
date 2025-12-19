from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # Coada de chat live suport: /suport/chat/
    path('chat/', views.chat_queue, name='chat_queue'),

    # Listă tichete: /suport/tichete/
    path('tichete/', views.tickets_list, name='tickets_list'),

    # Creare tichet: /suport/tichete/creare/
    path('tichete/creare/', views.ticket_create, name='ticket_create'),

    # Detaliu tichet: /suport/tichete/<id>/
    path('tichete/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),

    # Editare tichet: /suport/tichete/<id>/editare/
    path('tichete/<int:ticket_id>/editare/', views.ticket_update, name='ticket_update'),
]
