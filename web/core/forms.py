from django import forms
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # honeypot simplu – câmp ascuns, trebuie să rămână gol
    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput
    )

    # consimțământ GDPR
    consent = forms.BooleanField(
        required=True,
        label="Sunt de acord ca datele mele să fie prelucrate pentru a primi un răspuns la mesaj."
    )

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message', 'consent', 'honeypot']

        labels = {
            'name': 'Nume',
            'email': 'Email',
            'subject': 'Subiect',
            'message': 'Mesaj',
        }

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numele tău',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'ex: nume@exemplu.com',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Subiectul mesajului',
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Scrie mesajul tău aici...',
            }),
        }
