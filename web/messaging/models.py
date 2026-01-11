# messaging/models.py
from __future__ import annotations

import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import get_valid_filename

# ✅ Module-level constants (Meta can access these)
KIND_ORDER = "ORDER"
KIND_SUPPORT = "SUPPORT"


class Conversation(models.Model):
    KIND_ORDER = KIND_ORDER
    KIND_SUPPORT = KIND_SUPPORT

    KIND_CHOICES = [
        (KIND_ORDER, "Order (buyer ↔ seller)"),
        (KIND_SUPPORT, "Support (user ↔ staff)"),
    ]

    kind = models.CharField(
        max_length=12,
        choices=KIND_CHOICES,
        default=KIND_SUPPORT,
        db_index=True,
    )

    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="messaging_conversations",
    )

    support_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="support_conversations_started",
    )

    # ✅ NEW: conversatie per ticket (1:1)
    support_ticket = models.OneToOneField(
        "support.Ticket",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="conversation",
    )

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
        blank=True,
    )

    allow_staff = models.BooleanField(default=False, db_index=True)

    # ✅ marketplace-grade: close/reopen (în special pentru SUPPORT)
    is_closed = models.BooleanField(default=False, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_conversations",
    )

    created_at = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_updated"]
        indexes = [
            models.Index(fields=["kind", "last_updated"]),
            models.Index(fields=["allow_staff", "last_updated"]),
            models.Index(fields=["is_closed", "last_updated"]),
        ]
        constraints = [
            # ORDER: trebuie order, fără support_user / support_ticket
            # SUPPORT: trebuie support_user; support_ticket poate fi null (conversație generală) sau setat (per ticket)
            models.CheckConstraint(
                condition=(
                    Q(kind=KIND_ORDER, order__isnull=False, support_user__isnull=True, support_ticket__isnull=True)
                    | Q(kind=KIND_SUPPORT, order__isnull=True, support_user__isnull=False)
                ),
                name="conv_kind_requires_correct_link",
            ),
            # dacă ai support_ticket => obligatoriu kind SUPPORT
            models.CheckConstraint(
                condition=(Q(support_ticket__isnull=True) | Q(kind=KIND_SUPPORT)),
                name="support_ticket_requires_support_kind",
            ),
            # 1 conversație ORDER / comandă
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(kind=KIND_ORDER),
                name="uniq_order_conversation",
            ),
            # 1 conversație SUPPORT "generală" / user (support_ticket IS NULL)
            models.UniqueConstraint(
                fields=["support_user"],
                condition=Q(kind=KIND_SUPPORT, support_ticket__isnull=True),
                name="uniq_general_support_conversation_per_user",
            ),
            # 1 conversație SUPPORT / ticket
            models.UniqueConstraint(
                fields=["support_ticket"],
                condition=Q(kind=KIND_SUPPORT, support_ticket__isnull=False),
                name="uniq_support_ticket_conversation",
            ),
        ]

    def __str__(self) -> str:
        if self.kind == self.KIND_ORDER and self.order_id:
            return f"Conv ORDER (Order #{self.order_id})"
        if self.kind == self.KIND_SUPPORT:
            if self.support_ticket_id:
                return f"Conv SUPPORT (Ticket #{self.support_ticket_id})"
            if self.support_user_id:
                return f"Conv SUPPORT (User {self.support_user_id})"
        return f"Conversation #{self.pk}"

    def is_participant(self, user) -> bool:
        if not user or not getattr(user, "pk", None):
            return False
        return self.participants.filter(pk=user.pk).exists()

    def can_view(self, user) -> bool:
        if self.is_participant(user):
            return True
        return bool(getattr(user, "is_staff", False) and self.allow_staff)

    def touch(self, ts=None, *, commit: bool = True) -> None:
        ts = ts or timezone.now()
        self.last_updated = ts
        if commit:
            self.save(update_fields=["last_updated"])

    def close(self, by_user=None, *, ts=None, commit=True) -> None:
        ts = ts or timezone.now()
        self.is_closed = True
        self.closed_at = ts
        self.closed_by = by_user if getattr(by_user, "pk", None) else None
        if commit:
            self.save(update_fields=["is_closed", "closed_at", "closed_by"])

    def reopen(self, *, commit=True) -> None:
        self.is_closed = False
        self.closed_at = None
        self.closed_by = None
        if commit:
            self.save(update_fields=["is_closed", "closed_at", "closed_by"])


