# support/services_messaging.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from orders.models import Order
from messaging.models import Conversation, ConversationReadState
from .models import Ticket


def _order_sellers(order: Order):
    qs = order.items.select_related("product__owner").all()
    sellers = set()
    for it in qs:
        owner = getattr(getattr(it, "product", None), "owner", None)
        if owner and getattr(owner, "pk", None):
            sellers.add(owner)
    return sellers


def ensure_ticket_conversation(ticket: Ticket) -> Conversation:
    """
    Creează (sau returnează) conversația de SUPPORT pentru un ticket.

    - kind=SUPPORT
    - support_user=ticket.owner
    - support_ticket=ticket
    - allow_staff=True (staff poate vedea și join)
    - participants: owner + (dacă există order) buyer + sellers (tri-party)
    """
    conv = Conversation.objects.filter(
        kind=Conversation.KIND_SUPPORT,
        support_ticket=ticket,
    ).first()
    if conv:
        return conv

    with transaction.atomic():
        conv = Conversation.objects.create(
            kind=Conversation.KIND_SUPPORT,
            support_user=ticket.owner,
            support_ticket=ticket,
            allow_staff=True,
        )

        participants = {ticket.owner}

        # tri-party dacă există order: buyer + sellers
        if ticket.order_id and ticket.order:
            order = ticket.order
            if getattr(order, "buyer_id", None):
                participants.add(order.buyer)
            for s in _order_sellers(order):
                participants.add(s)

        conv.participants.add(*participants)

        now = timezone.now()
        for u in participants:
            ConversationReadState.objects.get_or_create(
                conversation=conv,
                user=u,
                defaults={"last_read_at": now},
            )

        conv.touch(now, commit=True)

    return conv
