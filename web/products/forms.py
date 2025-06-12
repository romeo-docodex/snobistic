from django import forms
from .models import Product, ProductImage
from django.forms import modelformset_factory


class BaseProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'brand', 'category', 'description',
            'listing_type', 'price', 'stock', 'condition',
            'authenticity_proof', 'size', 'color', 'material',
            'weight', 'meta_title', 'meta_description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'min': 0}),
            'meta_description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError("Prețul trebuie să fie pozitiv.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data['stock']
        if stock < 0:
            raise forms.ValidationError("Stock-ul nu poate fi negativ.")
        return stock


class StoreProductForm(BaseProductForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['listing_type'].initial = 'store'
        self.fields['listing_type'].widget = forms.HiddenInput()


class AuctionProductForm(BaseProductForm):
    auction_duration_days = forms.IntegerField(
        label="Durată licitație (zile)", min_value=1, max_value=30
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['listing_type'].initial = 'auction'
        self.fields['listing_type'].widget = forms.HiddenInput()


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_primary']


ProductImageFormSet = modelformset_factory(
    ProductImage,
    form=ProductImageForm,
    extra=3,
    max_num=5,
    validate_max=True,
    can_delete=True
)
