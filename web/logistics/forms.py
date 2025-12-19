# logistics/forms.py
from django import forms

from .models import Shipment


class ShipmentCreateForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = [
            "weight_kg",
            "service_name",
            "cash_on_delivery",
            "cod_amount",
            "package_photo",
            "parcel_photo",
        ]
        widgets = {
            "weight_kg": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.1", "min": "0.1"}
            ),
            "service_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: Standard, Easybox, SameDay",
                }
            ),
            "cash_on_delivery": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "cod_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        cod = cleaned.get("cash_on_delivery")
        amt = cleaned.get("cod_amount")

        if cod and (amt is None or amt <= 0):
            self.add_error("cod_amount", "Introdu o sumă ramburs > 0.")
        if not cod:
            cleaned["cod_amount"] = 0
        return cleaned
