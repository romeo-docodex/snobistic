# accounts/forms.py
from __future__ import annotations

import re
from datetime import date

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from .models import (
    Address,
    CustomUser,
    KycDocument,
    LegalAcceptance,
    Profile,
    SellerLocation,
    SellerProfile,
)


IBAN_RE = re.compile(r"^[A-Z0-9]{15,34}$")


def normalize_iban(value: str | None) -> str:
    return (value or "").replace(" ", "").upper().strip()


def validate_iban_basic(value: str) -> None:
    """
    Basic IBAN validation:
    - normalize (spaces removed, upper)
    - length 15–34
    - alphanumeric only
    (Optional: replace with python-stdnum / schwifty, etc.)
    """
    if not value:
        return
    if not IBAN_RE.match(value):
        raise forms.ValidationError(_("IBAN invalid."))


def _min_age_years() -> int:
    return int(getattr(settings, "ACCOUNTS_MIN_AGE_YEARS", 18))


def validate_min_age(dob: date | None) -> None:
    if not dob:
        return
    today = timezone.localdate()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < _min_age_years():
        raise forms.ValidationError(_("Trebuie să ai cel puțin %(age)s ani.") % {"age": _min_age_years()})


def _is_seller_user(user: CustomUser) -> bool:
    prof = getattr(user, "profile", None)
    return bool((prof and getattr(prof, "role_seller", False)) or getattr(user, "is_seller", False))


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(label=_("Parolă"), strip=False, widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False, initial=False, label=_("Ține-mă minte"))


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = (
        ("buyer", "Cumpărător"),
        ("seller", "Vânzător"),
    )

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect, label=_("Rol"), initial="buyer")

    first_name = forms.CharField(label=_("Prenume"))
    last_name = forms.CharField(label=_("Nume"))
    email = forms.EmailField(label=_("Email"))
    phone = PhoneNumberField(label=_("Telefon"))
    date_of_birth = forms.DateField(label=_("Data nașterii"), widget=forms.DateInput(attrs={"type": "date"}))

    company_vat = forms.CharField(required=False, label=_("CUI/TVA"))
    iban = forms.CharField(required=False, label=_("IBAN"))

    agree_terms = forms.BooleanField(label=_("Sunt de acord cu Termenii și Condițiile"))

    referral_code = forms.CharField(
        required=False,
        label=_("Cod recomandare (opțional)"),
        help_text=_("Dacă cineva ți-a recomandat Snobistic, introdu codul lui aici."),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError(_("Email invalid."))
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Există deja un cont cu acest email."))
        return email

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        validate_min_age(dob)
        return dob

    def clean_iban(self):
        iban = normalize_iban(self.cleaned_data.get("iban"))
        validate_iban_basic(iban)
        return iban

    def clean(self):
        cleaned = super().clean()

        role = cleaned.get("role")
        iban = cleaned.get("iban") or ""
        company_vat = (cleaned.get("company_vat") or "").strip()

        # seller requires iban
        if role == "seller" and not iban:
            self.add_error("iban", _("IBAN este obligatoriu pentru vânzători."))

        # company consistency (minimal)
        # NOTE: register only collects company_vat; other company fields are in ProfilePersonalForm
        # Policy: if company_vat present -> mark as company
        if company_vat:
            # nothing else to require here (no fields present), but keep normalized behavior
            cleaned["company_vat"] = company_vat

        return cleaned

    def clean_agree_terms(self):
        val = self.cleaned_data.get("agree_terms")
        if not val:
            raise forms.ValidationError(_("Trebuie să accepți Termenii și Condițiile."))
        return val

    def save(self, commit=True, *, ip: str | None = None, user_agent: str = ""):
        user = super().save(commit=False)

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.is_active = False

        role = self.cleaned_data.get("role")
        # legacy flag (will be synced anyway)
        user.is_seller = (role == "seller")

        if not commit:
            return user

        ua = (user_agent or "")[:1024]
        ip_val = ip or None

        try:
            with transaction.atomic():
                user.save()

                profile, _ = Profile.objects.get_or_create(user=user)
                profile.phone = self.cleaned_data["phone"]
                profile.date_of_birth = self.cleaned_data["date_of_birth"]

                company_vat = (self.cleaned_data.get("company_vat") or "").strip()
                profile.is_company = bool(company_vat)
                profile.company_vat = company_vat

                # ✅ SOURCE OF TRUTH
                profile.role_seller = (role == "seller")
                profile.role_buyer = True
                profile.save()

                if profile.role_seller:
                    seller, _ = SellerProfile.objects.get_or_create(user=user)
                    seller.iban = self.cleaned_data.get("iban") or ""
                    if profile.is_company:
                        seller.seller_type = SellerProfile.SELLER_TYPE_PROFESSIONAL
                    seller.save()

                    # best-effort default location
                    if not user.locations.exists():
                        SellerLocation.objects.create(user=user, code="USR", is_default=True)

                # Legal acceptances
                tos_ver = getattr(settings, "LEGAL_TOS_VERSION", "v1")
                privacy_ver = getattr(settings, "LEGAL_PRIVACY_VERSION", "v1")
                cookies_ver = getattr(settings, "LEGAL_COOKIES_VERSION", "v1")

                LegalAcceptance.objects.bulk_create(
                    [
                        LegalAcceptance(
                            user=user,
                            doc_type=LegalAcceptance.DOC_TERMS,
                            version=str(tos_ver),
                            ip=ip_val,
                            user_agent=ua,
                        ),
                        LegalAcceptance(
                            user=user,
                            doc_type=LegalAcceptance.DOC_PRIVACY,
                            version=str(privacy_ver),
                            ip=ip_val,
                            user_agent=ua,
                        ),
                        LegalAcceptance(
                            user=user,
                            doc_type=LegalAcceptance.DOC_COOKIES,
                            version=str(cookies_ver),
                            ip=ip_val,
                            user_agent=ua,
                        ),
                    ],
                    ignore_conflicts=True,
                )

                # Referral (best-effort)
                ref_code = (self.cleaned_data.get("referral_code") or "").strip()
                if ref_code and not user.referred_by_id:
                    inviter = CustomUser.objects.filter(referral_code__iexact=ref_code, is_active=True).first()
                    if inviter and inviter != user:
                        user.referred_by = inviter
                        user.save(update_fields=["referred_by"])

        except IntegrityError:
            raise forms.ValidationError(_("Există deja un cont cu acest email."))

        return user


class TwoFactorForm(forms.Form):
    code = forms.CharField(
        label=_("Cod 2FA sau cod de rezervă"),
        max_length=16,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )


class ProfilePersonalForm(forms.ModelForm):
    first_name = forms.CharField(label=_("Prenume"))
    last_name = forms.CharField(label=_("Nume"))
    phone = PhoneNumberField(label=_("Telefon"))
    date_of_birth = forms.DateField(label=_("Data nașterii"), widget=forms.DateInput(attrs={"type": "date"}))

    is_company = forms.BooleanField(required=False, label=_("Persoană juridică"))
    company_name = forms.CharField(required=False, label=_("Nume firmă"))
    company_address = forms.CharField(required=False, label=_("Adresă firmă"))
    company_vat = forms.CharField(required=False, label=_("CUI/TVA"))
    vat_payer = forms.BooleanField(required=False, label=_("Plătitor TVA"))

    iban = forms.CharField(required=False, label=_("IBAN"))

    class Meta:
        model = Profile
        fields = [
            "phone",
            "date_of_birth",
            "is_company",
            "company_name",
            "company_address",
            "company_vat",
            "vat_payer",
            "avatar",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = self.instance.user.first_name
        self.fields["last_name"].initial = self.instance.user.last_name

        seller = getattr(self.instance.user, "sellerprofile", None)
        if seller and "iban" in self.fields:
            self.fields["iban"].initial = seller.iban

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        validate_min_age(dob)
        return dob

    def clean_iban(self):
        iban = normalize_iban(self.cleaned_data.get("iban"))
        validate_iban_basic(iban)
        return iban

    def clean(self):
        cleaned = super().clean()

        # company auto-enable if VAT present
        company_vat = (cleaned.get("company_vat") or "").strip()
        if company_vat:
            cleaned["is_company"] = True
            cleaned["company_vat"] = company_vat

        is_company = bool(cleaned.get("is_company"))
        company_name = (cleaned.get("company_name") or "").strip()
        company_address = (cleaned.get("company_address") or "").strip()
        company_vat2 = (cleaned.get("company_vat") or "").strip()

        # ✅ Company consistency: if is_company OR vat present => require minimal fields
        if is_company or company_vat2:
            if not company_name:
                self.add_error("company_name", _("Numele firmei este obligatoriu."))
            if not company_address:
                self.add_error("company_address", _("Adresa firmei este obligatorie."))
            if not company_vat2:
                self.add_error("company_vat", _("CUI/TVA este obligatoriu."))

        # seller requires iban
        user = self.instance.user
        if _is_seller_user(user):
            iban = cleaned.get("iban") or ""
            if not iban:
                self.add_error("iban", _("IBAN este obligatoriu pentru vânzători."))

        return cleaned

    def save(self, commit=True):
        """
        ✅ PAS 6.1(5): commit=False fără DB writes.
        - nu salvează user, nu salvează sellerprofile, nu salvează profile
        """
        profile = super().save(commit=False)
        user = profile.user

        # apply user changes in-memory only
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        # apply company cleanup in-memory only
        if not profile.is_company:
            profile.company_name = ""
            profile.company_address = ""
            profile.company_vat = ""
            profile.vat_payer = False

        if not commit:
            return profile

        with transaction.atomic():
            # now we can persist
            user.save(update_fields=["first_name", "last_name"])
            profile.save()

            if _is_seller_user(user):
                seller, _ = SellerProfile.objects.get_or_create(user=user)
                iban_value = self.cleaned_data.get("iban") or ""
                if iban_value:
                    seller.iban = iban_value
                if profile.is_company and seller.seller_type == SellerProfile.SELLER_TYPE_PRIVATE:
                    seller.seller_type = SellerProfile.SELLER_TYPE_PROFESSIONAL
                seller.save()

        return profile


class ProfileDimensionsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "height_cm",
            "weight_kg",
            "shoulders",
            "bust",
            "waist",
            "hips",
            "length",
            "sleeve",
            "inseam",
            "outseam",
        ]


class ProfilePreferencesForm(forms.ModelForm):
    newsletter = forms.BooleanField(required=False, label=_("Primește newsletter"))
    marketing = forms.BooleanField(required=False, label=_("Marketing & oferte"))
    sms_notifications = forms.BooleanField(required=False, label=_("Notificări SMS"))

    class Meta:
        model = Profile
        fields = ["newsletter", "marketing", "sms_notifications"]


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "street_address",
            "building_info",
            "city",
            "region",
            "postal_code",
            "country",
            "is_billing",
            "is_default_shipping",
            "is_default_billing",
        ]


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

    def clean_iban(self):
        iban = normalize_iban(self.cleaned_data.get("iban"))
        validate_iban_basic(iban)
        return iban


