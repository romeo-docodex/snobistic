from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.hashers import make_password, check_password
from django.utils.crypto import get_random_string
from django.templatetags.static import static


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email trebuie furnizat')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser trebuie să aibă is_staff=True')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser trebuie să aibă is_superuser=True')
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField('email', unique=True)
    first_name = models.CharField('prenume', max_length=30)
    last_name = models.CharField('nume', max_length=30)
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_seller = models.BooleanField('este vânzător', default=False)

    # Program de recomandări
    referral_code = models.CharField(
        'cod referral',
        max_length=20,
        unique=True,
        blank=True,
        help_text='Cod unic folosit pentru programul de recomandări.'
    )
    referred_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='referred_users',
        verbose_name='recomandat de'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        # asigurăm cod referral unic la creare
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_referral_code(cls, length: int = 8) -> str:
        """
        Generează un cod referral unic, de forma:
        SNB-XXXXXXX.
        """
        prefix = "SNB-"
        while True:
            code = prefix + get_random_string(length).upper()
            if not cls.objects.filter(referral_code=code).exists():
                return code


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
        ("APPROVED", "Aprobat"),
        ("REJECTED", "Respins"),
    )

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")

    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        verbose_name="Poză profil"
    )

    # 2FA
    two_factor_enabled = models.BooleanField('2FA activ', default=False)
    two_factor_method = models.CharField(max_length=10, choices=TWOFA_METHODS, default="NONE")
    totp_secret = models.CharField(max_length=64, blank=True)  # setăm când activăm TOTP
    backup_codes = models.JSONField(default=list, blank=True)   # listă cu coduri unice
    last_2fa_at = models.DateTimeField(null=True, blank=True)

    # Date de contact & identitate
    phone = PhoneNumberField('telefon', region='RO', blank=True)
    date_of_birth = models.DateField('data nașterii', null=True, blank=True)

    # Persoană fizică / juridică + detalii firmă bogate
    is_company = models.BooleanField('persoană juridică', default=False)

    company_vat = models.CharField('CUI/TVA', max_length=50, blank=True)

    company_name = models.CharField(
        'nume firmă',
        max_length=255,
        blank=True,
        help_text='Denumirea comercială a companiei / PFA / SRL.'
    )
    company_address = models.CharField(
        'adresă firmă',
        max_length=255,
        blank=True,
        help_text='Adresă sediu social / punct de lucru pentru facturare.'
    )
    vat_payer = models.BooleanField(
        'plătitor TVA',
        default=False,
        help_text='Bifează dacă firma este înregistrată ca plătitoare de TVA.'
    )
    company_reg_number = models.CharField(
        'număr înregistrare (RC)',
        max_length=50,
        blank=True,
        help_text='Nr. registrul comerțului (ex: J05/123/2025).'
    )
    company_website = models.URLField(
        'website firmă',
        blank=True,
        help_text='Site-ul oficial al companiei (dacă există).'
    )
    company_phone = PhoneNumberField(
        'telefon firmă',
        region='RO',
        blank=True,
        help_text='Telefon de contact pentru firmă (dacă este diferit de telefonul personal).'
    )
    company_contact_person = models.CharField(
        'persoană de contact',
        max_length=120,
        blank=True,
        help_text='Nume persoană de contact pentru firmă (ex: administrator, responsabil vânzări).'
    )

    # Consimțământ marketing
    newsletter = models.BooleanField(default=True)
    marketing = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)

    # Roluri în platformă (business rule „seller vs buyer”)
    role_buyer = models.BooleanField(
        'rol cumpărător activ',
        default=True,
        help_text='Dacă este activ, utilizatorul poate cumpăra produse pe Snobistic.'
    )
    role_seller = models.BooleanField(
        'rol vânzător activ',
        default=False,
        help_text='Dacă este activ, utilizatorul are drept de listare ca vânzător.'
    )
    seller_can_buy = models.BooleanField(
        'vânzătorul poate cumpăra',
        default=True,
        help_text='Dacă este dezactivat, un cont de vânzător nu poate adăuga produse în coș.'
    )

    # KYC & seriozitate cumpărător
    kyc_status = models.CharField(
        'status KYC',
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default="NOT_STARTED",
    )
    kyc_approved_at = models.DateTimeField('KYC aprobat la', null=True, blank=True)

    buyer_trust_score = models.PositiveSmallIntegerField(
        'scor seriozitate cumpărător',
        default=50,
        help_text='0–100, calculat din activitate, retururi, incidente etc.'
    )

    # Dimensiuni generale (numeric – pentru matching mai precis)
    height_cm = models.PositiveSmallIntegerField(
        'Înălțime (cm)',
        null=True,
        blank=True,
        help_text='Folosește centimetri, ex: 170.'
    )
    weight_kg = models.DecimalField(
        'Greutate (kg)',
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text='Opțional; folosește kilograme, ex: 65.5.'
    )

    # Dimensiuni detaliate (stringuri „45 cm” cum folosești în form)
    shoulders = models.CharField('Umeri', max_length=50, blank=True)
    bust      = models.CharField('Bust',    max_length=50, blank=True)
    waist     = models.CharField('Talie',   max_length=50, blank=True)
    hips      = models.CharField('Șold',    max_length=50, blank=True)
    length    = models.CharField('Lungime', max_length=50, blank=True)
    sleeve    = models.CharField('Mâneca',  max_length=50, blank=True)
    inseam    = models.CharField('Crac interior', max_length=50, blank=True)
    outseam   = models.CharField('Crac exterior', max_length=50, blank=True)

    def __str__(self):
        return f'Profil {self.user.email}'

    @property
    def avatar_url(self) -> str:
        """
        URL pentru avatarul utilizatorului.
        Dacă nu există poză încărcată, întoarce un placeholder din static.
        """
        if self.avatar:
            try:
                return self.avatar.url
            except Exception:
                pass
        return static("images/placeholders/avatar-default.png")

    @property
    def buyer_trust_class(self) -> str:
        score = self.buyer_trust_score or 0
        if score >= 85:
            return "A"
        if score >= 70:
            return "B"
        if score >= 50:
            return "C"
        return "D"

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

    @property
    def primary_kyc_document(self):
        return self.user.kyc_documents.filter(status="APPROVED").order_by(
            "-reviewed_at", "-created_at"
        ).first()


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

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='sellerprofile')
    iban = models.CharField('IBAN', max_length=34, blank=True)

    # Tip & nivel vânzător
    seller_type = models.CharField(
        'tip vânzător',
        max_length=20,
        choices=SELLER_TYPE_CHOICES,
        default=SELLER_TYPE_PRIVATE,
    )
    seller_level = models.CharField(
        'nivel vânzător',
        max_length=20,
        choices=SELLER_LEVEL_CHOICES,
        default=SELLER_LEVEL_AMATOR,
        help_text="Amator / Rising / Top / VIP – pe baza volumului de vânzări."
    )

    # Scor & comision
    seller_trust_score = models.PositiveSmallIntegerField(
        'scor seriozitate vânzător',
        default=50,
        help_text='0–100, calculat din livrare, retururi din vina vânzătorului, rating etc.'
    )
    seller_commission_rate = models.DecimalField(
        'comision vânzător (%)',
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text='Comision aplicat vânzătorului (9 / 8 / 7 / 6 pentru Amator/Rising/Top/VIP).'
    )

    # Setări livrare & ramburs
    accept_cod = models.BooleanField(
        'acceptă plata ramburs',
        default=False,
        help_text='Dacă este activ, pot exista comenzi cu plata la livrare (în condițiile de risc).'
    )
    allow_local_pickup = models.BooleanField(
        'permite livrare locală / ridicare personală',
        default=False,
        help_text='Permite livrarea în același oraș / ~20km sau întâlnire fizică.'
    )
    local_delivery_radius_km = models.PositiveSmallIntegerField(
        'raza livrare locală (km)',
        default=20,
        help_text='Folosită pentru livrări locale (Uber/Glovo/meet-up).'
    )
    max_cod_value = models.DecimalField(
        'valoare maximă ramburs',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Limită opțională pentru valoarea comenzilor ramburs.'
    )

    # Cache volum vânzări (ajută la upgrade de nivel; se va actualiza din orders/payments)
    lifetime_sales_net = models.DecimalField(
        'volum vânzări net (RON)',
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Volum vânzări folosit la determinarea nivelului (Amator/Rising/Top/VIP).'
    )

    def __str__(self):
        return f'Profil vânzător {self.user.email}'

    @property
    def default_location(self):
        return self.user.locations.filter(is_default=True).first()

    @property
    def seller_trust_class(self) -> str:
        score = self.seller_trust_score or 0
        if score >= 85:
            return "A"
        if score >= 70:
            return "B"
        if score >= 50:
            return "C"
        return "D"

    @property
    def has_kyc_badge(self) -> bool:
        prof = getattr(self.user, "profile", None)
        return bool(prof and prof.kyc_status == "APPROVED")

    def save(self, *args, **kwargs):
        # dacă userul are profil de firmă, forțăm tipul PROFESSIONAL by default
        prof = getattr(self.user, "profile", None)
        if prof and prof.is_company and self.seller_type == self.SELLER_TYPE_PRIVATE:
            self.seller_type = self.SELLER_TYPE_PROFESSIONAL
        super().save(*args, **kwargs)