class ConversationReadState(models.Model):
    """
    Read + user state per (conversation, user).

    unread = messages from other people with sent_at > last_read_at

    marketplace-grade:
      - is_archived / archived_at
      - is_muted / muted_until
      - left_at (user "left" conversation)
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="read_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_read_states",
    )

    last_read_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ✅ inbox controls
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    is_muted = models.BooleanField(default=False, db_index=True)
    muted_until = models.DateTimeField(null=True, blank=True)

    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="uniq_conv_readstate_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "last_read_at"]),
            models.Index(fields=["conversation", "last_read_at"]),
            models.Index(fields=["user", "is_archived"]),
            models.Index(fields=["user", "is_muted"]),
            models.Index(fields=["user", "left_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"ReadState(conv={self.conversation_id}, user={self.user_id}, "
            f"last_read_at={self.last_read_at:%Y-%m-%d %H:%M})"
        )

    @property
    def is_muted_effective(self) -> bool:
        if self.is_muted:
            return True
        if self.muted_until and self.muted_until > timezone.now():
            return True
        return False


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )

    # allow attachment-only messages
    text = models.TextField(blank=True)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["sent_at"]
        indexes = [
            models.Index(fields=["conversation", "sent_at"]),
            models.Index(fields=["sender", "sent_at"]),
        ]

    def __str__(self) -> str:
        return f"Msg by {self.sender} @ {self.sent_at:%Y-%m-%d %H:%M}"

    @property
    def has_attachments(self) -> bool:
        return self.attachments.exists()


def _msg_attachment_upload_to(instance: "MessageAttachment", filename: str) -> str:
    """
    Storage path:
      msg_attachments/conv_<conversation_id>/<uuid>.<ext>
    """
    original = (filename or "").strip()
    original = os.path.basename(original)  # prevent path traversal
    original = get_valid_filename(original) or "file"

    ext = os.path.splitext(original)[1].lower()
    if not ext:
        ext = ".bin"

    conv_id = getattr(getattr(instance.message, "conversation", None), "id", None) or "x"
    new_name = f"{uuid.uuid4().hex}{ext}"
    return f"msg_attachments/conv_{conv_id}/{new_name}"


class MessageAttachment(models.Model):
    """
    Multi-attachments per message (poze + fișiere).
    Download/preview se face CONTROLAT via view, nu direct la /media/.
    """
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    file = models.FileField(upload_to=_msg_attachment_upload_to)

    # metadata (best-effort)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["message", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Attachment(msg={self.message_id}, name={self.original_name or self.file.name})"

    @property
    def is_image(self) -> bool:
        ct = (self.content_type or "").lower()
        if ct.startswith("image/"):
            return True
        # fallback by ext
        ext = os.path.splitext(self.original_name or self.file.name)[1].lower()
        return ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def save(self, *args, **kwargs):
        # Fill metadata (best-effort) before save
        if not self.original_name and getattr(self.file, "name", None):
            self.original_name = os.path.basename(self.file.name)[:255]

        f = getattr(self.file, "file", None)
        if f is not None and hasattr(f, "content_type"):
            self.content_type = (getattr(f, "content_type", "") or "")[:120]

        if not self.size_bytes:
            try:
                self.size_bytes = int(getattr(self.file, "size", 0) or 0)
            except Exception:
                self.size_bytes = 0

        super().save(*args, **kwargs)