class SellerLocationForm(forms.ModelForm):
    is_default = forms.BooleanField(required=False, label=_("Faceți această locație implicită"))

    class Meta:
        model = SellerLocation
        fields = ["code", "label", "is_default"]

    def __init__(self, *args, **kwargs):
        # allow passing user explicitly from view: form = SellerLocationForm(request.POST, user=request.user)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """
        ✅ PAS 6.1(4): default atomic.
        Dacă is_default=True, dezactivează restul în atomic.
        """
        obj = super().save(commit=False)

        if not commit:
            return obj

        with transaction.atomic():
            obj.save()
            if obj.is_default:
                SellerLocation.objects.filter(user=obj.user, is_default=True).exclude(pk=obj.pk).update(is_default=False)

        return obj


class DeleteAccountConfirmForm(forms.Form):
    code = forms.CharField(
        label=_("Cod de confirmare"),
        max_length=6,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
    )
    confirm_delete = forms.BooleanField(
        required=True,
        label=_("Înțeleg că această acțiune este ireversibilă și îmi va șterge contul."),
    )


class KycDocumentForm(forms.ModelForm):
    class Meta:
        model = KycDocument
        fields = ["document_type", "file"]


class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "is_active", "is_staff", "is_seller")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ 3.1: lock legacy flag in admin forms
        if "is_seller" in self.fields:
            self.fields["is_seller"].disabled = True
            self.fields["is_seller"].help_text = _("Derivat din Profile.role_seller (read-only).")
