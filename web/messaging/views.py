# messaging/views.py
from __future__ import annotations

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction, models
from django.db.models import Q, Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order

from .forms import MessageForm
from .models import Conversation, Message, ConversationReadState, MessageAttachment

CONVERSATIONS_PER_PAGE = 20
MESSAGES_PER_PAGE = 30


def _order_sellers(order: Order):
    qs = order.items.select_related("product__owner").all()
    sellers = set()
    for it in qs:
        owner = getattr(getattr(it, "product", None), "owner", None)
        if owner and getattr(owner, "pk", None):
            sellers.add(owner)
    return sellers


def _user_can_access_order(user, order: Order) -> bool:
    if not user or not getattr(user, "pk", None):
        return False
    if user.is_staff:
        return True
    if order.buyer_id == user.pk:
        return True
    sellers = _order_sellers(order)
    return any(s.pk == user.pk for s in sellers)


def _ensure_read_state(conv: Conversation, user, *, last_read_at=None) -> ConversationReadState | None:
    if not user or not getattr(user, "pk", None):
        return None
    obj, _ = ConversationReadState.objects.get_or_create(
        conversation=conv,
        user=user,
        defaults={"last_read_at": last_read_at or timezone.now()},
    )
    return obj


def _get_or_create_state(conv: Conversation, user) -> ConversationReadState:
    st = _ensure_read_state(conv, user, last_read_at=timezone.now())
    assert st is not None
    return st


@login_required
def conversation_list_view(request):
    # base visibility
    qs = Conversation.objects.filter(participants=request.user)

    if request.user.is_staff:
        staff_qs = Conversation.objects.filter(allow_staff=True)
        qs = (qs | staff_qs)

    qs = qs.distinct()

    # ===== annotations: last_read, unread_count, last_message preview, user state (archived/muted) =====
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

    last_read_sq = ConversationReadState.objects.filter(
        conversation=OuterRef("pk"),
        user=request.user,
    ).values("last_read_at")[:1]

    last_read_expr = Coalesce(
        Subquery(last_read_sq, output_field=models.DateTimeField()),
        Value(epoch, output_field=models.DateTimeField()),
    )

    # user state subqueries
    archived_sq = ConversationReadState.objects.filter(
        conversation=OuterRef("pk"),
        user=request.user,
    ).values("is_archived")[:1]

    muted_sq = ConversationReadState.objects.filter(
        conversation=OuterRef("pk"),
        user=request.user,
    ).values("is_muted")[:1]

    muted_until_sq = ConversationReadState.objects.filter(
        conversation=OuterRef("pk"),
        user=request.user,
    ).values("muted_until")[:1]

    # last message subqueries
    last_msg = Message.objects.filter(conversation=OuterRef("pk")).order_by("-sent_at", "-pk")
    last_msg_text_sq = last_msg.values("text")[:1]
    last_msg_sent_sq = last_msg.values("sent_at")[:1]
    last_msg_sender_email_sq = last_msg.values("sender__email")[:1]
    last_msg_sender_fn_sq = last_msg.values("sender__first_name")[:1]
    last_msg_sender_ln_sq = last_msg.values("sender__last_name")[:1]

    qs = qs.annotate(
        # preview
        last_message_text=Subquery(last_msg_text_sq, output_field=models.TextField()),
        last_message_sent_at=Subquery(last_msg_sent_sq, output_field=models.DateTimeField()),
        last_message_sender_email=Subquery(last_msg_sender_email_sq, output_field=models.CharField()),
        last_message_sender_first_name=Subquery(last_msg_sender_fn_sq, output_field=models.CharField()),
        last_message_sender_last_name=Subquery(last_msg_sender_ln_sq, output_field=models.CharField()),

        # state
        is_archived=Coalesce(
            Subquery(archived_sq, output_field=models.BooleanField()),
            Value(False, output_field=models.BooleanField()),
        ),
        is_muted=Coalesce(
            Subquery(muted_sq, output_field=models.BooleanField()),
            Value(False, output_field=models.BooleanField()),
        ),
        muted_until=Subquery(muted_until_sq, output_field=models.DateTimeField()),

        # unread
        unread_count=Count(
            "messages",
            filter=Q(messages__sent_at__gt=last_read_expr) & ~Q(messages__sender=request.user),
        ),
    ).order_by("-last_updated", "-pk")

    # ===== filters/search =====
    kind = (request.GET.get("kind") or "").strip().upper()
    if kind in {Conversation.KIND_ORDER, Conversation.KIND_SUPPORT}:
        qs = qs.filter(kind=kind)

    show = (request.GET.get("show") or "").strip().lower()
    # show=archived => only archived
    if show == "archived":
        qs = qs.filter(is_archived=True)
    else:
        qs = qs.filter(is_archived=False)

    if (request.GET.get("unread") or "").strip() == "1":
        qs = qs.filter(unread_count__gt=0)

    if (request.GET.get("muted") or "").strip() == "1":
        now = timezone.now()
        qs = qs.filter(Q(is_muted=True) | Q(muted_until__gt=now))

    q = (request.GET.get("q") or "").strip()
    if q:
        qf = Q()
        if q.isdigit():
            qf |= Q(order_id=int(q))
            qf |= Q(pk=int(q))
        qf |= Q(participants__email__icontains=q)
        qf |= Q(participants__first_name__icontains=q)
        qf |= Q(participants__last_name__icontains=q)
        qf |= Q(messages__text__icontains=q)
        qs = qs.filter(qf).distinct()

    # prefetch small page worth of participants
    paginator = Paginator(qs, CONVERSATIONS_PER_PAGE)
    page_number = request.GET.get("page") or "1"
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "messaging/conversation_list.html",
        {
            "conversations": page_obj.object_list,
            "page_obj": page_obj,
            "is_staff_inbox": bool(request.user.is_staff),
            "filters": {
                "q": q,
                "kind": kind,
                "show": show,
                "unread": (request.GET.get("unread") or "") == "1",
                "muted": (request.GET.get("muted") or "") == "1",
            },
        },
    )


