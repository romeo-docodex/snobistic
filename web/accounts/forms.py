from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser, UserProfile, UserAddress
from django_countries.widgets import CountrySelectWidget
from phonenumber_field.formfields import PhoneNumberField


class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    phone = PhoneNumberField()
    birth_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'phone', 'birth_date',
            'password1', 'password2', 'user_type', 'is_company', 'vat_payer'
        ]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'iban', 'description',
            'shoulder', 'bust', 'waist', 'hips', 'length',
            'sleeve', 'leg_in', 'leg_out'
        ]


class CustomUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'phone', 'birth_date', 'user_type', 'is_company', 'vat_payer']


class AddressForm(forms.ModelForm):
    class Meta:
        model = UserAddress
        fields = ['address_type', 'name', 'country', 'city', 'street_address', 'postal_code', 'is_default']
        widgets = {
            'country': CountrySelectWidget()
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Parola actuală'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Noua parolă'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirmă noua parolă'}))


class TwoFactorForm(forms.Form):
    code = forms.CharField(max_length=6, label='Cod 2FA', widget=forms.TextInput(attrs={
        'placeholder': 'Introdu codul primit'
    }))


class ResendActivationForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class':'form-control'}))


class ChangeEmailForm(forms.Form):
    new_email = forms.EmailField(label="Email nou", widget=forms.EmailInput(attrs={'class':'form-control'}))
    password = forms.CharField(label="Parola", widget=forms.PasswordInput(attrs={'class':'form-control'}))
