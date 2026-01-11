# support/services.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.db.models import Case, IntegerField, Q, Value, When
from django.contrib.auth import get_user_model

from .models import Ticket


@dataclass(frozen=True)
class QueueInfo:
    ticket: Optional[Ticket]
    position: int
    eta_minutes: int
    agents: int
    avg_minutes_per_ticket: int
    note: str = ""  # mesaj contextual (ex: awaiting_user)


def _priority_rank_case():
    return Case(
        When(priority=Ticket.Priority.HIGH, then=Value(0)),
        When(priority=Ticket.Priority.MEDIUM, then=Value(1)),
        When(priority=Ticket.Priority.LOW, then=Value(2)),
        default=Value(1),
        output_field=IntegerField(),
    )


def get_agent_count() -> int:
    User = get_user_model()
    return User.objects.filter(is_active=True, is_staff=True).count()


def _avg_minutes(category: str | None) -> int:
    by_cat = getattr(settings, "SUPPORT_AVG_HANDLE_MINUTES_BY_CATEGORY", None)
    if isinstance(by_cat, dict) and category:
        val = by_cat.get(category)
        if isinstance(val, int) and val > 0:
            return val

    default_val = getattr(settings, "SUPPORT_AVG_HANDLE_MINUTES", 6)
    try:
        default_val = int(default_val)
    except Exception:
        default_val = 6
    return max(default_val, 1)


def get_queue_ticket_for_user(user, *, category: str | None = None) -> Optional[Ticket]:
    """
    În coadă intră DOAR tichetele care necesită acțiune din partea suportului:
      - NEW
      - IN_PROGRESS
    Ticket-urile AWAITING_USER NU ocupă coada (așteaptă user).
    """
    qs = Ticket.objects.filter(owner=user, status__in=[Ticket.Status.NEW, Ticket.Status.IN_PROGRESS])
    if category and category != "all":
        qs = qs.filter(category=category)
    return qs.order_by("created_at", "id").first()


def compute_queue_info_for_user(user, *, category: str | None = None) -> QueueInfo:
    agents = get_agent_count()
    avg = _avg_minutes(category)

    # dacă user-ul are un ticket awaiting_user, îi arătăm un mesaj util
    awaiting = Ticket.objects.filter(owner=user, status=Ticket.Status.AWAITING_USER)
    if category and category != "all":
        awaiting = awaiting.filter(category=category)
    awaiting_ticket = awaiting.order_by("created_at", "id").first()
    if awaiting_ticket:
        return QueueInfo(
            ticket=awaiting_ticket,
            position=0,
            eta_minutes=0,
            agents=agents,
            avg_minutes_per_ticket=avg,
            note="Acest tichet așteaptă răspunsul tău. După ce răspunzi, revine în lucru.",
        )

    ticket = get_queue_ticket_for_user(user, category=category)
    if not ticket:
        return QueueInfo(ticket=None, position=0, eta_minutes=0, agents=agents, avg_minutes_per_ticket=avg)

    base = Ticket.objects.filter(status__in=[Ticket.Status.NEW, Ticket.Status.IN_PROGRESS])
    if category and category != "all":
        base = base.filter(category=category)

    base = base.annotate(priority_rank=_priority_rank_case())
    my_rank = {Ticket.Priority.HIGH: 0, Ticket.Priority.MEDIUM: 1, Ticket.Priority.LOW: 2}.get(ticket.priority, 1)

    ahead = base.filter(
        Q(priority_rank__lt=my_rank)
        | Q(priority_rank=my_rank, created_at__lt=ticket.created_at)
        | Q(priority_rank=my_rank, created_at=ticket.created_at, id__lt=ticket.id)
    ).count()

    position = ahead + 1
    effective_agents = max(agents, 1)
    eta = int(math.ceil(((position - 1) / effective_agents) * avg))

    return QueueInfo(
        ticket=ticket,
        position=position,
        eta_minutes=max(eta, 0),
        agents=agents,
        avg_minutes_per_ticket=avg,
    )
