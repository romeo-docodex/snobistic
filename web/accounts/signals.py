# web/accounts/signals.py
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, UserProfile, EmailToken
from wallet.models import Wallet


@receiver(post_save, sender=CustomUser)
def create_profile_wallet_and_activation_token(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        Wallet.objects.create(user=instance)
        token = uuid.uuid4().hex
        EmailToken.objects.create(user=instance, token=token, purpose='activation')
