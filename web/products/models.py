# web/products/models.py

import uuid
from django.db import models
from django.conf import settings
from django.urls import reverse
from django_countries.fields import CountryField
from .utils import unique_slugify


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    country = CountryField(blank=True)

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Branduri"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        related_name='children', on_delete=models.CASCADE
    )
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        verbose_name = "Categorie"
        verbose_name_plural = "Categorii"

    def save(self, *args, **kwargs):
        if not self.slug:
            # ensure unique slug across categories
            self.slug = unique_slugify(self.name, model=Category, instance=self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:product_list') + f'?category={self.pk}'

    def __str__(self):
        return self.name


class Product(models.Model):
    LISTING_TYPE_CHOICES = [
        ('store', 'Vânzare directă'),
        ('auction', 'Licitație'),
    ]
    CONDITION_CHOICES = [
        ('new', 'Nou'),
        ('like_new', 'Ca nou'),
        ('used', 'Folosit'),
        ('vintage', 'Vintage'),
    ]

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products'
    )
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(
        Brand, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='products'
    )
    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='products'
    )
    description = models.TextField()
    slug = models.SlugField(unique=True, blank=True)

    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    authenticity_proof = models.FileField(
        upload_to='products/authenticity/',
        blank=True, null=True
    )

    # Stock & SEO
    stock = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional attributes
    size = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=50, blank=True)
    material = models.CharField(max_length=100, blank=True)
    weight = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', 'is_approved']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            # generate a unique slug
            self.slug = unique_slugify(self.name, model=Product, instance=self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:product_detail', args=[self.slug])

    def get_primary_image(self):
        # return the image flagged primary, or first available
        primary = self.images.filter(is_primary=True).first()
        return primary or self.images.first()

    @property
    def price_display(self):
        return f"{self.price:,.2f} RON"

    def __str__(self):
        return f"{self.name} ({self.seller.email})"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, related_name='images', on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to='products/images/')
    alt_text = models.CharField(max_length=150, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_primary', 'id']

    def __str__(self):
        return f"Imagine pentru {self.product.name}"


class ProductReport(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='reports'
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reports'
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Raport pentru {self.product.name} de {self.reporter.email}"


class ProductAuditLog(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='audit_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} – {self.product.name} la {self.timestamp:%Y-%m-%d %H:%M}"
