# wallet/forms.py
from decimal import Decimal

from django import forms

from .models import WithdrawalRequest


class TopUpForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("1.00"),
        label="Sumă de încărcat (RON)",
    )
    method = forms.ChoiceField(
        choices=[("card", "Card bancar (Stripe)")],
        widget=forms.RadioSelect,
        label="Metodă de plată",
    )


class WithdrawForm(forms.ModelForm):
    class Meta:
        model = WithdrawalRequest
        fields = ["amount", "iban"]

    def __init__(self, *args, wallet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.wallet = wallet

    def clean_amount(self):
        amt = self.cleaned_data["amount"]
        if not self.wallet:
            return amt
        if self.wallet.balance < amt:
            raise forms.ValidationError("Sold insuficient.")
        return amt