@login_required
def start_support_conversation_view(request):
    conv, created = Conversation.objects.get_or_create(
        kind=Conversation.KIND_SUPPORT,
        support_user=request.user,
        defaults={"allow_staff": True},
    )

    if not conv.participants.filter(pk=request.user.pk).exists():
        conv.participants.add(request.user)

    _ensure_read_state(conv, request.user)

    if created:
        conv.touch(timezone.now(), commit=True)

    return redirect(reverse("messaging:conversation_detail", args=[conv.pk]))


@login_required
def start_order_conversation_view(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id)

    if not _user_can_access_order(request.user, order):
        raise Http404()

    conv, _created = Conversation.objects.get_or_create(
        kind=Conversation.KIND_ORDER,
        order=order,
        defaults={"allow_staff": (order.status == Order.STATUS_DISPUTED)},
    )

    sellers = _order_sellers(order)

    with transaction.atomic():
        conv.participants.add(order.buyer)
        for s in sellers:
            conv.participants.add(s)

    _ensure_read_state(conv, order.buyer)
    for s in sellers:
        _ensure_read_state(conv, s)

    return redirect(reverse("messaging:conversation_detail", args=[conv.pk]))


@login_required
def escalate_order_conversation_view(request, pk: int):
    conv = get_object_or_404(Conversation, pk=pk)

    if conv.kind != Conversation.KIND_ORDER:
        raise Http404()

    if not conv.is_participant(request.user):
        raise Http404()

    if conv.allow_staff:
        return redirect(reverse("messaging:conversation_detail", args=[conv.pk]))

    conv.allow_staff = True
    conv.save(update_fields=["allow_staff"])

    messages.success(request, "Conversația a fost escaladată către echipa Snobistic.")
    return redirect(reverse("messaging:conversation_detail", args=[conv.pk]))


