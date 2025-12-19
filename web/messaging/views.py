from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib import messages

from .models import Conversation, Message
from .forms import MessageForm, ConversationStartForm

@login_required
def conversation_list_view(request):
    convs = Conversation.objects.filter(participants=request.user).order_by('-last_updated')
    return render(request, 'messaging/conversation_list.html', {'conversations': convs})

@login_required
def start_conversation_view(request):
    if request.method == 'POST':
        form = ConversationStartForm(request.POST)
        if form.is_valid():
            conv = form.save(request.user)
            return redirect(reverse('messaging:conversation_detail', args=[conv.pk]))
    else:
        form = ConversationStartForm()
    return render(request, 'messaging/conversation_list.html', {
        'conversations': Conversation.objects.filter(participants=request.user),
        'start_form': form,
    })

@login_required
def conversation_detail_view(request, pk):
    conv = get_object_or_404(Conversation, pk=pk, participants=request.user)
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conv
            msg.sender = request.user
            msg.save()
            conv.last_updated = msg.sent_at
            conv.save(update_fields=['last_updated'])
            return redirect(reverse('messaging:conversation_detail', args=[pk]))
    else:
        form = MessageForm()
    messages_qs = conv.messages.order_by('sent_at')
    return render(request, 'messaging/conversation_detail.html', {
        'conversation': conv,
        'messages': messages_qs,
        'form': form,
    })
