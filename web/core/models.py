# core/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteSetting(models.Model):
    """
    Setări globale site (singleton-ish).
    Pentru SEO default + config general.
    """
    site_name = models.CharField(max_length=120, default="Snobistic")

    default_meta_title = models.CharField(
        max_length=160,
        blank=True,
        default="Snobistic – Marketplace fashion autentic",
    )
    default_meta_description = models.CharField(
        max_length=320,
        blank=True,
        default="Snobistic este marketplace-ul de fashion autentic, cu magazin, licitații, autentificare produse și plăți în siguranță.",
    )
    default_meta_robots = models.CharField(
        max_length=200,
        blank=True,
        default="index, follow, max-snippet:-1, max-image-preview:large",
    )

    contact_email = models.EmailField(blank=True, default="support@snobistic.ro")

    # versiune politică privacy (pentru audit GDPR)
    privacy_policy_version = models.CharField(max_length=32, blank=True, default="1.0")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return f"SiteSetting({self.site_name})"


class PageSEO(models.Model):
    """
    SEO per pagină statică / cheie logică.
    (Produsele/categoriile/licitatiile ar trebui să aibă SEO în app-urile lor.)
    """
    key = models.CharField(max_length=80, unique=True)  # ex: core:home, core:about
    meta_title = models.CharField(max_length=160, blank=True, default="")
    meta_description = models.CharField(max_length=320, blank=True, default="")
    meta_robots = models.CharField(max_length=200, blank=True, default="")
    canonical_path = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Ex: /despre-noi/ (fără domeniu). Dacă e gol, folosim request.build_absolute_uri",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Page SEO"
        verbose_name_plural = "Page SEO"

    def __str__(self):
        return self.key


class ContactMessage(models.Model):
    """
    Mesaje trimise prin formularul de contact.
    Le păstrăm pentru audit, follow-up și context la suport.
    """
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()

    # GDPR / audit
    consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    privacy_policy_version = models.CharField(max_length=32, blank=True, default="")

    # meta info
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # dacă user-ul era logat
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_messages",
    )

    # pentru suport
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_contact_messages",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["is_processed", "-created_at"]),
            models.Index(fields=["email", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.subject} – {self.email}"

    def mark_processed(self, by_user=None):
        self.is_processed = True
        self.processed_at = timezone.now()
        if by_user:
            self.processed_by = by_user
        self.save(update_fields=["is_processed", "processed_at", "processed_by"])
