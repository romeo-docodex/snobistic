# authenticator/models.py
from __future__ import annotations

import uuid
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuthRequest(models.Model):
    """
    O cerere de autentificare (ticket).
    Poate fi:
      - legată de un user (logged-in)
      - sau guest (email + public_token)
      - opțional legată de un produs Snobistic (catalog.Product)
    """

    class Status(models.TextChoices):
        PENDING = "pending", "În așteptare"
        SENT = "sent", "Trimisă către provider"
        SUCCESS = "success", "Finalizată"
        FAILED = "failed", "Eșuată"

    class Verdict(models.TextChoices):
        PENDING = "pending", "În evaluare"
        AUTHENTIC = "authentic", "Autentic"
        FAKE = "fake", "Neautentic"
        INCONCLUSIVE = "inconclusive", "Neconcludent"

    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)


    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="auth_requests",
    )
    email = models.EmailField(blank=True)  # for guests

    # Optional: link to a Snobistic product
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auth_requests",
    )

    # Details entered by user
    brand_text = models.CharField(max_length=120, default="")
    model_text = models.CharField(max_length=160, default="")
    serial_number = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    verdict = models.CharField(max_length=16, choices=Verdict.choices, default=Verdict.PENDING, db_index=True)

    # Provider integration
    provider = models.CharField(max_length=60, blank=True, db_index=True)
    provider_reference = models.CharField(max_length=120, blank=True, db_index=True)

    # Certificate (either file stored locally, or external link, or both)
    certificate_file = models.FileField(upload_to="certificates/", null=True, blank=True, max_length=255)
    certificate_url = models.URLField(blank=True)

    failure_reason = models.TextField(blank=True)
    provider_payload = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["status", "submitted_at"]),
            models.Index(fields=["provider", "provider_reference"]),
        ]

    def __str__(self) -> str:
        return f"AuthRequest #{self.pk} ({self.get_status_display()})"

    @property
    def contact_email(self) -> str:
        if self.user_id and getattr(self.user, "email", ""):
            return self.user.email
        return self.email

    @property
    def is_decided(self) -> bool:
        return self.verdict in {self.Verdict.AUTHENTIC, self.Verdict.FAKE, self.Verdict.INCONCLUSIVE}

    @property
    def is_success(self) -> bool:
        return self.status == self.Status.SUCCESS and self.is_decided

    def mark_sent(self, *, provider: str, provider_reference: str, payload: Optional[dict] = None) -> None:
        self.status = self.Status.SENT
        self.provider = provider or self.provider
        self.provider_reference = provider_reference or self.provider_reference
        self.sent_at = timezone.now()
        if payload is not None:
            self.provider_payload = payload

    def finalize(
        self,
        *,
        verdict: str,
        certificate_url: str = "",
        certificate_file=None,
        payload: Optional[dict] = None,
        failure_reason: str = "",
    ) -> None:
        """
        Setează verdict-ul final și atașează certificatul.
        """
        self.verdict = verdict
        self.status = self.Status.SUCCESS if verdict in {
            self.Verdict.AUTHENTIC, self.Verdict.FAKE, self.Verdict.INCONCLUSIVE
        } else self.Status.FAILED

        self.decided_at = timezone.now()
        self.failure_reason = failure_reason or ""

        if certificate_url:
            self.certificate_url = certificate_url

        if certificate_file is not None:
            self.certificate_file = certificate_file

        if payload is not None:
            self.provider_payload = payload


class AuthImage(models.Model):
    auth_request = models.ForeignKey(AuthRequest, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="auth_images/", max_length=255)
    position = models.PositiveIntegerField(default=0, db_index=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"Image {self.pk} for AuthRequest {self.auth_request_id}"


class ProductAuthentication(models.Model):
    """
    Starea finală de autentificare pentru un produs Snobistic.
    product.authentication -> folosit direct în Product.has_authentication_badge (deja ai property).
    """

    class Verdict(models.TextChoices):
        PENDING = "pending", "În evaluare"
        AUTHENTIC = "authentic", "Autentic"
        FAKE = "fake", "Neautentic"
        INCONCLUSIVE = "inconclusive", "Neconcludent"

    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="authentication",
    )

    is_verified = models.BooleanField(default=False, db_index=True)
    verdict = models.CharField(max_length=16, choices=Verdict.choices, default=Verdict.PENDING, db_index=True)

    provider = models.CharField(max_length=60, blank=True, db_index=True)
    provider_reference = models.CharField(max_length=120, blank=True, db_index=True)

    certificate_file = models.FileField(upload_to="certificates/", null=True, blank=True, max_length=255)
    certificate_url = models.URLField(blank=True)

    verified_at = models.DateTimeField(null=True, blank=True)

    last_auth_request = models.ForeignKey(
        AuthRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_to_products",
    )

    raw_payload = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-verified_at", "-id"]

    def __str__(self) -> str:
        return f"ProductAuthentication(product_id={self.product_id}, verified={self.is_verified})"

    def apply_from_request(self, req: AuthRequest) -> None:
        """
        Sincronizează starea produsului dintr-un AuthRequest finalizat.
        """
        self.last_auth_request = req
        self.provider = req.provider
        self.provider_reference = req.provider_reference
        self.raw_payload = req.provider_payload

        self.verdict = req.verdict
        self.is_verified = (req.verdict == AuthRequest.Verdict.AUTHENTIC)

        # prefer both if available
        self.certificate_url = req.certificate_url or self.certificate_url
        if req.certificate_file:
            self.certificate_file = req.certificate_file

        self.verified_at = req.decided_at or timezone.now()
