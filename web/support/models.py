from django.db import models
from django.conf import settings
from django.utils import timezone


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Deschis'),
        ('in_progress', 'În curs'),
        ('closed', 'Închis'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    attachment = models.FileField(upload_to='support_attachments/', blank=True, null=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_tickets',
        null=True, blank=True
    )

    def __str__(self):
        return f"#{self.pk} - {self.subject} ({self.get_status_display()})"
