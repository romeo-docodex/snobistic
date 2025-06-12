from django.utils import timezone
from .models import Auction, AuctionHistory


def close_expired_auctions():
    """
    Închide toate licitațiile care au trecut de `end_time`
    și sunt încă active.
    """
    now = timezone.now()
    expired_auctions = Auction.objects.filter(end_time__lt=now, is_active=True)

    for auction in expired_auctions:
        highest = auction.highest_bid()

        if highest:
            auction.winner = highest.bidder
            AuctionHistory.objects.create(
                auction=auction,
                user=highest.bidder,
                event=f"Licitația a fost închisă automat. Câștigător: {highest.bidder.email} - {highest.amount} RON"
            )
        else:
            AuctionHistory.objects.create(
                auction=auction,
                event="Licitația a fost închisă automat. Nicio ofertă înregistrată."
            )

        auction.is_active = False
        auction.save()
