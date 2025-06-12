# web/accounts/forms.py
from django import forms
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django_countries.widgets import CountrySelectWidget
from phonenumber_field.formfields import PhoneNumberField

from .models import CustomUser, UserProfile, UserAddress


class RegisterForm(UserCreationForm):
    email      = forms.EmailField()
    phone      = PhoneNumberField(required=False)
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model  = CustomUser
        fields = [
            'username','email','phone','birth_date',
            'password1','password2','user_type','is_company','vat_payer'
        ]

    def clean_birth_date(self):
        bd = self.cleaned_data.get('birth_date')
        if bd:
            age = (timezone.now().date() - bd).days // 365
            if age < 18:
                raise forms.ValidationError("Trebuie să ai cel puțin 18 ani.")
        return bd


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = UserProfile
        fields = [
            'avatar','iban','description',
            'shoulder','bust','waist','hips',
            'length','sleeve','leg_in','leg_out'
        ]


class CustomUserForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['email','phone','birth_date','user_type','is_company','vat_payer']


class AddressForm(forms.ModelForm):
    class Meta:
        model  = UserAddress
        fields = [
            'address_type','name','country',
            'city','street_address','postal_code','is_default'
        ]
        widgets = {
            'country': CountrySelectWidget()
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password  = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder':'Parola actuală'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder':'Noua parolă'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder':'Confirmă noua parolă'}))


class TwoFactorForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label='Cod 2FA',
        widget=forms.TextInput(attrs={'placeholder':'Introdu codul primit'})
    )


class ResendActivationForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class':'form-control','placeholder':'Email'}))


class ChangeEmailForm(forms.Form):
    new_email = forms.EmailField(
        label="Email nou",
        widget=forms.EmailInput(attrs={'class':'form-control'})
    )
    password = forms.CharField(
        label="Parola",
        widget=forms.PasswordInput(attrs={'class':'form-control'})
    )

    def clean_new_email(self):
        e = self.cleaned_data['new_email']
        if CustomUser.objects.filter(email=e).exists():
            raise forms.ValidationError("Acest email este deja folosit.")
        return e


class ReactivateForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class':'form-control','placeholder':'Email'
    }))

    def clean_email(self):
        e = self.cleaned_data['email']
        if not CustomUser.objects.filter(email=e, deleted_at__isnull=False).exists():
            raise forms.ValidationError("Nu există cont dezactivat cu acest email.")
        return e
