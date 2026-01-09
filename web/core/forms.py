# core/forms.py
from django import forms
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # honeypot simplu – câmp ascuns, trebuie să rămână gol
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message", "consent"]  # ✅ fără honeypot

        labels = {
            "name": "Nume",
            "email": "Email",
            "subject": "Subiect",
            "message": "Mesaj",
            "consent": "Sunt de acord ca datele mele să fie prelucrate pentru a primi un răspuns la mesaj.",
        }

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Numele tău"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "ex: nume@exemplu.com"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Subiectul mesajului"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "Scrie mesajul tău aici..."}),
        }

    def clean_honeypot(self):
        val = (self.cleaned_data.get("honeypot") or "").strip()
        if val:
            # nu aruncăm eroare “vizibilă”, doar o tratăm ca spam în view
            return val
        return ""

    def clean_subject(self):
        subject = (self.cleaned_data.get("subject") or "").strip()
        # prevenim header injection (CRLF)
        subject = subject.replace("\r", " ").replace("\n", " ")
        return subject
