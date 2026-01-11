# messaging/urls.py
from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.conversation_list_view, name="conversation_list"),
    path("suport/", views.start_support_conversation_view, name="start_support"),
    path("comanda/<int:order_id>/", views.start_order_conversation_view, name="start_order_conversation"),
    path("<int:pk>/escaladeaza/", views.escalate_order_conversation_view, name="escalate_order"),
    path("<int:pk>/join/", views.staff_join_conversation_view, name="staff_join"),

    # ✅ attachments (controlat)
    path("atasament/<int:pk>/", views.attachment_serve_view, name="attachment"),

    # ✅ inbox actions (POST-only)
    path("<int:pk>/archive-toggle/", views.conversation_toggle_archive_view, name="archive_toggle"),
    path("<int:pk>/mute-toggle/", views.conversation_toggle_mute_view, name="mute_toggle"),
    path("<int:pk>/leave/", views.conversation_leave_view, name="leave"),
    path("<int:pk>/close/", views.conversation_close_view, name="close"),
    path("<int:pk>/reopen/", views.conversation_reopen_view, name="reopen"),

    path("<int:pk>/", views.conversation_detail_view, name="conversation_detail"),
]
