# auctions/forms_wizard.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalog.forms_wizard import ProductPhotosForm
from catalog.models import Brand, Category, Subcategory, Product, ProductImage
from .models import Auction


class AuctionPhotosMetaForm(ProductPhotosForm):
    """
    Step 1 (CREATE): upload imagini + metadata (titlu + descriere).
    Refolosim logica robustă de imagini din ProductPhotosForm.
    """

    title = forms.CharField(
        label=_("Titlu"),
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ex: Rochie midi satinată verde"}
        ),
    )

    description = forms.CharField(
        label=_("Descriere"),
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Descrie produsul (material, croi, cum se așază, defecte etc.)",
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        cleaned["title"] = (cleaned.get("title") or "").strip()
        cleaned["description"] = (cleaned.get("description") or "").strip()

        if not cleaned["title"]:
            self.add_error("title", _("Te rog să completezi titlul."))
        if not cleaned["description"]:
            self.add_error("description", _("Te rog să completezi descrierea."))

        return cleaned


class AuctionExistingPhotosMetaForm(forms.Form):
    """
    Step 1 (EDIT): fără upload. Folosim DOAR imaginile existente ale produsului.
    Permitem:
      - reorder prin photos_order (chei: 'm' pentru main, 'e<ID>' pentru ProductImage)
      - setare main prin main_choice
      - edit titlu + descriere
    """

    photos_order = forms.CharField(required=False, widget=forms.HiddenInput())
    main_choice = forms.CharField(required=False, widget=forms.HiddenInput())

    title = forms.CharField(
        label=_("Titlu"),
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ex: Rochie midi satinată verde"}
        ),
    )

    description = forms.CharField(
        label=_("Descriere"),
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Descrie produsul (material, croi, cum se așază, defecte etc.)",
            }
        ),
    )

    def __init__(self, *args, product: Product, **kwargs):
        # ✅ IMPORTANT: scoatem kwargs custom venite din wizard (altfel ajung în BaseForm.__init__)
        self.require_min_photos = bool(kwargs.pop("require_min_photos", False))
        self.existing_photos_count = kwargs.pop("existing_photos_count", None)

        self.product = product
        super().__init__(*args, **kwargs)

        if not self.is_bound:
            keys = []
            if getattr(product, "main_image", None):
                keys.append("m")

            try:
                qs = product.images.all().order_by("position", "id")
            except Exception:
                qs = ProductImage.objects.filter(product=product).order_by("position", "id")

            keys.extend([f"e{im.pk}" for im in qs])

            self.initial.setdefault("photos_order", ",".join(keys))
            if keys:
                self.initial.setdefault("main_choice", "m" if "m" in keys else keys[0])

    def _available_keys(self) -> list[str]:
        keys = []
        if getattr(self.product, "main_image", None):
            keys.append("m")

        try:
            qs = self.product.images.all().order_by("position", "id")
        except Exception:
            qs = ProductImage.objects.filter(product=self.product).order_by("position", "id")

        keys.extend([f"e{im.pk}" for im in qs])
        return keys

    def clean(self):
        cleaned = super().clean()
        cleaned["title"] = (cleaned.get("title") or "").strip()
        cleaned["description"] = (cleaned.get("description") or "").strip()

        if not cleaned["title"]:
            self.add_error("title", _("Te rog să completezi titlul."))
        if not cleaned["description"]:
            self.add_error("description", _("Te rog să completezi descrierea."))

        available = self._available_keys()

        # ✅ enforce min photos only if asked (wizard îți trimite True)
        if self.require_min_photos and len(available) < 4:
            raise forms.ValidationError(
                _("Produsul trebuie să aibă minim 4 poze (imagine principală + cel puțin 3 imagini suplimentare).")
            )

        raw_order = (cleaned.get("photos_order") or "").strip()
        order = []
        seen = set()

        if raw_order:
            for k in [x.strip() for x in raw_order.split(",") if x.strip()]:
                if k in available and k not in seen:
                    order.append(k)
                    seen.add(k)

        # append any missing keys (safety)
        for k in available:
            if k not in seen:
                order.append(k)
                seen.add(k)

        main_choice = (cleaned.get("main_choice") or "").strip()
        if main_choice not in available:
            main_choice = order[0] if order else (available[0] if available else "")

        cleaned["photos_order_norm"] = order
        cleaned["main_choice_norm"] = main_choice
        return cleaned


