# messaging/forms.py
from __future__ import annotations

import os

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename


# ---- policy (poți muta în settings dacă vrei) ----
MAX_FILES_PER_MESSAGE = 5
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB / fișier

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_DOC_EXTS = {".pdf", ".txt"}
ALLOWED_EXTS = ALLOWED_IMAGE_EXTS | ALLOWED_DOC_EXTS

ALLOWED_MIME_PREFIXES = ("image/",)
ALLOWED_MIME_EXACT = {
    "application/pdf",
    "text/plain",
}


def _validate_upload(f) -> str:
    # sanitize nume
    original = os.path.basename(getattr(f, "name", "") or "")
    cleaned = get_valid_filename(original) or "file"
    ext = os.path.splitext(cleaned)[1].lower()

    if ext not in ALLOWED_EXTS:
        raise ValidationError(
            f"Tip fișier nepermis ({ext or 'fără extensie'}). Permise: {', '.join(sorted(ALLOWED_EXTS))}"
        )

    size = int(getattr(f, "size", 0) or 0)
    if size <= 0:
        raise ValidationError("Fișier invalid (mărime 0).")
    if size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"Fișier prea mare. Maxim {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB / fișier.")

    ct = (getattr(f, "content_type", "") or "").lower()
    if ct:
        ok = ct.startswith(ALLOWED_MIME_PREFIXES) or ct in ALLOWED_MIME_EXACT
        if not ok:
            raise ValidationError(f"Tip MIME nepermis: {ct}")

    return cleaned


class MultipleClearableFileInput(forms.ClearableFileInput):
    """
    Django default: ClearableFileInput NU suportă multiple.
    Fix: allow_multiple_selected = True
    """
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    Un FileField care acceptă listă de fișiere (multi-upload).
    """
    widget = MultipleClearableFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned_files = []
        for f in data:
            cleaned_files.append(super().clean(f, initial))
        return cleaned_files


class MessageForm(forms.Form):
    text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Scrie un mesaj…",
                "class": "form-control",
            }
        ),
    )

    attachments = MultipleFileField(
        required=False,
        widget=MultipleClearableFileInput(attrs={"class": "form-control", "multiple": True}),
    )

    def clean(self):
        cleaned = super().clean()

        text = (cleaned.get("text") or "").strip()
        files = cleaned.get("attachments") or []  # deja listă

        if not text and not files:
            raise ValidationError("Trimite un mesaj sau atașează unul sau mai multe fișiere.")

        if len(files) > MAX_FILES_PER_MESSAGE:
            raise ValidationError(f"Maxim {MAX_FILES_PER_MESSAGE} fișiere per mesaj.")

        # validate fiecare fișier (mărime/ext/mime)
        for f in files:
            _validate_upload(f)

        return cleaned
