# auctions/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden

from .models import Auction
from catalog.models import Product
from .forms import (
    AuctionStep1Form, AuctionStep2Form, AuctionStep3Form,
    AuctionStep4Form, AuctionStep5Form, BidForm,
    AuctionProductCreateForm,
)


def auction_list_view(request):
    now = timezone.now()
    state = request.GET.get("state", "active")
    qs = (
        Auction.objects.all()
        .select_related("product")
        .prefetch_related("images", "bids")
    )
    if state == "ended":
        qs = qs.filter(end_time__lte=now)
    elif state == "upcoming":
        qs = qs.filter(start_time__gt=now)
    else:  # active
        qs = qs.filter(end_time__gt=now, start_time__lte=now, is_active=True)
    return render(
        request,
        "auctions/auction_list.html",
        {"auctions": qs, "selected_state": state},
    )


def auction_detail_view(request, pk):
    auction = get_object_or_404(
        Auction.objects.select_related("product", "category", "creator")
        .prefetch_related("images", "materials", "bids__user"),
        pk=pk,
    )
    bid_form = BidForm(initial={"user": request.user}, auction=auction)
    return render(
        request,
        "auctions/auction_detail.html",
        {
            "auction": auction,
            "bid_form": bid_form,
        },
    )


@login_required
@require_POST
def place_bid_view(request, pk):
    auction = get_object_or_404(
        Auction, pk=pk, end_time__gt=timezone.now(), is_active=True
    )
    form = BidForm(request.POST, auction=auction, user=request.user)
    if form.is_valid():
        form.save()
    return redirect("auctions:auction_detail", pk=pk)


# 0 – CREARE PRODUS NOU PENTRU LICITAȚIE
@login_required
def auction_start_new_product(request):
    """
    Pas 0: creează un Product nou, folosit exclusiv pentru licitație.
    După salvare, redirect la step1 (metadata imagini licitație).
    """
    if request.method == "POST":
        form = AuctionProductCreateForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(owner=request.user)
            return redirect("auctions:create_auction", product_slug=product.slug)
    else:
        form = AuctionProductCreateForm()

    return render(
        request,
        "auctions/auction_create_steps/start_product.html",
        {"form": form},
    )


# 5-Step creation flow:
@login_required
def auction_step1_metadata(request, product_slug):
    # only the product owner can start an auction on their product
    product = get_object_or_404(Product, slug=product_slug, owner=request.user)

    if request.method == "POST":
        # bind to an instance that already has creator/product/category
        instance = Auction(
            product=product, category=product.category, creator=request.user
        )
        form = AuctionStep1Form(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            auction = form.save(commit=True)  # saves and creates AuctionImage rows
            return redirect("auctions:step2_size", pk=auction.pk)
    else:
        form = AuctionStep1Form(
            initial={
                "product": product.pk,
                "category": product.category.pk,
            }
        )

    return render(
        request,
        "auctions/auction_create_steps/step1_metadata.html",
        {
            "form": form,
            "product": product,
        },
    )


@login_required
def auction_step2_size(request, pk):
    auction = get_object_or_404(Auction, pk=pk, creator=request.user)
    if request.method == "POST":
        form = AuctionStep2Form(request.POST, instance=auction)
        if form.is_valid():
            form.save()
            return redirect("auctions:step3_dimensions", pk=pk)
    else:
        form = AuctionStep2Form(instance=auction)
    return render(
        request,
        "auctions/auction_create_steps/step2_size.html",
        {"form": form, "auction": auction},
    )


@login_required
def auction_step3_dimensions(request, pk):
    auction = get_object_or_404(Auction, pk=pk, creator=request.user)
    if request.method == "POST":
        form = AuctionStep3Form(request.POST, instance=auction)
        if form.is_valid():
            form.save()
            return redirect("auctions:step4_materials_description", pk=pk)
    else:
        form = AuctionStep3Form(instance=auction)
    return render(
        request,
        "auctions/auction_create_steps/step3_dimensions.html",
        {"form": form, "auction": auction},
    )


@login_required
def auction_step4_materials_description(request, pk):
    auction = get_object_or_404(Auction, pk=pk, creator=request.user)
    if request.method == "POST":
        form = AuctionStep4Form(request.POST, instance=auction)
        if form.is_valid():
            form.save()
            return redirect("auctions:step5_auction_settings", pk=pk)
    else:
        form = AuctionStep4Form(instance=auction)
    return render(
        request,
        "auctions/auction_create_steps/step4_materials_description.html",
        {"form": form, "auction": auction},
    )


@login_required
def auction_step5_auction_settings(request, pk):
    auction = get_object_or_404(Auction, pk=pk, creator=request.user)
    if request.method == "POST":
        form = AuctionStep5Form(request.POST, instance=auction)
        if form.is_valid():
            auction = form.save(commit=False)

            # activăm licitația
            auction.is_active = True
            auction.save()

            # ── sincronizăm produsul asociat ────────────────────────────────
            product = auction.product
            # marchează-l ca listat prin licitație
            product.sale_type = "AUCTION"
            # prețul de referință în catalog = preț de pornire
            product.price = auction.start_price
            product.quantity = 1

            # populăm câmpurile de auction din Product pentru consistență
            product.auction_start_price = auction.start_price
            product.auction_reserve_price = auction.min_price
            product.auction_end_at = auction.end_time

            product.save(
                update_fields=[
                    "sale_type",
                    "price",
                    "quantity",
                    "auction_start_price",
                    "auction_reserve_price",
                    "auction_end_at",
                ]
            )
            # ────────────────────────────────────────────────────────────────

            return redirect("auctions:auction_detail", pk=pk)
    else:
        form = AuctionStep5Form(instance=auction)
    return render(
        request,
        "auctions/auction_create_steps/step5_auction_settings.html",
        {"form": form, "auction": auction},
    )


@login_required
def close_auction_view(request, product_slug):
    auction = get_object_or_404(
        Auction, product__slug=product_slug, creator=request.user
    )
    auction.end_time = timezone.now()
    auction.is_active = False
    auction.save(update_fields=["end_time", "is_active"])
    return redirect("auctions:auction_detail", pk=auction.pk)
