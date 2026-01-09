# accounts/models.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.functions import Lower
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.templatetags.static import static
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField


# -----------------------------
# Trust score thresholds (single source of truth)
# -----------------------------
TRUST_A_MIN = 85
TRUST_B_MIN = 70
TRUST_C_MIN = 50

SCORE_MIN = 0
SCORE_MAX = 100


def _trust_class(score: int) -> str:
    score = int(score or 0)
    if score >= TRUST_A_MIN:
        return "A"
    if score >= TRUST_B_MIN:
        return "B"
    if score >= TRUST_C_MIN:
        return "C"
    return "D"


# -----------------------------
# Seller tier thresholds (single source of truth)
# -----------------------------
SELLER_TIER_THRESHOLDS_NET_RON = {
    "AMATOR": Decimal("0"),
    "RISING": Decimal("3000"),
    "TOP": Decimal("15000"),
    "VIP": Decimal("50000"),
}

SELLER_COMMISSION_BY_TIER = {
    "AMATOR": Decimal("9.00"),
    "RISING": Decimal("8.00"),
    "TOP": Decimal("7.00"),
    "VIP": Decimal("6.00"),
}


# =============================================================================
# KYC policy (enterprise defaults)
# =============================================================================
KYC_REQUIRED_DOC_TYPES_PRIVATE = ("ID_CARD", "PROOF_OF_ADDRESS")
KYC_REQUIRED_DOC_TYPES_COMPANY = ("ID_CARD", "PROOF_OF_ADDRESS", "COMPANY_REG")


