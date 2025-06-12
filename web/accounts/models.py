# web/accounts/models.py
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    phone = PhoneNumberField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    USER_TYPE_CHOICES = [
        ('buyer', 'Cumpărător'),
        ('seller', 'Vânzător'),
        ('shopmanager', 'Shop Manager'),
        ('admin', 'Administrator'),
    ]
    user_type = models.CharField(max_length=15, choices=USER_TYPE_CHOICES, default='buyer')

    is_company = models.BooleanField(default=False)
    vat_payer = models.BooleanField(default=False)
    two_fa_enabled = models.BooleanField(default=False)
    verified_email = models.BooleanField(default=False)

    deleted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        suffix = " (dezactivat)" if self.deleted_at else ""
        return f"{self.email} ({self.user_type}){suffix}"

    def delete(self, using=None, keep_parents=False):
        # soft-delete
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['deleted_at', 'is_active'])

    def reactivate(self):
        self.deleted_at = None
        self.is_active = True
        self.save(update_fields=['deleted_at', 'is_active'])

    def get_default_shipping_address(self):
        return self.addresses.filter(address_type='shipping', is_default=True).first()


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='user_avatars/', blank=True, null=True)
    iban = models.CharField(max_length=34, blank=True)
    description = models.TextField(blank=True)

    # optional measurements
    shoulder = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bust     = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    waist    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hips     = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    length   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sleeve   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    leg_in   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    leg_out  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Profil {self.user.username}"


class UserAddress(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ('shipping', 'Adresă livrare'),
        ('billing',  'Adresă facturare'),
    ]

    user           = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    address_type   = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES)
    name           = models.CharField(max_length=100)
    country        = CountryField()
    city           = models.CharField(max_length=100)
    street_address = models.CharField(max_length=255)
    postal_code    = models.CharField(max_length=20)
    is_default     = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'address_type', 'name')

    def __str__(self):
        return f"{self.get_address_type_display()} – {self.user.email}"


class EmailToken(models.Model):
    PURPOSE_CHOICES = [
        ('activation',     'Activare cont'),
        ('password_reset', 'Resetare parolă'),
        ('email_change',   'Schimbare email'),
    ]

    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_tokens')
    token      = models.CharField(max_length=128, unique=True, default=uuid.uuid4().hex)
    purpose    = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='activation')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    used       = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['purpose']),
        ]

    def __str__(self):
        return f"Token {self.get_purpose_display()} – {self.user.email}"

    def is_expired(self, hours=24):
        return timezone.now() > (self.created_at + timezone.timedelta(hours=hours))
