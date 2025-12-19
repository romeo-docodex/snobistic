# auctions/forms.py
from decimal import Decimal

from django import forms

from .models import Auction, Bid, AuctionImage
from catalog.models import Product, Material  # <— use real size choices & materials


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class AuctionStep1Form(forms.ModelForm):
    images = forms.FileField(
        widget=MultiFileInput(attrs={'multiple': True}),
        required=True,
        help_text="Încarcă minim 3 imagini"
    )

    class Meta:
        model = Auction
        fields = ['product', 'category', 'images']
        widgets = {
            'product':  forms.HiddenInput(),
            'category': forms.HiddenInput(),
        }

    def clean_images(self):
        files = self.files.getlist('images')
        if len(files) < 3:
            raise forms.ValidationError("Trebuie să încarci minim 3 imagini.")
        return files

    def save(self, commit=True):
        """
        Saves auction instance and creates AuctionImage rows.
        Works whether instance was passed in or not.
        """
        auction = super().save(commit=commit)
        # IMPORTANT: create images after we have an ID
        for img in self.cleaned_data.get('images', []):
            AuctionImage.objects.create(auction=auction, image=img)
        return auction


class AuctionStep2Form(forms.ModelForm):
    # ensure we present the same size options as Products
    size = forms.ChoiceField(choices=[(s, s) for s, _ in Product.SIZE_CHOICES])

    class Meta:
        model = Auction
        fields = ['size']


class AuctionStep3Form(forms.ModelForm):
    class Meta:
        model = Auction
        fields = ['dimensions']
        widgets = {
            'dimensions': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': '{"Bust": "90 cm", "Talie": "70 cm"}'
            }),
        }


class AuctionStep4Form(forms.ModelForm):
    # store real materials (normalized) via M2M
    materials = forms.ModelMultipleChoiceField(
        queryset=Material.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Auction
        fields = ['materials', 'description']


class AuctionStep5Form(forms.ModelForm):
    class Meta:
        model = Auction
        fields = ['start_price', 'min_price', 'duration_days']

    def clean(self):
        data = super().clean()
        start_price = data.get('start_price') or Decimal('0')
        min_price   = data.get('min_price') or Decimal('0')
        if min_price < start_price:
            self.add_error('min_price', "Prețul minim (rezervă) trebuie să fie ≥ prețul de pornire.")
        return data


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount']

    def __init__(self, *args, auction=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.auction = auction
        self.user = user

    def clean_amount(self):
        amt = self.cleaned_data['amount']
        # next bid must be ≥ current_price (you can switch to > if you prefer)
        min_allowed = max(self.auction.current_price(), self.auction.start_price)
        if amt < min_allowed:
            raise forms.ValidationError(f"Suma trebuie să fie ≥ {min_allowed} RON.")
        return amt

    def save(self, commit=True):
        bid = super().save(commit=False)
        bid.auction = self.auction
        bid.user = self.user
        if commit:
            bid.save()
        return bid


class AuctionProductCreateForm(forms.ModelForm):
    """
    Formular minimal pentru a crea un Product nou,
    folosit EXCLUSIV ca bază pentru o licitație.
    """

    class Meta:
        model = Product
        fields = [
            "title",
            "description",
            "category",
            "size",
            "gender",
            "condition",
            "condition_notes",
            "main_image",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "size": forms.Select(attrs={"class": "form-select"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "condition_notes": forms.TextInput(attrs={"class": "form-control"}),
            "main_image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }

    def save(self, commit=True, owner=None):
        if owner is None:
            raise ValueError("owner is required for AuctionProductCreateForm.save()")

        product = super().save(commit=False)
        product.owner = owner
        product.sale_type = "AUCTION"

        # preț placeholder – va fi suprascris din setările licitației
        product.price = Decimal("0.01")
        product.quantity = 1
        product.is_active = True

        product.auction_start_price = None
        product.auction_buy_now_price = None
        product.auction_reserve_price = None
        product.auction_end_at = None

        if commit:
            product.save()
        return product