# -----------------------------
# User
# -----------------------------
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email trebuie furnizat")

        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser trebuie să aibă is_staff=True")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser trebuie să aibă is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    # NOTE:
    # - Păstrăm EmailField(unique=True) pentru compatibilitate/migrări.
    # - Unicitatea CI e întărită de UniqueConstraint(Lower("email")) + normalizare în save().
    email = models.EmailField("email", unique=True)
    first_name = models.CharField("prenume", max_length=30)
    last_name = models.CharField("nume", max_length=30)
    date_joined = models.DateTimeField(default=timezone.now)

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    # ✅ Legacy flag only (admin-friendly). Must be DERIVED from Profile.role_seller.
    is_seller = models.BooleanField("este vânzător", default=False)

    referral_code = models.CharField(
        "cod referral",
        max_length=20,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Cod unic folosit pentru programul de recomandări.",
    )
    referred_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_users",
        verbose_name="recomandat de",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    class Meta:
        ordering = ["-date_joined"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
            models.UniqueConstraint(
                Lower("referral_code"),
                condition=~models.Q(referral_code=""),
                name="uniq_user_referral_code_ci",
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @classmethod
    def _generate_referral_code(cls, length: int = 8) -> str:
        prefix = "SNB-"
        while True:
            code = (prefix + get_random_string(length).upper()).strip()
            if not cls.objects.filter(referral_code__iexact=code).exists():
                return code

    # ✅ PAS 7(4): referral anti-loop (self + A↔B minim)
    def clean(self):
        super().clean()

        # self-referral block
        if self.referred_by_id:
            if self.pk and self.referred_by_id == self.pk:
                raise ValidationError({"referred_by": _("Nu te poți recomanda pe tine însuți.")})

            # A↔B two-cycle block: A.referred_by=B AND B.referred_by=A
            if self.pk and CustomUser.objects.filter(pk=self.referred_by_id, referred_by_id=self.pk).exists():
                raise ValidationError({"referred_by": _("Referral invalid (loop A↔B).")})

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        if self.referral_code:
            self.referral_code = self.referral_code.strip().upper()

        if not self.pk and not self.referral_code:
            self.referral_code = self._generate_referral_code()

        # ✅ Enforcement:
        # Never allow manual drift: if profile exists, force is_seller to match truth.
        if self.pk:
            try:
                prof = getattr(self, "profile", None)
                if prof is None:
                    prof = Profile.objects.filter(user=self).only("role_seller").first()
                if prof is not None:
                    self.is_seller = bool(getattr(prof, "role_seller", False))
            except Exception:
                pass

        # PAS 7(4): make clean() effective even outside ModelForms
        try:
            self.full_clean()
        except ValidationError:
            raise

        super().save(*args, **kwargs)


# -----------------------------
# Profile
# -----------------------------
class Profile(models.Model):
    TWOFA_METHODS = (
        ("NONE", "Nicio metodă"),
        ("TOTP", "Aplicație (TOTP)"),
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
    )

    KYC_STATUS_CHOICES = (
        ("NOT_STARTED", "Neînceput"),
        ("IN_REVIEW", "În verificare"),
        ("NEEDS_MORE_INFO", "Necesită informații suplimentare"),
        ("APPROVED", "Aprobat"),
        ("REJECTED", "Respins"),
    )

    PHONE_VERIFY_STATUS = (
        ("UNVERIFIED", "Neverificat"),
        ("PENDING", "În verificare"),
        ("VERIFIED", "Verificat"),
        ("FAILED", "Eșuat"),
    )

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")

    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, verbose_name="Poză profil")

    # 2FA
    two_factor_enabled = models.BooleanField("2FA activ", default=False)
    two_factor_method = models.CharField(max_length=10, choices=TWOFA_METHODS, default="NONE")
    totp_secret = models.CharField(max_length=64, blank=True)

    backup_codes = models.JSONField(default=list, blank=True)
    last_2fa_at = models.DateTimeField(null=True, blank=True)

    phone = PhoneNumberField("telefon", region="RO", blank=True)
    phone_verification_status = models.CharField(
        "status verificare telefon",
        max_length=12,
        choices=PHONE_VERIFY_STATUS,
        default="UNVERIFIED",
    )
    phone_verified_at = models.DateTimeField("telefon verificat la", null=True, blank=True)

    date_of_birth = models.DateField("data nașterii", null=True, blank=True)

    is_company = models.BooleanField("persoană juridică", default=False)
    company_vat = models.CharField("CUI/TVA", max_length=50, blank=True)
    company_name = models.CharField("nume firmă", max_length=255, blank=True)
    company_address = models.CharField("adresă firmă", max_length=255, blank=True)
    company_iban = models.CharField("IBAN firmă", max_length=34, blank=True)
    vat_payer = models.BooleanField("plătitor TVA", default=False)
    company_reg_number = models.CharField("număr înregistrare (RC)", max_length=50, blank=True)
    company_website = models.URLField("website firmă", blank=True)
    company_phone = PhoneNumberField("telefon firmă", region="RO", blank=True)
    company_contact_person = models.CharField("persoană de contact", max_length=120, blank=True)

    newsletter = models.BooleanField(default=True)
    marketing = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)

    # ✅ Roles (truth)
    role_buyer = models.BooleanField("rol cumpărător activ", default=True)
    role_seller = models.BooleanField("rol vânzător activ", default=False)
    seller_can_buy = models.BooleanField("vânzătorul poate cumpăra", default=True)

    # ✅ KYC cache (denormalized): MUST be synced from KycRequest.status
    kyc_status = models.CharField("status KYC", max_length=20, choices=KYC_STATUS_CHOICES, default="NOT_STARTED")
    kyc_approved_at = models.DateTimeField("KYC aprobat la", null=True, blank=True)

    buyer_trust_score = models.PositiveSmallIntegerField(
        "scor seriozitate cumpărător",
        default=50,
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
    )

    height_cm = models.PositiveSmallIntegerField("Înălțime (cm)", null=True, blank=True)
    weight_kg = models.DecimalField("Greutate (kg)", max_digits=5, decimal_places=1, null=True, blank=True)

    shoulders = models.CharField("Umeri", max_length=50, blank=True)
    bust = models.CharField("Bust", max_length=50, blank=True)
    waist = models.CharField("Talie", max_length=50, blank=True)
    hips = models.CharField("Șold", max_length=50, blank=True)
    length = models.CharField("Lungime", max_length=50, blank=True)
    sleeve = models.CharField("Mâneca", max_length=50, blank=True)
    inseam = models.CharField("Crac interior", max_length=50, blank=True)
    outseam = models.CharField("Crac exterior", max_length=50, blank=True)

    buyer_bonus_kyc_applied = models.BooleanField(default=False)
    buyer_bonus_2fa_applied = models.BooleanField(default=False)

    def __str__(self):
        return f"Profil {self.user.email}"

    @property
    def avatar_url(self) -> str:
        if self.avatar:
            try:
                return self.avatar.url
            except Exception:
                pass
        return static("images/placeholders/avatar-default.png")

    @property
    def buyer_trust_class(self) -> str:
        return _trust_class(self.buyer_trust_score or 0)

    @property
    def has_kyc_badge(self) -> bool:
        return self.kyc_status == "APPROVED"

    @property
    def is_seller_only(self) -> bool:
        return self.role_seller and not self.role_buyer

    @property
    def can_buy(self) -> bool:
        if self.role_seller and not self.role_buyer:
            return False
        if self.role_seller and not self.seller_can_buy:
            return False
        return self.role_buyer

    # -----------------------------
    # Backup codes (hashed) helpers
    # -----------------------------
    def set_backup_codes(self, raw_codes: Iterable[str], *, commit: bool = True) -> None:
        """
        Store ONLY hashes for backup codes.
        raw_codes should be shown to user ONCE (UI layer), then discarded.
        """
        hashes: list[str] = []
        for c in raw_codes or []:
            c = (c or "").strip()
            if c:
                hashes.append(make_password(c))
        self.backup_codes = hashes
        if commit:
            self.save(update_fields=["backup_codes"])

    def has_backup_code(self, raw_code: str) -> bool:
        raw_code = (raw_code or "").strip()
        if not raw_code:
            return False
        for h in (self.backup_codes or []):
            try:
                if check_password(raw_code, h):
                    return True
            except Exception:
                continue
        return False

    def consume_backup_code(self, raw_code: str, *, commit: bool = True) -> bool:
        """
        If the code matches, remove its hash and persist.
        """
        raw_code = (raw_code or "").strip()
        if not raw_code:
            return False

        hashes = list(self.backup_codes or [])
        kept: list[str] = []
        consumed = False
        for h in hashes:
            if not consumed:
                try:
                    if check_password(raw_code, h):
                        consumed = True
                        continue
                except Exception:
                    pass
            kept.append(h)

        if consumed:
            self.backup_codes = kept
            if commit:
                self.save(update_fields=["backup_codes"])
        return consumed

    def save(self, *args, **kwargs):
        """
        ✅ Seller source-of-truth enforcement:
        - Profile.role_seller is authoritative.
        - Keep CustomUser.is_seller synced as legacy flag (admin-friendly fallback).
        """
        # Normalize 2FA fields
        if not self.two_factor_enabled:
            if self.two_factor_method != "NONE":
                self.two_factor_method = "NONE"

        role_seller_truth = bool(self.role_seller)
        super().save(*args, **kwargs)

        try:
            if self.user_id:
                CustomUser.objects.filter(pk=self.user_id).exclude(is_seller=role_seller_truth).update(
                    is_seller=role_seller_truth
                )
        except Exception:
            pass