@login_required
def staff_join_conversation_view(request, pk: int):
    if not request.user.is_staff:
        raise Http404()

    conv = get_object_or_404(Conversation, pk=pk, allow_staff=True)

    if not conv.is_participant(request.user):
        conv.participants.add(request.user)

    _ensure_read_state(conv, request.user, last_read_at=timezone.now())

    return redirect(reverse("messaging:conversation_detail", args=[conv.pk]))


@login_required
def attachment_serve_view(request, pk: int):
    """
    Download/inline preview CONTROLAT (permission check pe conversație).
    """
    att = get_object_or_404(
        MessageAttachment.objects.select_related("message__conversation"),
        pk=pk,
    )
    conv = att.message.conversation

    if not conv.can_view(request.user):
        raise Http404()

    inline = request.GET.get("inline") == "1"

    resp = FileResponse(
        att.file.open("rb"),
        as_attachment=not inline,
        filename=att.original_name or "attachment",
    )

    if att.content_type:
        resp["Content-Type"] = att.content_type

    if inline:
        resp["Content-Disposition"] = f'inline; filename="{att.original_name or "attachment"}"'

    return resp


@require_POST
@login_required
def conversation_toggle_archive_view(request, pk: int):
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.can_view(request.user):
        raise Http404()

    st = _get_or_create_state(conv, request.user)
    st.is_archived = not st.is_archived
    st.archived_at = timezone.now() if st.is_archived else None
    st.save(update_fields=["is_archived", "archived_at", "updated_at"])

    return redirect(request.POST.get("next") or reverse("messaging:conversation_list"))


@require_POST
@login_required
def conversation_toggle_mute_view(request, pk: int):
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.can_view(request.user):
        raise Http404()

    st = _get_or_create_state(conv, request.user)
    st.is_muted = not st.is_muted
    if st.is_muted:
        st.muted_until = None  # mute indefinit (poți schimba în viitor pe 24h/7d)
    else:
        st.muted_until = None
    st.save(update_fields=["is_muted", "muted_until", "updated_at"])

    return redirect(request.POST.get("next") or reverse("messaging:conversation_detail", args=[conv.pk]))


@require_POST
@login_required
def conversation_leave_view(request, pk: int):
    """
    "Leave" = scoate user din participants + marchează left_at.
    Safe default: allow pentru SUPPORT; pentru ORDER recomand să folosești Archive în loc.
    """
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.is_participant(request.user):
        raise Http404()

    if conv.kind == Conversation.KIND_ORDER:
        messages.error(request, "Pentru conversațiile de comandă folosește Arhivare, nu Leave.")
        return redirect(request.POST.get("next") or reverse("messaging:conversation_detail", args=[conv.pk]))

    st = _get_or_create_state(conv, request.user)
    st.left_at = timezone.now()
    st.save(update_fields=["left_at", "updated_at"])

    conv.participants.remove(request.user)
    messages.success(request, "Ai părăsit conversația.")
    return redirect(reverse("messaging:conversation_list"))


@require_POST
@login_required
def conversation_close_view(request, pk: int):
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.can_view(request.user):
        raise Http404()

    if conv.kind != Conversation.KIND_SUPPORT:
        raise Http404()

    # user-ul sau staff-ul poate închide SUPPORT
    if not (request.user.is_staff or conv.support_user_id == request.user.pk):
        raise Http404()

    if not conv.is_closed:
        conv.close(by_user=request.user, ts=timezone.now(), commit=True)
        messages.success(request, "Conversația a fost închisă.")
    return redirect(request.POST.get("next") or reverse("messaging:conversation_detail", args=[conv.pk]))


