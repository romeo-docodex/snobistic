from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import SupportTicket
from .forms import SupportTicketForm, SupportTicketUpdateForm


# ========================
# CREARE TICKET - USER
# ========================
@login_required
def create_ticket_view(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            messages.success(request, "Ticketul a fost trimis cu succes.")
            return redirect('ticket_list')
    else:
        form = SupportTicketForm()

    return render(request, 'support/ticket_form.html', {'form': form})


# ========================
# LISTARE TICKETE - USER
# ========================
@login_required
def user_ticket_list_view(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'support/ticket_list.html', {'tickets': tickets})


# ========================
# DETALII TICKET - USER
# ========================
@login_required
def ticket_detail_view(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, pk=ticket_id, user=request.user)
    return render(request, 'support/ticket_detail.html', {'ticket': ticket})


# ========================
# LISTARE TICKETE - STAFF
# ========================
@user_passes_test(lambda u: u.is_staff)
def admin_ticket_list_view(request):
    tickets = SupportTicket.objects.all().order_by('-created_at')
    return render(request, 'support/admin/ticket_list.html', {'tickets': tickets})


# ========================
# DETALII & UPDATE - STAFF
# ========================
@user_passes_test(lambda u: u.is_staff)
def admin_ticket_detail_view(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)

    if request.method == 'POST':
        form = SupportTicketUpdateForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            messages.success(request, "Ticketul a fost actualizat.")
            return redirect('admin_ticket_detail', ticket_id=ticket.pk)
    else:
        form = SupportTicketUpdateForm(instance=ticket)

    return render(request, 'support/admin/ticket_detail.html', {
        'ticket': ticket,
        'form': form
    })
