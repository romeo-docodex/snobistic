from django import forms
from .models import Bid, Auction
from django.utils import timezone


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sumă ofertată'})
        }

    def __init__(self, *args, **kwargs):
        self.auction = kwargs.pop('auction', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not self.auction:
            raise forms.ValidationError("Licitația este invalidă.")

        # Validare: timp activ
        now = timezone.now()
        if not (self.auction.start_time <= now <= self.auction.end_time):
            raise forms.ValidationError("Licitația a expirat sau nu a început încă.")

        # Validare: sumă minimă
        highest = self.auction.highest_bid()
        min_amount = highest.amount + 1 if highest else self.auction.starting_price
        if amount <= min_amount:
            raise forms.ValidationError(f"Oferta trebuie să fie mai mare decât {min_amount} RON.")

        return amount

    def save(self, commit=True):
        bid = super().save(commit=False)
        bid.auction = self.auction
        bid.bidder = self.user
        if commit:
            bid.save()
        return bid
