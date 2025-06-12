from django.contrib.auth.models import AbstractUser
from django.db import models
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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.user_type})"


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='user_avatars/', blank=True, null=True)
    iban = models.CharField(max_length=34, blank=True)
    description = models.TextField(blank=True)

    # Dimensiuni
    shoulder = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bust = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    waist = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hips = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    length = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sleeve = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    leg_in = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    leg_out = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Profil {self.user.username}"


class UserAddress(models.Model):
    ADDRESS_TYPE_CHOICES = [('shipping', 'Adresă livrare'), ('billing', 'Adresă facturare')]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    country = CountryField()
    city = models.CharField(max_length=100)
    street_address = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_address_type_display()} – {self.user.email}"


class EmailToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    purpose = models.CharField(max_length=20, default='activation')

    def __str__(self):
        return f"Token {self.purpose} – {self.user.email}"
