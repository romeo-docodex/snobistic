# auctions/views.py
from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import Product
from .forms import BidForm
from .models import Auction


def _user_is_seller(user) -> bool:
    """
    Source of truth:
    - profile.role_seller preferred
    - fallback user.is_seller
    """
    try:
        prof = getattr(user, "profile", None)
        if prof is not None and getattr(prof, "role_seller", False):
            return True
    except Exception:
        pass
    return bool(getattr(user, "is_seller", False))


def _expire_due_auctions():
    """
    Lightweight safety: close auctions that passed end_time.
    (In prod: management command / cron / celery beat.)
    """
    qs = Auction.objects.due_to_expire().only("id")
    ids = list(qs.values_list("id", flat=True)[:200])  # soft cap
    if not ids:
        return
    for a in Auction.objects.filter(id__in=ids).select_related("product").iterator():
        a.settle_if_needed()


@login_required
def create_auction_for_product_view(request, product_slug):
    """
    Start auction for an EXISTING product:
    - creates Auction (PENDING) if missing
    - redirects to wizard_edit (so user configures it)
    """
    if not _user_is_seller(request.user):
        return HttpResponseForbidden("Doar vânzătorii pot porni licitații.")

    product = get_object_or_404(Product, slug=product_slug, owner=request.user)

    # if already has auction -> go there / edit
    existing = Auction.objects.filter(product=product).first()
    if existing:
        if existing.status == Auction.Status.PENDING:
            return redirect("auctions:wizard_edit", pk=product.pk)
        return redirect("auctions:auction_detail", pk=existing.pk)

    # sanity: product must have images etc (wizard step will enforce anyway)
    start_price = product.price if product.price is not None else Decimal("10.00")

    auction = Auction.objects.create(
        product=product,
        creator=request.user,
        start_price=start_price,
        reserve_price=None,
        duration_days=7,
        min_increment_percent=10,
        payment_window_hours=48,
        start_time=timezone.now(),
        status=Auction.Status.PENDING,
    )

    messages.info(request, "Am creat licitația în așteptare. Configureaz-o și finalizează.")
    return redirect("auctions:wizard_edit", pk=product.pk)


def auction_list_view(request):
    _expire_due_auctions()

    now = timezone.now()
    state = request.GET.get("state", "active").lower()

    qs = (
        Auction.objects.all()
        .select_related("product", "creator", "winner", "winning_bid")
        .prefetch_related("images", "product__images")
    )

    if state == "ended":
        qs = qs.filter(status=Auction.Status.ENDED)
    elif state == "upcoming":
        qs = qs.filter(status=Auction.Status.PENDING, start_time__gt=now)
    elif state == "canceled":
        qs = qs.filter(status=Auction.Status.CANCELED)
    else:  # active
        qs = qs.filter(status=Auction.Status.ACTIVE, start_time__lte=now, end_time__gt=now)

    return render(
        request,
        "auctions/auction_list.html",
        {"auctions": qs, "selected_state": state},
    )


def auction_detail_view(request, pk):
    _expire_due_auctions()

    auction = get_object_or_404(
        Auction.objects.select_related("product", "creator", "winner", "winning_bid").prefetch_related(
            "images", "product__images"
        ),
        pk=pk,
    )

    bid_form = BidForm(auction=auction, user=request.user)

    return render(
        request,
        "auctions/auction_detail.html",
        {"auction": auction, "bid_form": bid_form},
    )


@login_required
@require_POST
def place_bid_view(request, pk):
    _expire_due_auctions()

    auction = get_object_or_404(Auction.objects.select_related("product", "creator"), pk=pk)
    form = BidForm(request.POST, auction=auction, user=request.user)

    if not form.is_valid():
        return render(
            request,
            "auctions/auction_detail.html",
            {"auction": auction, "bid_form": form},
        )

    try:
        auction.place_bid(user=request.user, amount=form.cleaned_data["amount"])
        messages.success(request, "Oferta ta a fost înregistrată.")
        return redirect("auctions:auction_detail", pk=pk)
    except ValidationError as e:
        msg = None
        try:
            msg = e.messages[0]
        except Exception:
            msg = str(e)
        form.add_error("amount", msg)
        return render(
            request,
            "auctions/auction_detail.html",
            {"auction": auction, "bid_form": form},
        )


@login_required
@require_POST
def close_auction_view(request, product_slug):
    auction = get_object_or_404(
        Auction.objects.select_related("product"),
        product__slug=product_slug,
        creator=request.user,
    )
    if auction.status != Auction.Status.ACTIVE:
        return redirect("auctions:auction_detail", pk=auction.pk)

    auction.end_time = timezone.now()
    auction.save(update_fields=["end_time", "updated_at"])
    auction.settle_if_needed()
    return redirect("auctions:auction_detail", pk=auction.pk)


@login_required
@require_POST
def cancel_auction_view(request, product_slug):
    auction = get_object_or_404(
        Auction.objects.select_related("product"),
        product__slug=product_slug,
        creator=request.user,
    )
    auction.cancel(by_user=request.user)
    return redirect("auctions:auction_detail", pk=auction.pk)
