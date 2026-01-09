# cart/forms.py
from django import forms


class CartAddProductForm(forms.Form):
    """
    qty=1 policy: păstrăm form-ul doar pentru compat, fără quantity.
    """
    product_id = forms.IntegerField(widget=forms.HiddenInput)


class CouponApplyForm(forms.Form):
    code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Cod promoțional",
            }
        ),
    )

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise forms.ValidationError("Introdu un cod promoțional.")
        return code


class CheckoutForm(forms.Form):
    address = forms.ChoiceField(label="Adresă de livrare", widget=forms.Select(attrs={"class": "form-select"}))

    shipping_method = forms.ChoiceField(
        choices=[("standard", "Standard"), ("express", "Express")],
        widget=forms.RadioSelect,
    )

    payment_method = forms.ChoiceField(
        choices=[
            ("wallet", "Wallet Snobistic"),
            ("card", "Card bancar"),
            ("cash_on_delivery", "Cash la livrare"),
        ],
        widget=forms.RadioSelect,
    )

    agree_terms = forms.BooleanField(
        label="Sunt de acord cu termenii și condițiile",
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "tf-check",
                "id": "check-agree",
            }
        ),
        error_messages={"required": "Trebuie să accepți termenii și condițiile pentru a continua."},
    )
