from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import ChatSession, Message
from .forms import MessageForm
from django.utils import timezone


@login_required
def inbox_view(request):
    sessions = ChatSession.objects.filter(Q(user1=request.user) | Q(user2=request.user))
    return render(request, 'chat/chat_list.html', {
        'sessions': sessions
    })


@login_required
def chat_session_view(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id)

    # Asigură-te că userul face parte din conversație
    if request.user not in [session.user1, session.user2]:
        return redirect('inbox')

    other_user = session.get_other_user(request.user)
    messages = session.messages.all()

    # Marchează ca citite toate mesajele primite
    unread = messages.filter(receiver=request.user, is_read=False)
    unread.update(is_read=True)

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.session = session
            msg.sender = request.user
            msg.receiver = other_user
            msg.timestamp = timezone.now()
            msg.save()
            return redirect('chat_session', session_id=session.id)
    else:
        form = MessageForm()

    return render(request, 'chat/chat_session.html', {
        'session': session,
        'messages': messages,
        'form': form,
        'other_user': other_user,
    })


@login_required
def start_chat_view(request, user_id):
    from accounts.models import CustomUser
    target = get_object_or_404(CustomUser, pk=user_id)

    if request.user == target:
        return redirect('inbox')

    # Evită dublura conversațiilor
    session = ChatSession.objects.filter(
        (Q(user1=request.user) & Q(user2=target)) | 
        (Q(user1=target) & Q(user2=request.user))
    ).first()

    if not session:
        session = ChatSession.objects.create(user1=request.user, user2=target)

    return redirect('chat_session', session_id=session.id)
