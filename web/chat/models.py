from django.db import models
from django.conf import settings
from django.utils import timezone


class ChatSession(models.Model):
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_user1')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_user2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user1', 'user2')
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat: {self.user1.email} ↔ {self.user2.email}"

    def get_other_user(self, current_user):
        return self.user2 if self.user1 == current_user else self.user1

    def has_unread_messages(self, user):
        return self.messages.filter(receiver=user, is_read=False).exists()


def chat_attachment_path(instance, filename):
    return f"chat_attachments/{instance.session.id}/{filename}"


class Message(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to=chat_attachment_path, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Mesaj de la {self.sender.email} către {self.receiver.email} @ {self.timestamp:%H:%M %d-%m}"
