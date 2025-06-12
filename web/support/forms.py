from django import forms
from .models import SupportTicket


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['subject', 'description', 'attachment']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titlul cererii'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Descrie problema ta...'
            }),
            'attachment': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'subject': 'Subiect',
            'description': 'Descriere',
            'attachment': 'Fișier atașat (opțional)',
        }


class SupportTicketUpdateForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['status', 'assigned_to']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'status': 'Status',
            'assigned_to': 'Atribuit către',
        }
