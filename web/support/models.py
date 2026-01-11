# support/models.py
from __future__ import annotations

from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Nou"
        IN_PROGRESS = "in_progress", "În lucru"
        AWAITING_USER = "awaiting_user", "Așteaptă răspuns utilizator"
        RESOLVED = "resolved", "Rezolvat"
        REJECTED = "rejected", "Respins"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Category(models.TextChoices):
        GENERAL = "general", "General"
        ORDER = "order", "Comandă"
        RETURN = "return", "Retur"
        PAYMENT = "payment", "Plată / escrow"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
        help_text="Dacă tichetul este despre o comandă anume, leagă-l aici.",
    )
    return_request = models.ForeignKey(
        "orders.ReturnRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
        help_text="Dacă tichetul este despre un retur anume, leagă-l aici.",
    )

    subject = models.CharField(max_length=200)
    description = models.TextField()

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "status", "updated_at"]),
            models.Index(fields=["status", "priority", "created_at"]),
        ]

    def __str__(self) -> str:
        base = f"#{self.id} – {self.subject}"
        if self.order_id:
            base += f" (Order #{self.order_id})"
        return base

    @property
    def is_closed(self) -> bool:
        return self.status in {self.Status.RESOLVED, self.Status.REJECTED}

    @property
    def is_waiting_user(self) -> bool:
        return self.status == self.Status.AWAITING_USER


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_messages",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Msg by {self.author} on Ticket #{self.ticket.id}"
