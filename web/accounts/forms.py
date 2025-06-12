# accounts/forms.py

from datetime import date, timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django_countries.widgets import CountrySelectWidget
from phonenumber_field.formfields import PhoneNumberField

from .models import CustomUser, UserProfile, UserAddress, EmailToken


def validate_minimum_age(value):
    """Verifică să fie cel puțin 18 ani."""
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 18:
        raise ValidationError(_("Trebuie să ai cel puțin 18 ani."))


def validate_iban(value):
    """Validare superficială IBAN (lungime între 15 și 34)."""
    iban = value.replace(' ', '').upper()
    if len(iban) < 15 or len(iban) > 34:
        raise ValidationError(_("IBAN invalid (lungime incorectă)."))


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={'class':'form-control'}))
    phone = PhoneNumberField(label=_("Telefon"), widget=forms.TextInput(attrs={'class':'form-control'}))
    birth_date = forms.DateField(
        label=_("Data nașterii"),
        validators=[validate_minimum_age],
        widget=forms.DateInput(attrs={'type': 'date', 'class':'form-control'})
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'phone', 'birth_date',
            'password1', 'password2', 'user_type', 'is_company', 'vat_payer'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class':'form-control'}),
            'user_type': forms.Select(attrs={'class':'form-select'}),
            'is_company': forms.CheckboxInput(attrs={'class':'form-check-input'}),
            'vat_payer': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError(_("Un cont cu acest email există deja."))
        return email


class ProfileForm(forms.ModelForm):
    iban = forms.CharField(
        required=False,
        validators=[validate_iban],
        widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'RO49...'})
    )

    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'iban', 'description',
            'shoulder', 'bust', 'waist', 'hips', 'length',
            'sleeve', 'leg_in', 'leg_out'
        ]
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'description': forms.Textarea(attrs={'class':'form-control', 'rows':3}),
            **{
                field: forms.NumberInput(attrs={'class':'form-control', 'step':'0.01'})
                for field in ['shoulder','bust','waist','hips','length','sleeve','leg_in','leg_out']
            }
        }


class CustomUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'phone', 'birth_date', 'user_type', 'is_company', 'vat_payer']
        widgets = {
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'phone': forms.TextInput(attrs={'class':'form-control'}),
            'birth_date': forms.DateInput(attrs={'type':'date','class':'form-control'}),
            'user_type': forms.Select(attrs={'class':'form-select'}),
            'is_company': forms.CheckboxInput(attrs={'class':'form-check-input'}),
            'vat_payer': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError(_("Email-ul este deja folosit de alt cont."))
        return email


class AddressForm(forms.ModelForm):
    class Meta:
        model = UserAddress
        fields = ['address_type', 'name', 'country', 'city', 'street_address', 'postal_code', 'is_default']
        widgets = {
            'address_type': forms.Select(attrs={'class':'form-select'}),
            'name': forms.TextInput(attrs={'class':'form-control'}),
            'country': CountrySelectWidget(attrs={'class':'form-select'}),
            'city': forms.TextInput(attrs={'class':'form-control'}),
            'street_address': forms.TextInput(attrs={'class':'form-control'}),
            'postal_code': forms.TextInput(attrs={'class':'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_default'):
            # Resetăm celelalte implicit
            UserAddress.objects.filter(
                user=self.instance.user or self.initial.get('user'),
                address_type=cleaned.get('address_type')
            ).update(is_default=False)
        return cleaned


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label=_("Parola actuală"),
        widget=forms.PasswordInput(attrs={'class':'form-control'})
    )
    new_password1 = forms.CharField(
        label=_("Noua parolă"),
        widget=forms.PasswordInput(attrs={'class':'form-control'})
    )
    new_password2 = forms.CharField(
        label=_("Confirmă noua parolă"),
        widget=forms.PasswordInput(attrs={'class':'form-control'})
    )


class TwoFactorForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label=_("Cod 2FA"),
        widget=forms.TextInput(attrs={'class':'form-control','placeholder':_('Introdu codul primit')})
    )


class ResendActivationForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={'class':'form-control'})
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if not CustomUser.objects.filter(email=email, is_active=False).exists():
            raise ValidationError(_("Nu există cont inactiv cu acest email."))
        return email


class ChangeEmailForm(forms.Form):
    new_email = forms.EmailField(
        label=_("Email nou"),
        widget=forms.EmailInput(attrs={'class':'form-control'})
    )
    password = forms.CharField(
        label=_("Parola"),
        widget=forms.PasswordInput(attrs={'class':'form-control'})
    )

    def clean_new_email(self):
        email = self.cleaned_data['new_email'].lower()
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError(_("Email-ul este deja folosit."))
        return email

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('password')
        if pwd and not self.initial.get('request').user.check_password(pwd):
            raise ValidationError({'password': _("Parolă incorectă.")})
        return cleaned
