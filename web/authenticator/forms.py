# authenticator/forms.py
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import AuthRequest, AuthImage


ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_FILES = 5
MAX_FILE_SIZE_MB = 8


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class AuthUploadForm(forms.ModelForm):
    images = forms.FileField(
        widget=MultiFileInput(attrs={"class": "form-control"}),
        required=True,
        label="Imagini produs",
        help_text=f"Încarcă între 1 și {MAX_FILES} imagini (JPG/PNG/WEBP).",
    )

    class Meta:
        model = AuthRequest
        fields = [
            "email",
            "product",
            "brand_text",
            "model_text",
            "serial_number",
            "notes",
            "images",
        ]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email (doar dacă nu ai cont)"}),
            "product": forms.HiddenInput(),
            "brand_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Gucci"}),
            "model_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Ace GG Supreme"}),
            "serial_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opțional"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Opțional"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

        # email only required for guests
        if user and getattr(user, "is_authenticated", False):
            self.fields["email"].required = False
        else:
            self.fields["email"].required = True

    def clean_images(self):
        files = self.files.getlist("images")
        if not files:
            raise ValidationError("Trebuie să încarci cel puțin o imagine.")
        if len(files) > MAX_FILES:
            raise ValidationError(f"Poți încărca maximum {MAX_FILES} imagini.")

        for f in files:
            if hasattr(f, "content_type") and f.content_type not in ALLOWED_IMAGE_MIME:
                raise ValidationError("Formate permise: JPG, PNG, WEBP.")
            size_mb = (f.size or 0) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                raise ValidationError(f"Un fișier este prea mare. Maxim {MAX_FILE_SIZE_MB}MB per imagine.")
        return files

    def clean(self):
        cleaned = super().clean()

        user = self._user
        if not (user and getattr(user, "is_authenticated", False)):
            email = (cleaned.get("email") or "").strip()
            if not email:
                self.add_error("email", "Email-ul este obligatoriu dacă nu ai cont.")

        brand = (cleaned.get("brand_text") or "").strip()
        model = (cleaned.get("model_text") or "").strip()
        if not brand:
            self.add_error("brand_text", "Brand-ul este obligatoriu.")
        if not model:
            self.add_error("model_text", "Modelul este obligatoriu.")

        return cleaned

    def save_request(self) -> AuthRequest:
        """
        Salvează AuthRequest + toate imaginile asociate.
        IMPORTANT: nu folosi commit=False în view; aici controlăm tot flow-ul.
        """
        req: AuthRequest = super().save(commit=False)

        user = self._user
        if user and getattr(user, "is_authenticated", False):
            req.user = user
            req.email = ""  # optional; keep clean
        else:
            req.email = (self.cleaned_data.get("email") or "").strip()

        req.submitted_at = req.submitted_at or None  # keep default
        req.status = AuthRequest.Status.PENDING
        req.verdict = AuthRequest.Verdict.PENDING

        req.save()

        files = self.files.getlist("images")
        for idx, f in enumerate(files):
            AuthImage.objects.create(auth_request=req, image=f, position=idx)

        return req
