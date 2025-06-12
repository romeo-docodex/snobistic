from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Auction, Bid, AuctionHistory
from .forms import BidForm


def auction_list_view(request):
    """
    Afișează licitațiile active, paginate.
    """
    qs = Auction.objects.filter(is_active=True, end_time__gt=timezone.now())
    paginator = Paginator(qs, 9)  # 9 licitații pe pagină
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'auctions/auction_list.html', {'auctions': page_obj})


def auction_detail_view(request, product_slug):
    """
    Afișează detaliile licitației pentru produsul cu slug-ul dat.
    """
    auction = get_object_or_404(
        Auction,
        product__slug=product_slug,
        is_active=True
    )
    bids = auction.bids.all()
    history = auction.history.all()
    can_bid = auction.is_ongoing()

    return render(request, 'auctions/auction_detail.html', {
        'auction': auction,
        'bids': bids,
        'history': history,
        'can_bid': can_bid,
        'form': BidForm(auction=auction, user=request.user) if request.user.is_authenticated else None,
    })


@login_required
def place_bid_view(request, product_slug):
    """
    Primește POST cu ofertă, validează și salvează.
    """
    auction = get_object_or_404(Auction, product__slug=product_slug, is_active=True)
    if not auction.is_ongoing():
        messages.error(request, "Licitația nu este activă.")
        return redirect('auctions:auction_detail', product_slug=product_slug)

    form = BidForm(request.POST or None, auction=auction, user=request.user)
    if request.method == 'POST':
        if form.is_valid():
            bid = form.save()
            AuctionHistory.objects.create(
                auction=auction,
                user=request.user,
                event=f"A plasat o ofertă de {bid.amount} RON"
            )
            messages.success(request, "Oferta a fost înregistrată.")
            return redirect('auctions:auction_detail', product_slug=product_slug)
        else:
            messages.error(request, "Oferta nu a fost validă.")

    return render(request, 'auctions/place_bid.html', {
        'auction': auction,
        'form': form,
    })


@login_required
def close_auction_view(request, product_slug):
    """
    Închide licitația manual (doar staff).
    """
    if not request.user.is_staff:
        messages.error(request, "Nu ai permisiunea.")
        return redirect('auctions:auction_detail', product_slug=product_slug)

    auction = get_object_or_404(Auction, product__slug=product_slug)
    if auction.is_active:
        highest = auction.highest_bid()
        auction.is_active = False
        if highest:
            auction.winner = highest.bidder
            AuctionHistory.objects.create(
                auction=auction,
                user=highest.bidder,
                event=f"A câștigat licitația cu {highest.amount} RON"
            )
        else:
            AuctionHistory.objects.create(
                auction=auction,
                event="Licitația a fost închisă fără nicio ofertă."
            )
        auction.save()
        messages.success(request, "Licitația a fost închisă.")
    return redirect('auctions:auction_detail', product_slug=product_slug)
