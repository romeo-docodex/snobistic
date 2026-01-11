# messaging/admin.py
from django.contrib import admin

from .models import Conversation, Message, ConversationReadState, MessageAttachment


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "kind", "order_id", "support_user", "allow_staff",
        "is_closed", "closed_at", "closed_by",
        "participants_list", "last_updated",
    )
    list_filter = ("kind", "allow_staff", "is_closed", "last_updated")
    search_fields = ("participants__email", "participants__first_name", "participants__last_name", "support_user__email")
    filter_horizontal = ("participants",)
    autocomplete_fields = ("support_user", "order", "closed_by")

    def participants_list(self, obj):
        return ", ".join(
            (getattr(u, "full_name", "").strip() or getattr(u, "email", ""))
            for u in obj.participants.all()
        )

    participants_list.short_description = "Participanți"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "short_text", "sent_at", "attachments_count")
    search_fields = ("sender__email", "text")
    list_filter = ("sent_at",)
    autocomplete_fields = ("conversation", "sender")

    def short_text(self, obj):
        txt = (obj.text or "").strip()
        return (txt[:50] + "…") if len(txt) > 50 else txt

    def attachments_count(self, obj):
        return obj.attachments.count()

    short_text.short_description = "Mesaj"
    attachments_count.short_description = "Atașamente"


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "original_name", "content_type", "size_bytes", "created_at")
    search_fields = ("original_name", "content_type", "message__sender__email")
    list_filter = ("content_type", "created_at")
    autocomplete_fields = ("message",)


@admin.register(ConversationReadState)
class ConversationReadStateAdmin(admin.ModelAdmin):
    list_display = (
        "id", "conversation", "user", "last_read_at", "is_archived",
        "is_muted", "muted_until", "left_at", "updated_at",
    )
    search_fields = ("user__email",)
    list_filter = ("is_archived", "is_muted", "last_read_at", "updated_at")
    autocomplete_fields = ("conversation", "user")
