# accounts/forms.py

from datetime import date
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_countries.widgets import CountrySelectWidget
from phonenumber_field.formfields import PhoneNumberField

from .models import CustomUser, UserProfile, UserAddress


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ex: you@example.com'})
    )
    phone = PhoneNumberField(
        label="Telefon",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: +40741234567'})
    )
    birth_date = forms.DateField(
        label="Data nașterii",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'phone', 'birth_date',
            'password1', 'password2', 'user_type', 'is_company', 'vat_payer'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'user_type': forms.Select(attrs={'class': 'form-select'}),
            'is_company': forms.CheckboxInput(),
            'vat_payer': forms.CheckboxInput(),
        }

    def clean_birth_date(self):
        bd = self.cleaned_data['birth_date']
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        if age < 18:
            raise ValidationError("Trebuie să ai cel puțin 18 ani pentru a te înregistra.")
        return bd


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'iban', 'description',
            'shoulder', 'bust', 'waist', 'hips', 'length',
            'sleeve', 'leg_in', 'leg_out'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'iban': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RO49AAAA1B31007593840000'}),
        }

    def clean_iban(self):
        iban = self.cleaned_data.get('iban', '').replace(' ', '')
        if iban and (len(iban) < 15 or len(iban) > 34 or not iban.isalnum()):
            raise ValidationError("IBAN pare invalid.")
        return iban


class CustomUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'phone', 'birth_date', 'user_type', 'is_company', 'vat_payer']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'user_type': forms.Select(attrs={'class': 'form-select'}),
            'is_company': forms.CheckboxInput(),
            'vat_payer': forms.CheckboxInput(),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = UserAddress
        fields = ['address_type', 'name', 'country', 'city', 'street_address', 'postal_code', 'is_default']
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'country': CountrySelectWidget(attrs={'class': 'form-select'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Parola actuală'}),
        label="Parola actuală"
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Noua parolă'}),
        label="Noua parolă"
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmă noua parolă'}),
        label="Confirmare parolă"
    )


class TwoFactorForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label='Cod 2FA',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Introdu codul primit'})
    )


class ResendActivationForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
        label="Email"
    )


class ChangeEmailForm(forms.Form):
    new_email = forms.EmailField(
        label="Email nou",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ex: new@example.com'})
    )
    password = forms.CharField(
        label="Parolă actuală",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Parola ta'})
    )

    def clean_new_email(self):
        email = self.cleaned_data['new_email']
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("Acest email este deja folosit.")
        return email
