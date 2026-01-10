# auctions/forms.py
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Auction


class BidForm(forms.Form):
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))

    def __init__(self, *args, auction: Auction, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.auction = auction
        self.user = user

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        a = self.auction
        now = timezone.now()

        if a.status != Auction.Status.ACTIVE:
            raise ValidationError("Licitația nu este activă.")
        if a.start_time and a.start_time > now:
            raise ValidationError("Licitația nu a început încă.")
        if a.end_time and a.end_time <= now:
            raise ValidationError("Licitația este încheiată.")

        # anti self-bid (seller/owner)
        try:
            if self.user.is_authenticated:
                if self.user.id == a.creator_id or self.user.id == getattr(a.product, "owner_id", None):
                    raise ValidationError("Nu poți licita la propria ta licitație.")
        except Exception:
            pass

        min_allowed = a.min_next_bid()
        if Decimal(amount) < min_allowed:
            raise ValidationError(f"Oferta trebuie să fie ≥ {min_allowed} RON.")
        return amount
