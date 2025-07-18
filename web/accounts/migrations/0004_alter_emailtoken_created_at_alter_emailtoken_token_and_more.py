# Generated by Django 5.2.1 on 2025-06-12 09:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_emailtoken_token_alter_useraddress_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailtoken',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='emailtoken',
            name='token',
            field=models.CharField(default='54aab9317b8a4230a7c8502f3bbf912f', max_length=128, unique=True),
        ),
        migrations.AlterField(
            model_name='useraddress',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
