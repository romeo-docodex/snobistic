from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, UserProfile
from wallet.models import Wallet


@receiver(post_save, sender=CustomUser)
def create_profile_and_wallet(sender, instance, created, **kwargs):
    if created:
        # Creare profil extins
        UserProfile.objects.create(user=instance)

        # Creare portofel
        Wallet.objects.create(user=instance)
