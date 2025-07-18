# Generated by Django 5.2.1 on 2025-06-12 06:36

import django.db.models.deletion
import django_countries.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('country', django_countries.fields.CountryField(blank=True, max_length=2)),
            ],
            options={
                'verbose_name': 'Brand',
                'verbose_name_plural': 'Branduri',
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='products.category')),
            ],
            options={
                'verbose_name': 'Categorie',
                'verbose_name_plural': 'Categorii',
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('listing_type', models.CharField(choices=[('store', 'Vânzare directă'), ('auction', 'Licitație')], max_length=10)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('condition', models.CharField(choices=[('new', 'Nou'), ('like_new', 'Ca nou'), ('used', 'Folosit'), ('vintage', 'Vintage')], max_length=20)),
                ('authenticity_proof', models.FileField(blank=True, null=True, upload_to='products/authenticity/')),
                ('is_active', models.BooleanField(default=True)),
                ('is_published', models.BooleanField(default=False)),
                ('is_approved', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('size', models.CharField(blank=True, max_length=50)),
                ('color', models.CharField(blank=True, max_length=50)),
                ('material', models.CharField(blank=True, max_length=100)),
                ('weight', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('brand', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.brand')),
                ('category', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.category')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProductAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=100)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('comment', models.TextField(blank=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='products.product')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='products/images/')),
                ('alt_text', models.CharField(blank=True, max_length=150)),
                ('is_primary', models.BooleanField(default=False)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='products.product')),
            ],
        ),
        migrations.CreateModel(
            name='ProductReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_resolved', models.BooleanField(default=False)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='products.product')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
