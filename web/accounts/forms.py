from django import forms
from django.contrib.auth.forms import (
    UserCreationForm, AuthenticationForm,
    PasswordResetForm, SetPasswordForm, PasswordChangeForm
)
from phonenumber_field.formfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Profile, Address, SellerProfile, KycDocument


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={'autofocus': True})
    )
    password = forms.CharField(
        label=_('Parolă'),
        strip=False,
        widget=forms.PasswordInput
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Ține-mă minte')
    )


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = (
        ('buyer', 'Cumpărător'),
        ('seller', 'Vânzător'),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect,
        label=_('Rol'),
        initial='buyer',
    )

    first_name    = forms.CharField(label=_('Prenume'))
    last_name     = forms.CharField(label=_('Nume'))
    email         = forms.EmailField(label=_('Email'))
    phone         = PhoneNumberField(label=_('Telefon'))
    date_of_birth = forms.DateField(
        label=_('Data nașterii'),
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    # am SCOS is_company din formular
    company_vat   = forms.CharField(
        required=False,
        label=_('CUI/TVA')
    )
    iban          = forms.CharField(
        required=False,
        label=_('IBAN')
    )
    agree_terms   = forms.BooleanField(
        label=_('Sunt de acord cu Termenii și Condițiile')
    )

    referral_code = forms.CharField(
        required=False,
        label=_('Cod recomandare (opțional)'),
        help_text=_('Dacă cineva ți-a recomandat Snobistic, introdu codul lui aici.')
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ascundem textele lungi generate automat pentru parole
        self.fields['password1'].help_text = ''
        self.fields['password2'].help_text = ''

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        if role == 'seller' and not cleaned.get('iban'):
            self.add_error('iban', _('IBAN este obligatoriu pentru vânzători.'))
        return cleaned

    def clean_agree_terms(self):
        val = self.cleaned_data.get('agree_terms')
        if not val:
            raise forms.ValidationError(_("Trebuie să accepți Termenii și Condițiile."))
        return val

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.email      = self.cleaned_data['email']
        user.is_active  = False
        user.is_seller  = (self.cleaned_data['role'] == 'seller')

        if commit:
            user.save()

            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone         = self.cleaned_data['phone']
            profile.date_of_birth = self.cleaned_data['date_of_birth']

            # logica nouă: dacă CUI/TVA e completat => persoană juridică
            company_vat = (self.cleaned_data.get('company_vat') or "").strip()
            profile.is_company  = bool(company_vat)
            profile.company_vat = company_vat
            profile.save()

            if user.is_seller:
                seller, _ = SellerProfile.objects.get_or_create(user=user)
                seller.iban = self.cleaned_data['iban']
                if profile.is_company:
                    seller.seller_type = SellerProfile.SELLER_TYPE_PROFESSIONAL
                seller.save()

            ref_code = (self.cleaned_data.get('referral_code') or "").strip()
            if ref_code:
                inviter = CustomUser.objects.filter(referral_code__iexact=ref_code).first()
                if inviter and inviter != user:
                    user.referred_by = inviter
                    user.save(update_fields=["referred_by"])

        return user


class TwoFactorForm(forms.Form):
    # Max length mai mare pentru a permite și backup codes (8 caractere),
    # nu doar codurile 2FA de 6 cifre.
    code = forms.CharField(
        label=_('Cod 2FA sau cod de rezervă'),
        max_length=16,
        widget=forms.TextInput(attrs={'autocomplete': 'one-time-code'})
    )


class ProfilePersonalForm(forms.ModelForm):
    first_name    = forms.CharField(label=_('Prenume'))
    last_name     = forms.CharField(label=_('Nume'))
    phone         = PhoneNumberField(label=_('Telefon'))
    date_of_birth = forms.DateField(
        label=_('Data nașterii'),
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    is_company    = forms.BooleanField(
        required=False,
        label=_('Persoană juridică')
    )
    company_name = forms.CharField(
        required=False,
        label=_('Nume firmă')
    )
    company_address = forms.CharField(
        required=False,
        label=_('Adresă firmă')
    )
    company_vat   = forms.CharField(
        required=False,
        label=_('CUI/TVA')
    )
    vat_payer = forms.BooleanField(
        required=False,
        label=_('Plătitor TVA')
    )
    # IBAN nu e în Profile, ci în SellerProfile – îl mapăm manual
    iban = forms.CharField(
        required=False,
        label=_('IBAN')
    )

    class Meta:
        model  = Profile
        fields = [
            'phone',
            'date_of_birth',
            'is_company',
            'company_name',
            'company_address',
            'company_vat',
            'vat_payer',
            'avatar',
        ]
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill first/last name from User
        self.fields['first_name'].initial = self.instance.user.first_name
        self.fields['last_name'].initial  = self.instance.user.last_name

        # Pre-fill IBAN din SellerProfile, dacă există
        seller = getattr(self.instance.user, "sellerprofile", None)
        if seller and 'iban' in self.fields:
            self.fields['iban'].initial = seller.iban

    def save(self, commit=True):
        profile = super().save(commit=False)
        user    = profile.user

        # sincronizăm numele cu CustomUser
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.save()

        # dacă NU este companie, curățăm câmpurile de firmă
        if not profile.is_company:
            profile.company_name = ""
            profile.company_address = ""
            profile.company_vat = ""
            profile.vat_payer = False

        if commit:
            profile.save()

        # IBAN & logică seller profile (dacă userul este vânzător)
        iban_value = self.cleaned_data.get('iban', '').strip()
        if user.is_seller:
            seller, _ = SellerProfile.objects.get_or_create(user=user)
            if iban_value:
                seller.iban = iban_value
            # dacă profilul este company -> forțăm PROFESSIONAL by default
            if profile.is_company and seller.seller_type == SellerProfile.SELLER_TYPE_PRIVATE:
                seller.seller_type = SellerProfile.SELLER_TYPE_PROFESSIONAL
            seller.save()

        return profile


class ProfileDimensionsForm(forms.ModelForm):
    """
    Let users record their own body measurements.
    """
    class Meta:
        model = Profile
        fields = [
            'height_cm',
            'weight_kg',
            'shoulders',
            'bust',
            'waist',
            'hips',
            'length',
            'sleeve',
            'inseam',
            'outseam',
        ]
        widgets = {
            'height_cm': forms.NumberInput(attrs={
                'placeholder': 'Ex: 170',
                'min': 100,
                'max': 230,
            }),
            'weight_kg': forms.NumberInput(attrs={
                'placeholder': 'Ex: 65.5',
                'step': '0.1',
                'min': 30,
                'max': 250,
            }),
            'shoulders': forms.TextInput(attrs={'placeholder': 'Ex: 45 cm'}),
            'bust':      forms.TextInput(attrs={'placeholder': 'Ex: 90 cm'}),
            'waist':     forms.TextInput(attrs={'placeholder': 'Ex: 70 cm'}),
            'hips':      forms.TextInput(attrs={'placeholder': 'Ex: 95 cm'}),
            'length':    forms.TextInput(attrs={'placeholder': 'Ex: 120 cm'}),
            'sleeve':    forms.TextInput(attrs={'placeholder': 'Ex: 60 cm'}),
            'inseam':    forms.TextInput(attrs={'placeholder': 'Ex: 75 cm'}),
            'outseam':   forms.TextInput(attrs={'placeholder': 'Ex: 100 cm'}),
        }


class ProfilePreferencesForm(forms.ModelForm):
    newsletter        = forms.BooleanField(required=False, label=_('Primește newsletter'))
    marketing         = forms.BooleanField(required=False, label=_('Marketing & oferte'))
    sms_notifications = forms.BooleanField(required=False, label=_('Notificări SMS'))

    class Meta:
        model  = Profile
        fields = ['newsletter', 'marketing', 'sms_notifications']
        widgets = {
            'newsletter':        forms.CheckboxInput(attrs={'class': 'form-check-input', 'autocomplete': 'off'}),
            'marketing':         forms.CheckboxInput(attrs={'class': 'form-check-input', 'autocomplete': 'off'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input', 'autocomplete': 'off'}),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "street_address", "building_info", "city",
            "region", "postal_code", "country",
            "is_billing", "is_default_shipping", "is_default_billing",
        ]
        widgets = {
            "is_billing": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_default_shipping": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_default_billing": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


# --- Setări vânzător (IBAN & livrare)
class SellerSettingsForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = [
            "seller_type",
            "iban",
            "accept_cod",
            "allow_local_pickup",
            "local_delivery_radius_km",
            "max_cod_value",
        ]
        widgets = {
            "iban": forms.TextInput(attrs={"placeholder": "RO49AAAA1B31007593840000"}),
            "local_delivery_radius_km": forms.NumberInput(attrs={"min": 0, "max": 200}),
            "max_cod_value": forms.NumberInput(attrs={"step": "0.01"}),
        }


# --- Locație vânzător
class SellerLocationForm(forms.ModelForm):
    is_default = forms.BooleanField(required=False, label=_("Faceți această locație implicită"))

    class Meta:
        from .models import SellerLocation
        model = SellerLocation
        fields = ["code", "label", "is_default"]
        widgets = {
            "code": forms.TextInput(attrs={"maxlength": 3, "placeholder": "ex: ORA"}),
            "label": forms.TextInput(attrs={"placeholder": "ex: Oradea"}),
        }


class DeleteAccountConfirmForm(forms.Form):
    code = forms.CharField(
        label=_("Cod de confirmare"),
        max_length=6,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"})
    )
    confirm_delete = forms.BooleanField(
        required=True,
        label=_("Înțeleg că această acțiune este ireversibilă și îmi va șterge contul.")
    )


# --- KYC document upload form
class KycDocumentForm(forms.ModelForm):
    class Meta:
        model = KycDocument
        fields = ["document_type", "file"]
        widgets = {
            "document_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_seller')
