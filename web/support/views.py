# support/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse

from .models import Ticket, TicketMessage
from .forms import TicketForm, TicketMessageForm, TicketUpdateForm


def user_is_agent(user):
    return user.is_staff or user.has_perm("support.change_ticket")


@login_required
def chat_queue(request):
    # stub: you’d pull real queue position & ETA
    position = getattr(request.user, "chat_queue_position", lambda: 1)()
    eta = getattr(request.user, "chat_queue_eta", lambda: 5)()
    return render(
        request,
        "support/chat_queue.html",
        {"position": position, "eta": eta},
    )


@login_required
def tickets_list(request):
    tickets = Ticket.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "support/tickets_list.html", {"tickets": tickets})


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST, user=request.user)
        if form.is_valid():
            tic = form.save(commit=False)
            tic.owner = request.user
            tic.save()
            messages.success(request, "Ticket creat cu succes.")
            return redirect("support:tickets_list")
    else:
        form = TicketForm(user=request.user)
    return render(request, "support/ticket_create.html", {"form": form})


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # doar owner sau agent suport pot vedea tichetul
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
            messages.success(request, "Mesaj trimis.")
            return redirect(reverse("support:ticket_detail", args=[ticket.id]))
    else:
        msg_form = TicketMessageForm()

    return render(
        request,
        "support/ticket_detail.html",
        {
            "ticket": ticket,
            "messages": ticket.messages.order_by("created_at"),
            "msg_form": msg_form,
        },
    )


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
    return render(
        request,
        "support/ticket_update.html",
        {"ticket": ticket, "form": form},
    )
