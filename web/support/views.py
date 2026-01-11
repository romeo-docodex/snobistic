# support/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse

from .models import Ticket
from .forms import TicketForm, TicketMessageForm, TicketUpdateForm
from .services import compute_queue_info_for_user
from .services_messaging import ensure_ticket_conversation


def user_is_agent(user):
    return user.is_staff or user.has_perm("support.change_ticket")


@login_required
def chat_queue(request):
    """
    Queue real:
    - user e în coadă dacă are tichet NEW/IN_PROGRESS
    - poziție derivată din: prioritate + created_at
    - ETA derivat din: nr agenți (staff) + avg minutes / ticket (SLA)
    """
    category = request.GET.get("category", "all")
    qinfo = compute_queue_info_for_user(request.user, category=category)

    return render(
        request,
        "support/chat_queue.html",
        {
            "queue_ticket": qinfo.ticket,
            "position": qinfo.position,
            "eta": qinfo.eta_minutes,
            "agents": qinfo.agents,
            "avg_minutes": qinfo.avg_minutes_per_ticket,
            "category": category,
            "queue_note": getattr(qinfo, "note", ""),
        },
    )


@login_required
def tickets_list(request):
    tickets = Ticket.objects.filter(owner=request.user).order_by("-updated_at", "-created_at")
    return render(request, "support/tickets_list.html", {"tickets": tickets})


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST, user=request.user)
        if form.is_valid():
            tic = form.save(commit=False)
            tic.owner = request.user
            tic.status = Ticket.Status.NEW
            tic.save()

            # ✅ opțional: creează automat conversația de suport pentru tichet
            ensure_ticket_conversation(tic)

            messages.success(request, "Ticket creat cu succes.")
            return redirect("support:tickets_list")
    else:
        form = TicketForm(user=request.user)
    return render(request, "support/ticket_create.html", {"form": form})


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.owner != request.user and not user_is_agent(request.user):
        messages.error(request, "Nu ai acces la acest tichet.")
        return redirect("support:tickets_list")

    if request.method == "POST":
        msg_form = TicketMessageForm(request.POST)
        if msg_form.is_valid():
            msg = msg_form.save(commit=False)
            msg.ticket = ticket
            msg.author = request.user
            msg.save()

            is_agent = user_is_agent(request.user)

            # ✅ workflow automat:
            # - dacă agentul răspunde la NEW => IN_PROGRESS
            # - dacă user-ul răspunde la AWAITING_USER => IN_PROGRESS
            # - dacă user-ul scrie pe RESOLVED/REJECTED => re-open (NEW)
            new_status = None

            if is_agent and ticket.status == Ticket.Status.NEW:
                new_status = Ticket.Status.IN_PROGRESS

            if (not is_agent) and ticket.status == Ticket.Status.AWAITING_USER:
                new_status = Ticket.Status.IN_PROGRESS

            if (not is_agent) and ticket.status in (Ticket.Status.RESOLVED, Ticket.Status.REJECTED):
                new_status = Ticket.Status.NEW

            if new_status and new_status != ticket.status:
                ticket.status = new_status
                ticket.save(update_fields=["status", "updated_at"])
            else:
                ticket.save(update_fields=["updated_at"])

            messages.success(request, "Mesaj trimis.")
            return redirect(reverse("support:ticket_detail", args=[ticket.id]))
    else:
        msg_form = TicketMessageForm()

    return render(
        request,
        "support/ticket_detail.html",
        {
            "ticket": ticket,
            "messages": ticket.messages.select_related("author").order_by("created_at"),
            "msg_form": msg_form,
        },
    )


@login_required
def ticket_open_chat(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.owner != request.user and not user_is_agent(request.user):
        messages.error(request, "Nu ai acces la acest tichet.")
        return redirect("support:tickets_list")

    conv = ensure_ticket_conversation(ticket)
    return redirect(reverse("messaging:conversation_detail", args=[conv.pk]))


@login_required
@user_passes_test(user_is_agent)
def ticket_update(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == "POST":
        form = TicketUpdateForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            messages.success(request, "Ticket actualizat.")
            return redirect(reverse("support:ticket_detail", args=[ticket.id]))
    else:
        form = TicketUpdateForm(instance=ticket)

    return render(request, "support/ticket_update.html", {"ticket": ticket, "form": form})
