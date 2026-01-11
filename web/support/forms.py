# support/forms.py
from django import forms
from django.db.models import Q

from .models import Ticket, TicketMessage
from orders.models import Order


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "description", "priority", "category", "order"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        labels = {
            "subject": "Subiect",
            "description": "Descriere",
            "priority": "Prioritate",
            "category": "Categorie",
            "order": "Comandă (opțional)",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].required = False

        if user is not None:
            qs = Order.objects.filter(Q(buyer=user) | Q(items__product__owner=user)).distinct()
            self.fields["order"].queryset = qs


class TicketMessageForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Scrie răspuns…"})}
        labels = {"text": ""}


class TicketUpdateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["status", "priority", "category", "order", "return_request"]
