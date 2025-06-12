from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(
        label="Nume",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numele tău'})
    )

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplu.com'})
    )

    message = forms.CharField(
        label="Mesaj",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Scrie mesajul aici...'})
    )