class SellerLocation(models.Model):
    """
    Locații pentru generarea SKU ([LOC3]/...), una implicită.
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
                name="uniq_default_loc_per_user"
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = (self.code or "").upper()[:3]
        super().save(*args, **kwargs)

    def __str__(self):
        base = self.code or "LOC"
        return f"{base} – {self.label}" if self.label else base


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


class TrustedDevice(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="trusted_devices")
    # store only a hash of the token
    token_hash = models.CharField(max_length=128, db_index=True)
    label = models.CharField(max_length=128, blank=True)  # e.g., "Chrome on Mac"
    user_agent = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["user", "token_hash"])]

    def matches(self, raw_token: str) -> bool:
        return check_password(raw_token, self.token_hash)

    @classmethod
    def issue(cls, user, *, user_agent="", ip="", ttl_days=30, label=""):
        token = get_random_string(40)
        obj = cls.objects.create(
            user=user,
            token_hash=make_password(token),
            user_agent=user_agent[:1024],
            ip=ip or None,
            label=label[:128],
            expires_at=timezone.now() + timezone.timedelta(days=ttl_days),
        )
        return obj, token  # caller sets cookie


class Address(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    street_address = models.CharField('stradă și număr', max_length=255)
    building_info = models.CharField('bloc/scară/etaj', max_length=255, blank=True)
    city = models.CharField('oraș', max_length=100)
    region = models.CharField('județ/regiune', max_length=100)
    postal_code = models.CharField('cod poștal', max_length=20)
    country = CountryField('țară')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_billing = models.BooleanField('adresă de facturare', default=False)

    # NEW:
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing  = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ensure single default per user
        if self.is_default_shipping:
            Address.objects.filter(
                user=self.user,
                is_default_shipping=True
            ).exclude(pk=self.pk).update(is_default_shipping=False)
        if self.is_default_billing:
            Address.objects.filter(
                user=self.user,
                is_default_billing=True
            ).exclude(pk=self.pk).update(is_default_billing=False)

    def __str__(self):
        return f'{self.street_address}, {self.city}'


class KycDocument(models.Model):
    """
    Document KYC încărcat de utilizator (CI, pașaport, acte firmă etc.)
    Folosit pentru a susține statusul KYC din Profile.
    """

    DOC_TYPE_ID_CARD = "ID_CARD"
    DOC_TYPE_PASSPORT = "PASSPORT"
    DOC_TYPE_DRIVING_LICENSE = "DRIVING_LICENSE"
    DOC_TYPE_COMPANY_REG = "COMPANY_REG"
    DOC_TYPE_OTHER = "OTHER"

    DOC_TYPE_CHOICES = (
        (DOC_TYPE_ID_CARD, "Carte de identitate / Buletin"),
        (DOC_TYPE_PASSPORT, "Pașaport"),
        (DOC_TYPE_DRIVING_LICENSE, "Permis de conducere"),
        (DOC_TYPE_COMPANY_REG, "Certificat înregistrare firmă / act constitutiv"),
        (DOC_TYPE_OTHER, "Alt document"),
    )

    STATUS_PENDING = "PENDING"
    STATUS_IN_REVIEW = "IN_REVIEW"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (STATUS_PENDING, "În așteptare"),
        (STATUS_IN_REVIEW, "În verificare"),
        (STATUS_APPROVED, "Aprobat"),
        (STATUS_REJECTED, "Respins"),
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="kyc_documents",
        verbose_name="utilizator",
    )
    document_type = models.CharField(
        "tip document",
        max_length=32,
        choices=DOC_TYPE_CHOICES,
    )
    file = models.FileField(
        "fișier",
        upload_to="kyc_documents/",
    )
    status = models.CharField(
        "status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    is_primary = models.BooleanField(
        "document principal",
        default=False,
        help_text="Dacă este bifat, acest document va fi folosit ca referință principală în badge-uri și afișări."
    )

    reference_code = models.CharField(
        "cod referință intern",
        max_length=64,
        blank=True,
        help_text="Cod opțional folosit intern pentru tracking (ex: KYC-2025-0001)."
    )

    notes = models.TextField(
        "note interne",
        blank=True,
        help_text="Note pentru echipa de verificare (nu sunt vizibile userului)."
    )
    rejection_reason = models.TextField(
        "motiv respingere",
        blank=True,
        help_text="Completat atunci când statusul este Respins."
    )

    created_at = models.DateTimeField("încărcat la", auto_now_add=True)
    updated_at = models.DateTimeField("actualizat la", auto_now=True)
    reviewed_at = models.DateTimeField("revizuit la", null=True, blank=True)
    expires_at = models.DateTimeField("expiră la", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "document KYC"
        verbose_name_plural = "documente KYC"

    def __str__(self):
        return f"KYC {self.user.email} – {self.document_type} ({self.status})"

    def save(self, *args, **kwargs):
        # păstrăm vechiul status pentru a detecta tranziția spre APPROVED
        old_status = None
        if self.pk:
            old_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()

        # dacă devine primary, dezactivăm alte primary pentru același user
        super().save(*args, **kwargs)
        if self.is_primary:
            type(self).objects.filter(user=self.user, is_primary=True).exclude(pk=self.pk).update(is_primary=False)

        # dacă documentul tocmai a fost aprobat, sincronizăm profilul + scorurile
        if self.status == self.STATUS_APPROVED and old_status != self.STATUS_APPROVED:
            prof = getattr(self.user, "profile", None)
            if prof:
                if prof.kyc_status != "APPROVED":
                    prof.kyc_status = "APPROVED"
                    prof.kyc_approved_at = timezone.now()
                    prof.save(update_fields=["kyc_status", "kyc_approved_at"])

                # Aplicăm bonusurile de identitate (buyer +, seller + dacă există).
                try:
                    from accounts.services.score import (
                        apply_buyer_identity_bonuses,
                        apply_seller_identity_bonuses,
                    )

                    apply_buyer_identity_bonuses(prof, commit=True)

                    seller = getattr(self.user, "sellerprofile", None)
                    if seller:
                        apply_seller_identity_bonuses(seller, commit=True)
                except Exception:
                    # nu blocăm salvarea documentului dacă serviciul de scor eșuează
                    pass

        # dacă statusul devine REJECTED și profilul era APPROVED strict pe baza acestui doc,
        # logica business pentru downgrade se va decide ulterior (deocamdată nu-l coborâm automat).
        pass
