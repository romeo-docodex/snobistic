from django import forms
from .models import ReturnRequest, Order

class OrderAddressForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['shipping_address', 'billing_address']
        widgets = {
            'shipping_address': forms.Textarea(attrs={
                'class':'form-control','rows':3,'placeholder':'Adresă de livrare'
            }),
            'billing_address': forms.Textarea(attrs={
                'class':'form-control','rows':3,'placeholder':'Adresă de facturare (opțional)'
            }),
        }
        labels = {
            'shipping_address': 'Adresă de livrare',
            'billing_address': 'Adresă de facturare (opțional)',
        }

class ReturnRequestForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={
                'class':'form-control','rows':4,
                'placeholder':'Motivul returului...'
            }),
        }
        labels = {'reason':'Motivul returului'}
