from django.db import models
from django.conf import settings
from django.utils import timezone


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations'
    )
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        names = ", ".join(
            (getattr(u, "full_name", "").strip() or u.email)
            for u in self.participants.all()
        )
        return f"Conv ({names})"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    text = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)
    attachment = models.FileField(upload_to='msg_attachments/', null=True, blank=True)

    def __str__(self):
        return f"Msg by {self.sender} @ {self.sent_at}"