# -----------------------------
# Seller
# -----------------------------
class SellerProfile(models.Model):
    SELLER_TYPE_PRIVATE = "PRIVATE"
    SELLER_TYPE_PROFESSIONAL = "PROFESSIONAL"
    SELLER_TYPE_CHOICES = (
        (SELLER_TYPE_PRIVATE, "Private seller (persoană fizică)"),
        (SELLER_TYPE_PROFESSIONAL, "Professional seller (persoană juridică)"),
    )

    SELLER_LEVEL_AMATOR = "AMATOR"
    SELLER_LEVEL_RISING = "RISING"
    SELLER_LEVEL_TOP = "TOP"
    SELLER_LEVEL_VIP = "VIP"
    SELLER_LEVEL_CHOICES = (
        (SELLER_LEVEL_AMATOR, "Amator Seller"),
        (SELLER_LEVEL_RISING, "Rising Seller"),
        (SELLER_LEVEL_TOP, "Top Seller"),
        (SELLER_LEVEL_VIP, "VIP Seller"),
    )

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="sellerprofile")
    iban = models.CharField("IBAN", max_length=34, blank=True)

    seller_type = models.CharField(
        "tip vânzător",
        max_length=20,
        choices=SELLER_TYPE_CHOICES,
        default=SELLER_TYPE_PRIVATE,
    )
    seller_level = models.CharField(
        "nivel vânzător",
        max_length=20,
        choices=SELLER_LEVEL_CHOICES,
        default=SELLER_LEVEL_AMATOR,
        help_text="Amator / Rising / Top / VIP – pe baza volumului de vânzări.",
    )

    seller_trust_score = models.PositiveSmallIntegerField(
        "scor seriozitate vânzător",
        default=50,
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
        help_text="0–100, calculat din livrare, retururi din vina vânzătorului, rating etc.",
    )
    seller_commission_rate = models.DecimalField(
        "comision vânzător (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("9.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Comision aplicat vânzătorului (9 / 8 / 7 / 6 pentru Amator/Rising/Top/VIP).",
    )

    accept_cod = models.BooleanField(
        "acceptă plata ramburs",
        default=False,
        help_text="Dacă este activ, pot exista comenzi cu plata la livrare (în condițiile de risc).",
    )
    allow_local_pickup = models.BooleanField(
        "permite livrare locală / ridicare personală",
        default=False,
        help_text="Permite livrarea în același oraș / ~20km sau întâlnire fizică.",
    )
    local_delivery_radius_km = models.PositiveSmallIntegerField(
        "raza livrare locală (km)",
        default=20,
        help_text="Folosită pentru livrări locale (Uber/Glovo/meet-up).",
    )
    max_cod_value = models.DecimalField(
        "valoare maximă ramburs",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Limită opțională pentru valoarea comenzilor ramburs.",
    )

    lifetime_sales_net = models.DecimalField(
        "volum vânzări net (RON)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Volum vânzări folosit la determinarea nivelului (Amator/Rising/Top/VIP).",
    )

    seller_bonus_kyc_applied = models.BooleanField(default=False)
    seller_bonus_2fa_applied = models.BooleanField(default=False)

    def __str__(self):
        return f"Profil vânzător {self.user.email}"

    @property
    def default_location(self):
        return self.user.locations.filter(is_default=True).first()

    @property
    def seller_trust_class(self) -> str:
        return _trust_class(self.seller_trust_score or 0)

    @property
    def has_kyc_badge(self) -> bool:
        prof = getattr(self.user, "profile", None)
        return bool(prof and prof.kyc_status == "APPROVED")

    @staticmethod
    def _tier_for_sales(sales_net: Decimal) -> str:
        sales_net = Decimal(sales_net or "0")
        if sales_net >= SELLER_TIER_THRESHOLDS_NET_RON["VIP"]:
            return "VIP"
        if sales_net >= SELLER_TIER_THRESHOLDS_NET_RON["TOP"]:
            return "TOP"
        if sales_net >= SELLER_TIER_THRESHOLDS_NET_RON["RISING"]:
            return "RISING"
        return "AMATOR"

    def recompute_tier(self, *, commit: bool = True) -> bool:
        target_level = self._tier_for_sales(self.lifetime_sales_net)
        target_commission = SELLER_COMMISSION_BY_TIER.get(target_level, Decimal("9.00"))

        changed = False
        if self.seller_level != target_level:
            self.seller_level = target_level
            changed = True
        if Decimal(self.seller_commission_rate or "0") != Decimal(target_commission):
            self.seller_commission_rate = target_commission
            changed = True

        if changed and commit:
            self.save(update_fields=["seller_level", "seller_commission_rate"])
        return changed

    def save(self, *args, **kwargs):
        prof = getattr(self.user, "profile", None)
        if prof and prof.is_company and self.seller_type == self.SELLER_TYPE_PRIVATE:
            self.seller_type = self.SELLER_TYPE_PROFESSIONAL

        try:
            self.recompute_tier(commit=False)
        except Exception:
            pass

        super().save(*args, **kwargs)


