from django import forms
from .models import Product, ProductImage
from django.forms import modelformset_factory


class BaseProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'brand', 'category', 'description',
            'listing_type', 'price', 'condition',
            'authenticity_proof', 'size', 'color', 'material', 'weight'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError("Prețul trebuie să fie pozitiv.")
        return price


class StoreProductForm(BaseProductForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['listing_type'].initial = 'store'
        self.fields['listing_type'].widget = forms.HiddenInput()


class AuctionProductForm(BaseProductForm):
    auction_duration_days = forms.IntegerField(label="Durată licitație (zile)", min_value=1, max_value=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['listing_type'].initial = 'auction'
        self.fields['listing_type'].widget = forms.HiddenInput()


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_primary']


# Formular pentru multiple imagini (FormSet)
ProductImageFormSet = modelformset_factory(
    ProductImage,
    form=ProductImageForm,
    extra=3,
    max_num=5,
    validate_max=True,
    can_delete=True
)