@require_POST
@login_required
def conversation_reopen_view(request, pk: int):
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.can_view(request.user):
        raise Http404()

    if conv.kind != Conversation.KIND_SUPPORT:
        raise Http404()

    if not (request.user.is_staff or conv.support_user_id == request.user.pk):
        raise Http404()

    if conv.is_closed:
        conv.reopen(commit=True)
        messages.success(request, "Conversația a fost redeschisă.")
    return redirect(request.POST.get("next") or reverse("messaging:conversation_detail", args=[conv.pk]))


@login_required
def conversation_detail_view(request, pk: int):
    conv = get_object_or_404(Conversation, pk=pk)

    if not conv.can_view(request.user):
        raise Http404()

    def mark_read(ts=None):
        ts = ts or timezone.now()
        ConversationReadState.objects.update_or_create(
            conversation=conv,
            user=request.user,
            defaults={"last_read_at": ts},
        )

    # fetch state for UI toggles
    st = _get_or_create_state(conv, request.user)
    is_muted_effective = st.is_muted_effective

    # POST message
    can_post = True
    if conv.is_closed and not request.user.is_staff:
        can_post = False

    if request.method == "POST":
        if not can_post:
            messages.error(request, "Conversația este închisă. Redeschide ca să trimiți mesaje.")
            return redirect(reverse("messaging:conversation_detail", args=[pk]))

        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            text = (form.cleaned_data.get("text") or "").strip()
            files = form.cleaned_data.get("attachments") or []

            with transaction.atomic():
                msg = Message.objects.create(
                    conversation=conv,
                    sender=request.user,
                    text=text,
                    sent_at=timezone.now(),
                )

                for f in files:
                    MessageAttachment.objects.create(
                        message=msg,
                        file=f,
                        original_name=getattr(f, "name", "")[:255],
                        content_type=(getattr(f, "content_type", "") or "")[:120],
                        size_bytes=int(getattr(f, "size", 0) or 0),
                    )

                # staff posting in staff-allowed conversation => auto-join
                if request.user.is_staff and conv.allow_staff and not conv.is_participant(request.user):
                    conv.participants.add(request.user)

                conv.touch(msg.sent_at, commit=True)

                # sender read state updated to message time
                mark_read(msg.sent_at)

            return redirect(reverse("messaging:conversation_detail", args=[pk]))
    else:
        form = MessageForm()
        mark_read(timezone.now())

    # ===== messages pagination (newest page=1, older pages=2,3...) =====
    messages_qs = (
        conv.messages
        .select_related("sender")
        .prefetch_related("attachments")
        .order_by("-sent_at", "-pk")
    )

    paginator = Paginator(messages_qs, MESSAGES_PER_PAGE)
    page_number = request.GET.get("page") or "1"
    page_obj = paginator.get_page(page_number)
    is_latest_page = str(page_obj.number) == "1"

    order = getattr(conv, "order", None)
    is_order = conv.kind == Conversation.KIND_ORDER
    is_support = conv.kind == Conversation.KIND_SUPPORT

    can_escalate = is_order and conv.is_participant(request.user) and not conv.allow_staff
    can_staff_join = bool(request.user.is_staff and conv.allow_staff and not conv.is_participant(request.user))

    # can close/reopen UI
    can_close = is_support and (request.user.is_staff or conv.support_user_id == request.user.pk)
    can_reopen = can_close and conv.is_closed

    return render(
        request,
        "messaging/conversation_detail.html",
        {
            "conversation": conv,
            "messages_page": page_obj,
            "form": form,
            "is_order": is_order,
            "is_support": is_support,
            "order": order,
            "can_escalate": can_escalate,
            "can_staff_join": can_staff_join,
            "can_post": can_post,
            "is_latest_page": is_latest_page,
            "state": {
                "is_archived": bool(st.is_archived),
                "is_muted": bool(st.is_muted),
                "is_muted_effective": bool(is_muted_effective),
            },
            "can_close": can_close,
            "can_reopen": can_reopen,
        },
    )
