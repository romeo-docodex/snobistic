# payments/forms.py
from django import forms
from .models import WalletTransaction


class TopUpForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=1,
        label="Sumă de încărcat (RON)",
    )
    method = forms.ChoiceField(
        choices=[("card", "Card bancar (Stripe)")],
        widget=forms.RadioSelect,
        label="Metodă de plată",
    )


class WithdrawForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=1, label="Sumă de retras (RON)"
    )
    iban = forms.CharField(max_length=34, label="IBAN destinatar")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_amount(self):
        amt = self.cleaned_data["amount"]
        if self.user.wallet.balance < amt:
            raise forms.ValidationError("Sold insuficient.")
        return amt
