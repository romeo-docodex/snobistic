from django.db import models
from django.conf import settings
from django.utils import timezone

class AuthRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'În așteptare'
        SUCCESS = 'success', 'Procesată'
        FAILED  = 'failed',  'Eșuată'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='auth_requests'
    )
    email = models.EmailField(blank=True)  # for guests
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)

    def __str__(self):
        return f"AuthRequest #{self.pk} ({self.get_status_display()})"


class AuthImage(models.Model):
    auth_request = models.ForeignKey(
        AuthRequest,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='auth_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image {self.pk} for AuthRequest {self.auth_request_id}"
