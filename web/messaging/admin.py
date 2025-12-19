# messaging/admin.py
from django.contrib import admin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "participants_list", "last_updated")
    search_fields = ("participants__email", "participants__first_name", "participants__last_name")
    filter_horizontal = ("participants",)

    def participants_list(self, obj):
        return ", ".join(
            (getattr(u, "full_name", "").strip() or u.email)
            for u in obj.participants.all()
        )
    participants_list.short_description = "Participanți"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "short_text", "sent_at")
    search_fields = ("sender__email", "text")
    list_filter = ("sent_at",)

    def short_text(self, obj):
        return (obj.text[:50] + "…") if len(obj.text) > 50 else obj.text
    short_text.short_description = "Mesaj"
