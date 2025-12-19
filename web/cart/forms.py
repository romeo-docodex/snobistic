from django import forms


class CartAddProductForm(forms.Form):
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'width:80px; display:inline-block;',
        })
    )


class CouponApplyForm(forms.Form):
    code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cod promoțional',
        })
    )


class CheckoutForm(forms.Form):
    address = forms.ChoiceField(
        label="Adresă de livrare",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    shipping_method = forms.ChoiceField(
        choices=[('standard', 'Standard'), ('express', 'Express')],
        widget=forms.RadioSelect
    )

    payment_method = forms.ChoiceField(
        choices=[
            ('wallet', 'Wallet Snobistic'),
            ('card', 'Card bancar'),
            # PayPal rămâne rezervat pentru viitor, dar nu este afișat momentan în UI
            # ('paypal', 'PayPal'),
            ('cash_on_delivery', 'Cash la livrare'),
        ],
        widget=forms.RadioSelect
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
        error_messages={
            "required": "Trebuie să accepți termenii și condițiile pentru a continua."
        },
    )
