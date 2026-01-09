# orders/signals.py
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ReturnRequest


@receiver(post_save, sender=ReturnRequest)
def _return_request_created_mark_disputed(sender, instance: ReturnRequest, created: bool, **kwargs):
    if not created:
        return
    try:
        instance.order.mark_escrow_disputed()
    except Exception:
        pass
