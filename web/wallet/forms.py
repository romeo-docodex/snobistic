from django import forms
from .models import Transaction


class TopUpForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1,
        max_digits=10,
        decimal_places=2,
        label="Sumă de alimentat (RON)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'ex: 100.00'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Transfer bancar, Revolut...'})
    )


class PayoutForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1,
        max_digits=10,
        decimal_places=2,
        label="Sumă de retras (RON)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'ex: 50.00'})
    )
    iban = forms.CharField(
        max_length=34,
        label="Cont IBAN",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RO49AAAA1B31007593840000'})
    )


class TransactionFilterForm(forms.Form):
    type = forms.ChoiceField(
        choices=[('', 'Toate tipurile')] + Transaction.TRANSACTION_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        label="De la",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        label="Până la",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