class SellerLocation(models.Model):
    """
    ✅ PAS 7(5) DECIZIE: rămâne minimal (marker).
    Extinderea la “warehouse real” (adresă/program/contact) o facem ulterior într-un migration separat,
    ca să nu amestecăm schema-change cu hardening-ul de integritate.
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="locations")
    code = models.CharField(max_length=3, help_text="Cod 3 litere (ex: ORA)")
    label = models.CharField(max_length=64, blank=True, help_text="Denumire opțională (ex: Oradea)")
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "code"], name="uniq_user_loc_code"),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="uniq_default_loc_per_user",
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = (self.code or "").upper()[:3]

        with transaction.atomic():
            if self.is_default and self.user_id:
                type(self).objects.select_for_update().filter(
                    user_id=self.user_id,
                    is_default=True,
                ).exclude(pk=self.pk).update(is_default=False)

            super().save(*args, **kwargs)

    def __str__(self):
        base = self.code or "LOC"
        return f"{base} – {self.label}" if self.label else base


# -----------------------------
# Audit events
# -----------------------------
class AccountEvent(models.Model):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAIL = "login_fail"
    TWOFA_SUCCESS = "2fa_success"
    TWOFA_FAIL = "2fa_fail"
    PASSWORD_CHANGE = "password_change"
    EMAIL_CHANGE_REQUEST = "email_change_request"
    EMAIL_CHANGE_CONFIRMED = "email_change_confirmed"

    EVENT_CHOICES = (
        (LOGIN_SUCCESS, "Login success"),
        (LOGIN_FAIL, "Login fail"),
        (TWOFA_SUCCESS, "2FA success"),
        (TWOFA_FAIL, "2FA fail"),
        (PASSWORD_CHANGE, "Password changed"),
        (EMAIL_CHANGE_REQUEST, "Email change requested"),
        (EMAIL_CHANGE_CONFIRMED, "Email change confirmed"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=64, choices=EVENT_CHOICES)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} – {self.event} @ {self.created_at:%Y-%m-%d %H:%M}"


# -----------------------------
# Legal acceptances
# -----------------------------
class LegalAcceptance(models.Model):
    DOC_TERMS = "TERMS"
    DOC_PRIVACY = "PRIVACY"
    DOC_COOKIES = "COOKIES"

    DOC_TYPE_CHOICES = (
        (DOC_TERMS, "Terms & Conditions"),
        (DOC_PRIVACY, "Privacy Policy"),
        (DOC_COOKIES, "Cookies Policy"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="legal_acceptances")
    doc_type = models.CharField(max_length=16, choices=DOC_TYPE_CHOICES)
    version = models.CharField(max_length=32)
    accepted_at = models.DateTimeField(auto_now_add=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-accepted_at"]
        indexes = [
            models.Index(fields=["user", "doc_type", "accepted_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "doc_type", "version"],
                name="uniq_legal_acceptance_user_doc_ver",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} accepted {self.doc_type} {self.version} @ {self.accepted_at:%Y-%m-%d %H:%M}"


# -----------------------------
# Trusted devices
# -----------------------------
class TrustedDevice(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="trusted_devices")
    token_hash = models.CharField(max_length=512, db_index=True)
    label = models.CharField(max_length=128, blank=True)
    user_agent = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["user", "token_hash"]),
            models.Index(fields=["expires_at"]),
        ]

    def matches(self, raw_token: str) -> bool:
        if not raw_token:
            return False
        return check_password(raw_token, self.token_hash)

    @classmethod
    def issue(cls, user, *, user_agent="", ip="", ttl_days=30, label=""):
        token = get_random_string(40)

        try:
            ttl_days = int(ttl_days)
        except Exception:
            ttl_days = 30
        ttl_days = max(1, min(ttl_days, 3650))

        obj = cls.objects.create(
            user=user,
            token_hash=make_password(token),
            user_agent=(user_agent or "")[:1024],
            ip=ip or None,
            label=(label or "")[:128],
            expires_at=timezone.now() + timedelta(days=ttl_days),
        )
        return obj, token


# -----------------------------
# Addresses
# -----------------------------
class Address(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="addresses")

    street_address = models.CharField("stradă și număr", max_length=255)
    building_info = models.CharField("bloc/scară/etaj", max_length=255, blank=True)
    city = models.CharField("oraș", max_length=100)
    region = models.CharField("județ/regiune", max_length=100)
    postal_code = models.CharField("cod poștal", max_length=20)
    country = CountryField("țară")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_billing = models.BooleanField("adresă de facturare", default=False)
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default_shipping=True),
                name="uniq_default_shipping_per_user",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default_billing=True),
                name="uniq_default_billing_per_user",
            ),

            # ✅ Address consistency at DB level (Django 5.x: condition=)
            models.CheckConstraint(
                condition=models.Q(is_default_billing=False) | models.Q(is_billing=True),
                name="addr_default_billing_requires_billing",
            ),
        ]


    # ✅ PAS 7(1): Address consistency in clean()
    def clean(self):
        super().clean()

        if self.is_default_billing and not self.is_billing:
            raise ValidationError(
                {"is_default_billing": _("O adresă implicită de billing trebuie să fie marcată ca billing.")}
            )

        if not self.is_billing and self.is_default_billing:
            # same as above, explicit per spec
            raise ValidationError({"is_billing": _("Dacă adresa nu e billing, nu poate fi implicită billing.")})

    def save(self, *args, **kwargs):
        # make clean() effective even outside ModelForms
        self.full_clean()

        with transaction.atomic():
            if self.user_id:
                if self.is_default_shipping:
                    type(self).objects.select_for_update().filter(
                        user_id=self.user_id,
                        is_default_shipping=True,
                    ).exclude(pk=self.pk).update(is_default_shipping=False)

                if self.is_default_billing:
                    type(self).objects.select_for_update().filter(
                        user_id=self.user_id,
                        is_default_billing=True,
                    ).exclude(pk=self.pk).update(is_default_billing=False)

            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.street_address}, {self.city}"


# -----------------------------
# KYC (request/case + documents)
# -----------------------------
class KycRequest(models.Model):
    STATUS_NOT_STARTED = "NOT_STARTED"
    STATUS_IN_REVIEW = "IN_REVIEW"
    STATUS_NEEDS_MORE_INFO = "NEEDS_MORE_INFO"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = (
        (STATUS_NOT_STARTED, "Neînceput"),
        (STATUS_IN_REVIEW, "În verificare"),
        (STATUS_NEEDS_MORE_INFO, "Necesită informații suplimentare"),
        (STATUS_APPROVED, "Aprobat"),
        (STATUS_REJECTED, "Respins"),
    )

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="kyc_request")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    reviewed_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kyc_reviews",
        help_text="Staff user care a făcut review-ul (dacă există).",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    internal_notes = models.JSONField(
        default=list,
        blank=True,
        help_text="Note structurate (listă de obiecte): {ts, author_id(optional), note}.",
    )
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f"KYC Request {self.user.email} ({self.status})"

    @property
    def required_doc_types(self) -> tuple[str, ...]:
        """
        ✅ PAS 7(3): required_doc_types dependent de Profile.is_company.
        """
        prof = getattr(self.user, "profile", None)
        if prof and bool(getattr(prof, "is_company", False)):
            return tuple(KYC_REQUIRED_DOC_TYPES_COMPANY)
        return tuple(KYC_REQUIRED_DOC_TYPES_PRIVATE)

    def missing_required_doc_types(self) -> list[str]:
        needed = set(self.required_doc_types)
        present = set(self.documents.all().values_list("document_type", flat=True))
        return sorted(list(needed - present))

    @property
    def has_all_required_documents(self) -> bool:
        return len(self.missing_required_doc_types()) == 0

    def add_note(self, note: str, *, author: CustomUser | None = None, commit: bool = True) -> None:
        note = (note or "").strip()
        if not note:
            return
        payload = {"ts": timezone.now().isoformat(), "note": note}
        if author and getattr(author, "pk", None):
            payload["author_id"] = str(author.pk)
        self.internal_notes = list(self.internal_notes or [])
        self.internal_notes.append(payload)
        if commit:
            self.save(update_fields=["internal_notes"])

    def sync_profile_status(self, *, commit: bool = True) -> None:
        prof = getattr(self.user, "profile", None)
        if not prof:
            return

        desired_status = self.status

        if desired_status == self.STATUS_APPROVED:
            desired_approved_at = prof.kyc_approved_at or timezone.now()
        else:
            desired_approved_at = None

        dirty = False
        if prof.kyc_status != desired_status:
            prof.kyc_status = desired_status
            dirty = True
        if prof.kyc_approved_at != desired_approved_at:
            prof.kyc_approved_at = desired_approved_at
            dirty = True

        if dirty and commit:
            prof.save(update_fields=["kyc_status", "kyc_approved_at"])

    def ensure_in_review_from_documents(self, *, commit: bool = True) -> None:
        if self.status in (self.STATUS_NOT_STARTED, self.STATUS_NEEDS_MORE_INFO):
            self.status = self.STATUS_IN_REVIEW
            if commit:
                self.save(update_fields=["status", "updated_at"])

    def save(self, *args, **kwargs):
        old_status = None
        if self.pk:
            old_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()

        super().save(*args, **kwargs)

        if old_status != self.status:
            try:
                self.sync_profile_status(commit=True)
            except Exception:
                pass


class KycDocument(models.Model):
    DOC_TYPE_ID_CARD = "ID_CARD"
    DOC_TYPE_PASSPORT = "PASSPORT"
    DOC_TYPE_DRIVING_LICENSE = "DRIVING_LICENSE"
    DOC_TYPE_PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    DOC_TYPE_COMPANY_REG = "COMPANY_REG"
    DOC_TYPE_OTHER = "OTHER"

    DOC_TYPE_CHOICES = (
        (DOC_TYPE_ID_CARD, "Carte de identitate / Buletin"),
        (DOC_TYPE_PASSPORT, "Pașaport"),
        (DOC_TYPE_DRIVING_LICENSE, "Permis de conducere"),
        (DOC_TYPE_PROOF_OF_ADDRESS, "Dovadă adresă (utilități / extras bancar etc.)"),
        (DOC_TYPE_COMPANY_REG, "Certificat înregistrare firmă / act constitutiv"),
        (DOC_TYPE_OTHER, "Alt document"),
    )

    STATUS_PENDING = "PENDING"
    STATUS_IN_REVIEW = "IN_REVIEW"
    STATUS_NEEDS_MORE_INFO = "NEEDS_MORE_INFO"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (STATUS_PENDING, "În așteptare"),
        (STATUS_IN_REVIEW, "În verificare"),
        (STATUS_NEEDS_MORE_INFO, "Necesită informații suplimentare"),
        (STATUS_APPROVED, "Aprobat"),
        (STATUS_REJECTED, "Respins"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="kyc_documents", verbose_name="utilizator")
    request = models.ForeignKey(KycRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")

    document_type = models.CharField("tip document", max_length=32, choices=DOC_TYPE_CHOICES)
    file = models.FileField("fișier", upload_to="kyc_documents/")
    status = models.CharField("status", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    is_primary = models.BooleanField(
        "document principal",
        default=False,
        help_text="Dacă este bifat, acest document va fi folosit ca referință principală în badge-uri și afișări.",
    )

    reference_code = models.CharField("cod referință intern", max_length=64, blank=True)
    notes = models.TextField("note interne", blank=True)
    rejection_reason = models.TextField("motiv respingere", blank=True)

    reviewed_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kyc_document_reviews",
        help_text="Staff user care a făcut review-ul documentului (dacă există).",
    )

    created_at = models.DateTimeField("încărcat la", auto_now_add=True)
    updated_at = models.DateTimeField("actualizat la", auto_now=True)
    reviewed_at = models.DateTimeField("revizuit la", null=True, blank=True)
    expires_at = models.DateTimeField("expiră la", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "document KYC"
        verbose_name_plural = "documente KYC"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_primary=True),
                name="uniq_primary_kyc_doc_per_user",
            )
        ]

    def __str__(self):
        return f"KYC {self.user.email} – {self.document_type} ({self.status})"

    # ✅ PAS 7(2): request/user integrity
    def clean(self):
        super().clean()
        if self.request_id and self.user_id and self.request.user_id != self.user_id:
            raise ValidationError({"request": _("Request-ul KYC aparține altui utilizator.")})

    def _touch_case_workflow_state(self, req: KycRequest) -> None:
        try:
            req.ensure_in_review_from_documents(commit=True)
        except Exception:
            pass

    def save(self, *args, **kwargs):
        # make clean() effective even outside ModelForms
        self.full_clean()

        req = None
        with transaction.atomic():
            # If request is missing, attach the canonical one for this user BEFORE saving
            if not self.request_id and self.user_id:
                req, _ = KycRequest.objects.get_or_create(user_id=self.user_id)
                self.request = req
            else:
                req = self.request

            if self.is_primary and self.user_id:
                type(self).objects.select_for_update().filter(
                    user_id=self.user_id,
                    is_primary=True,
                ).exclude(pk=self.pk).update(is_primary=False)

            super().save(*args, **kwargs)

            if self.status in (self.STATUS_APPROVED, self.STATUS_REJECTED, self.STATUS_NEEDS_MORE_INFO) and not self.reviewed_at:
                now = timezone.now()
                type(self).objects.filter(pk=self.pk).update(reviewed_at=now)
                self.reviewed_at = now

        if req:
            self._touch_case_workflow_state(req)


# -----------------------------
# Enterprise missing pieces (models)
# -----------------------------
class EmailChangeRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_EXPIRED = "EXPIRED"

    STATUS_CHOICES = (
        (STATUS_PENDING, "În așteptare"),
        (STATUS_CONFIRMED, "Confirmat"),
        (STATUS_CANCELLED, "Anulat"),
        (STATUS_EXPIRED, "Expirat"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="email_change_requests")
    new_email = models.EmailField("email nou")
    token_hash = models.CharField(max_length=512, db_index=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["expires_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower("new_email"),
                condition=models.Q(status="PENDING"),
                name="uniq_pending_email_change_new_email_ci",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="PENDING"),
                name="uniq_pending_email_change_per_user",
            ),
        ]

    def matches(self, raw_token: str) -> bool:
        if not raw_token:
            return False
        return check_password(raw_token, self.token_hash)

    @classmethod
    def issue(
        cls,
        user: CustomUser,
        new_email: str,
        *,
        ttl_hours: int = 24,
        ip: str | None = None,
        user_agent: str = "",
    ):
        new_email = (new_email or "").strip().lower()
        ttl_hours = int(ttl_hours or 24)
        ttl_hours = max(1, min(ttl_hours, 24 * 14))

        token = get_random_string(48)

        obj = cls.objects.create(
            user=user,
            new_email=new_email,
            token_hash=make_password(token),
            ip=ip or None,
            user_agent=(user_agent or "")[:1024],
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
            status=cls.STATUS_PENDING,
        )
        return obj, token

    def mark_expired_if_needed(self, *, commit: bool = True) -> bool:
        if self.status != self.STATUS_PENDING:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            self.status = self.STATUS_EXPIRED
            if commit:
                self.save(update_fields=["status"])
            return True
        return False


class PhoneOTPChallenge(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_VERIFIED = "VERIFIED"
    STATUS_FAILED = "FAILED"
    STATUS_EXPIRED = "EXPIRED"

    STATUS_CHOICES = (
        (STATUS_PENDING, "În așteptare"),
        (STATUS_VERIFIED, "Verificat"),
        (STATUS_FAILED, "Eșuat"),
        (STATUS_EXPIRED, "Expirat"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="phone_otp_challenges")
    phone = PhoneNumberField("telefon", region="RO")
    code_hash = models.CharField(max_length=512)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=6)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @classmethod
    def issue(
        cls,
        user: CustomUser,
        phone,
        *,
        ttl_minutes: int = 10,
        code_len: int = 6,
        ip: str | None = None,
        user_agent: str = "",
    ):
        ttl_minutes = int(ttl_minutes or 10)
        ttl_minutes = max(2, min(ttl_minutes, 60))
        code_len = int(code_len or 6)
        code_len = max(4, min(code_len, 10))

        raw = get_random_string(code_len, allowed_chars="0123456789")
        obj = cls.objects.create(
            user=user,
            phone=phone,
            code_hash=make_password(raw),
            attempts=0,
            max_attempts=6,
            status=cls.STATUS_PENDING,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
            ip=ip or None,
            user_agent=(user_agent or "")[:1024],
        )
        return obj, raw

    def verify(self, raw_code: str, *, commit: bool = True) -> bool:
        if self.status != self.STATUS_PENDING:
            return False

        now = timezone.now()
        if self.expires_at <= now:
            self.status = self.STATUS_EXPIRED
            if commit:
                self.save(update_fields=["status"])
            return False

        raw_code = (raw_code or "").strip()
        try:
            ok = check_password(raw_code, self.code_hash)
        except Exception:
            ok = False

        if ok:
            self.status = self.STATUS_VERIFIED
            if commit:
                self.save(update_fields=["status"])
            return True

        self.attempts = int(self.attempts or 0) + 1
        if self.attempts >= int(self.max_attempts or 6):
            self.status = self.STATUS_FAILED

        if commit:
            self.save(update_fields=["attempts", "status"])
        return False


class TrustScoreEvent(models.Model):
    SUBJECT_BUYER = "BUYER"
    SUBJECT_SELLER = "SELLER"
    SUBJECT_CHOICES = (
        (SUBJECT_BUYER, "Buyer"),
        (SUBJECT_SELLER, "Seller"),
    )

    # Standardized reasons (extend as needed)
    REASON_ORDER_CANCELLED = "ORDER_CANCELLED"
    REASON_LATE_SHIPMENT = "LATE_SHIPMENT"
    REASON_CHARGEBACK = "CHARGEBACK"
    REASON_DISPUTE_WON = "DISPUTE_WON"
    REASON_DISPUTE_LOST = "DISPUTE_LOST"
    REASON_REFUND_ISSUED = "REFUND_ISSUED"
    REASON_RETURN_ABUSE = "RETURN_ABUSE"
    REASON_KYC_APPROVED = "KYC_APPROVED"
    REASON_KYC_REJECTED = "KYC_REJECTED"
    REASON_SELLER_SALE_REGISTERED = "SELLER_SALE_REGISTERED"
    REASON_MANUAL_ADJUST = "MANUAL_ADJUST"

    REASON_CHOICES = (
        (REASON_ORDER_CANCELLED, "Order cancelled"),
        (REASON_LATE_SHIPMENT, "Late shipment"),
        (REASON_CHARGEBACK, "Chargeback"),
        (REASON_DISPUTE_WON, "Dispute won"),
        (REASON_DISPUTE_LOST, "Dispute lost"),
        (REASON_REFUND_ISSUED, "Refund issued"),
        (REASON_RETURN_ABUSE, "Return abuse"),
        (REASON_KYC_APPROVED, "KYC approved"),
        (REASON_KYC_REJECTED, "KYC rejected"),
        (REASON_SELLER_SALE_REGISTERED, "Seller sale registered"),
        (REASON_MANUAL_ADJUST, "Manual adjustment"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="trust_events")
    subject = models.CharField(max_length=12, choices=SUBJECT_CHOICES)
    delta = models.SmallIntegerField()

    score_before = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
    )
    score_after = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)]
    )

    reason = models.CharField(max_length=32, choices=REASON_CHOICES)

    ref_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    ref_object_id = models.CharField(max_length=64, null=True, blank=True)
    ref_object = GenericForeignKey("ref_content_type", "ref_object_id")

    source_app = models.CharField(max_length=32, blank=True)
    source_event_id = models.CharField(max_length=64, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "subject", "created_at"]),
            models.Index(fields=["source_app", "source_event_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_app", "source_event_id"],
                condition=~models.Q(source_app="") & ~models.Q(source_event_id=""),
                name="uniq_trust_event_source_pair",
            )
        ]

    def __str__(self):
        return f"{self.user.email} {self.subject} {self.delta:+d} => {self.score_after} ({self.reason})"


# =============================================================================
# ✅ Signals: prevent contradictory seller states
# =============================================================================
@receiver(post_save, sender=CustomUser)
def _ensure_profile_and_sync_seller(sender, instance: CustomUser, created: bool, **kwargs):
    """
    Ensure Profile exists. Keep seller state consistent:
    - Source of truth stays Profile.role_seller.
    - On fresh user creation, if admin set is_seller=True, reflect into Profile.role_seller (once).
    - Always keep legacy flag aligned to Profile (truth).
    """
    try:
        prof, prof_created = Profile.objects.get_or_create(user=instance)

        if (created or prof_created) and bool(instance.is_seller) and not bool(prof.role_seller):
            prof.role_seller = True
            prof.save(update_fields=["role_seller"])

        truth = bool(prof.role_seller)
        if bool(instance.is_seller) != truth:
            CustomUser.objects.filter(pk=instance.pk).update(is_seller=truth)
    except Exception:
        pass
