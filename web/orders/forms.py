# orders/forms.py
from django import forms
from accounts.models import Address
from .models import ReturnRequest


class OrderAddressForm(forms.Form):
    shipping_address = forms.ModelChoiceField(
        label='Adresă de livrare',
        queryset=Address.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    billing_address = forms.ModelChoiceField(
        label='Adresă de facturare (opțional)',
        queryset=Address.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            qs = Address.objects.filter(user=user)
            self.fields['shipping_address'].queryset = qs
            self.fields['billing_address'].queryset = qs


class ReturnRequestForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Motivul returului...'
            }),
        }
        labels = {'reason': 'Motivul returului'}