class AuctionCategoryBrandForm(forms.Form):
    """
    Step 2: Categorie + subcategorie + brand.
    (fără gender — cerința ta)
    """

    category = forms.ModelChoiceField(
        label=_("Categorie"),
        queryset=Category.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    subcategory = forms.ModelChoiceField(
        label=_("Subcategorie"),
        queryset=Subcategory.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    brand = forms.ModelChoiceField(
        label=_("Brand"),
        queryset=Brand.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    brand_other = forms.CharField(
        label=_("Alt brand (dacă nu e în listă)"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = Category.objects.all().order_by("name")
        self.fields["brand"].queryset = Brand.objects.all().order_by("name")

        sub_qs = Subcategory.objects.none()
        data = self.data if self.is_bound else None

        category_obj = None
        if data:
            cat_key = self.add_prefix("category")
            if cat_key in data:
                try:
                    category_id = int(data.get(cat_key))
                    category_obj = Category.objects.filter(pk=category_id).first()
                    if category_obj:
                        sub_qs = Subcategory.objects.filter(category=category_obj)
                except (TypeError, ValueError):
                    pass

        if not category_obj and self.initial.get("category"):
            category_obj = self.initial["category"]
            sub_qs = Subcategory.objects.filter(category=category_obj)

        initial_sub = self.initial.get("subcategory")
        if initial_sub:
            sub_qs = (sub_qs | Subcategory.objects.filter(pk=getattr(initial_sub, "pk", initial_sub))).distinct()

        self.fields["subcategory"].queryset = sub_qs.order_by("name")

    def clean(self):
        cleaned = super().clean()

        brand = cleaned.get("brand")
        brand_other = (cleaned.get("brand_other") or "").strip()
        cleaned["brand_other"] = brand_other

        category = cleaned.get("category")
        subcategory = cleaned.get("subcategory")

        if brand and brand_other:
            self.add_error("brand_other", _("Alege fie un brand din listă, fie completează „Alt brand”, nu ambele."))

        if not brand and not brand_other:
            self.add_error("brand", _("Alege un brand din listă sau completează câmpul „Alt brand”."))

        if not category:
            self.add_error("category", _("Alege o categorie."))

        if subcategory and category and subcategory.category_id != category.id:
            self.add_error("subcategory", _("Subcategoria aleasă nu aparține categoriei selectate."))

        return cleaned


class AuctionSettingsForm(forms.ModelForm):
    """
    Step 5: Setări licitație.
    """

    start_time = forms.DateTimeField(
        label=_("Data/ora de start"),
        required=False,
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        help_text=_("Dacă lași gol, pornește imediat la finalizarea formularului."),
    )

    class Meta:
        model = Auction
        fields = [
            "start_price",
            "reserve_price",
            "duration_days",
            "min_increment_percent",
            "payment_window_hours",
            "start_time",
        ]
        labels = {
            "start_price": _("Preț de pornire (RON)"),
            "reserve_price": _("Preț de rezervă (RON)"),
            "duration_days": _("Durată (zile)"),
            "min_increment_percent": _("Increment minim (%)"),
            "payment_window_hours": _("Fereastră plată câștigător (ore)"),
        }
        widgets = {
            "start_price": forms.NumberInput(attrs={"class": "form-control", "min": "10", "step": "0.01"}),
            "reserve_price": forms.NumberInput(attrs={"class": "form-control", "min": "10", "step": "0.01"}),
            "duration_days": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1"}),
            "min_increment_percent": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1"}),
            "payment_window_hours": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1"}),
        }

    def clean_start_price(self):
        v = self.cleaned_data.get("start_price")
        if v is None:
            raise forms.ValidationError(_("Te rog să introduci un preț de pornire."))
        if v < Decimal("10.00"):
            raise forms.ValidationError(_("Minim 10 RON."))
        return v

    def clean(self):
        cleaned = super().clean()

        start_price = cleaned.get("start_price")
        reserve_price = cleaned.get("reserve_price")

        if reserve_price is not None and start_price is not None and reserve_price < start_price:
            self.add_error("reserve_price", _("Rezerva trebuie să fie ≥ prețul de pornire."))

        st = cleaned.get("start_time")
        if st:
            if st < timezone.now() - timedelta(days=1):
                self.add_error("start_time", _("Data de start pare în trecut. Corectează, te rog."))

        return cleaned
