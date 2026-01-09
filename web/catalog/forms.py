# catalog/forms.py
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Any

from django import forms
from django.db.models import Q

from .models import (
    Product,
    Category,
    Subcategory,
    Brand,
    Material,
)


class SearchForm(forms.Form):
    q = forms.CharField(
        label="",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Caută produse…", "class": "form-control"}
        ),
    )


def _flatten_files(value: Any) -> List[Any]:
    """
    Wizard storage poate returna:
      - [] / None
      - UploadedFile
      - [UploadedFile, UploadedFile, ...]
      - [[UploadedFile, ...]]  (nested)
    Vrem mereu listă plată de UploadedFile.
    """
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        out: List[Any] = []
        for v in value:
            out.extend(_flatten_files(v))
        return out
    return [value]


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        """
        IMPORTANT:
        - In request.FILES (MultiValueDict), getlist(name) funcționează.
        - In wizard storage, uneori `files.get(name)` poate fi LISTĂ de fișiere.
        """
        if hasattr(files, "getlist"):
            return files.getlist(name)

        val = files.get(name)
        if not val:
            return []

        # dacă storage a pus deja listă/tuplu
        if isinstance(val, (list, tuple)):
            return list(val)

        return [val]


class MultiImageField(forms.Field):
    widget = MultiFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        return _flatten_files(value)


class ProductForm(forms.ModelForm):
    """
    ⚠️ Fallback / legacy form.
    Wizard-ul (forms_wizard.py) este sursa principală de adevăr pentru reguli,
    dar dacă păstrezi acest form pentru staff / debug, îl facem “corect”:
    - min 4 poze
    - dimensiuni obligatorii în funcție de measurement_profile (nu “min 3 dims” global)
    - subcategorie filtrată după categorie
    """

    extra_images = MultiImageField(
        label="Imagini suplimentare",
        help_text=(
            "Produsul trebuie să aibă în total minim 4 poze "
            "(imagine principală + cel puțin 3 imagini suplimentare)."
        ),
        widget=MultiFileInput(
            attrs={
                "multiple": True,
                "class": "form-control",
                "accept": "image/*",
            }
        ),
        required=False,
    )

    # Dimensiuni obligatorii pe profil (aliniat cu ProductDimensionsForm din wizard)
    REQUIRED_BY_PROFILE = {
        Subcategory.MeasurementProfile.TOP: ["bust_cm", "waist_cm", "length_cm"],
        Subcategory.MeasurementProfile.DRESS: ["bust_cm", "waist_cm", "hips_cm", "length_cm"],
        Subcategory.MeasurementProfile.JUMPSUIT: ["bust_cm", "waist_cm", "hips_cm", "length_cm", "inseam_cm"],
        Subcategory.MeasurementProfile.PANTS: ["waist_cm", "hips_cm", "inseam_cm", "length_cm"],
        Subcategory.MeasurementProfile.SKIRT: ["waist_cm", "hips_cm", "length_cm"],
        Subcategory.MeasurementProfile.SHOES: ["shoe_insole_length_cm"],
        Subcategory.MeasurementProfile.BAGS: ["bag_width_cm", "bag_height_cm"],
        Subcategory.MeasurementProfile.BELTS: ["belt_length_total_cm", "belt_length_usable_cm", "belt_width_cm"],
        Subcategory.MeasurementProfile.JEWELRY: [],
        Subcategory.MeasurementProfile.ACCESSORY_GENERIC: [],
    }

    class Meta:
        model = Product
        fields = [
            # core
            "title",
            "description",
            "price",
            "gender",
            "category",
            "subcategory",
            "brand",
            "brand_other",

            # size / condition / material
            "size",
            "size_alpha",
            "condition",
            "condition_notes",
            "material",

            # images
            "main_image",

            # dimensiuni îmbrăcăminte
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
            "inseam_cm",
            "outseam_cm",

            # dimensiuni shoes
            "shoe_insole_length_cm",
            "shoe_width_cm",
            "shoe_heel_height_cm",
            "shoe_total_height_cm",

            # dimensiuni bags
            "bag_width_cm",
            "bag_height_cm",
            "bag_depth_cm",
            "strap_length_cm",

            # dimensiuni belts
            "belt_length_total_cm",
            "belt_length_usable_cm",
            "belt_width_cm",

            # dimensiuni jewelry
            "jewelry_chain_length_cm",
            "jewelry_drop_length_cm",
            "jewelry_pendant_size_cm",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": "10", "step": "0.01"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "subcategory": forms.Select(attrs={"class": "form-select"}),
            "brand": forms.Select(attrs={"class": "form-select"}),
            "brand_other": forms.TextInput(attrs={"class": "form-control"}),

            "size": forms.Select(attrs={"class": "form-select"}),
            "size_alpha": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: S, M, L, 2XL"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "condition_notes": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: purtat de 2 ori, fără defecte"}),
            "material": forms.Select(attrs={"class": "form-select"}),

            "main_image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.setdefault("min", "0")

        sub_qs = Subcategory.objects.all()
        category_obj = None
        data = self.data if self.is_bound else None

        if data:
            category_key = self.add_prefix("category")
            if category_key in data:
                try:
                    category_id = int(data.get(category_key))
                    category_obj = Category.objects.filter(pk=category_id).first()
                except (TypeError, ValueError):
                    category_obj = None

        if not category_obj:
            category_obj = self.initial.get("category") or getattr(self.instance, "category", None)

        if category_obj and getattr(category_obj, "pk", None):
            sub_qs = sub_qs.filter(category=category_obj)

        current_sub = self.initial.get("subcategory") or getattr(self.instance, "subcategory", None)
        if current_sub and getattr(current_sub, "pk", None):
            sub_qs = (sub_qs | Subcategory.objects.filter(pk=current_sub.pk)).distinct()

        self.fields["subcategory"].queryset = sub_qs.order_by("name")

        if "brand" in self.fields:
            self.fields["brand"].queryset = Brand.objects.all().order_by("name")

        if "material" in self.fields:
            self.fields["material"].queryset = Material.objects.all().order_by("name")

    def clean(self):
        cleaned = super().clean()
        instance = self.instance

        brand_other = (cleaned.get("brand_other") or "").strip()
        size_alpha = (cleaned.get("size_alpha") or "").strip()
        cleaned["brand_other"] = brand_other
        cleaned["size_alpha"] = size_alpha

        category = cleaned.get("category")
        subcategory = cleaned.get("subcategory")
        if subcategory and category and subcategory.category_id != category.id:
            self.add_error("subcategory", "Subcategoria aleasă nu aparține categoriei selectate.")

        brand = cleaned.get("brand")
        if not brand and not brand_other:
            self.add_error("brand", "Alege un brand din listă sau completează câmpul „Alt brand”.")

        # min 4 photos (main + existing extra + new extra)
        main_image = cleaned.get("main_image") or getattr(instance, "main_image", None)
        new_extra_images = _flatten_files(cleaned.get("extra_images"))
        existing_extra_count = instance.images.count() if instance.pk else 0

        total_photos = (1 if main_image else 0) + existing_extra_count + len(new_extra_images)
        if total_photos < 4:
            raise forms.ValidationError(
                "Produsul trebuie să aibă minim 4 poze "
                "(imagine principală + cel puțin 3 imagini suplimentare)."
            )

        mp = getattr(subcategory, "measurement_profile", None) if subcategory is not None else None
        if mp:
            required_fields = self.REQUIRED_BY_PROFILE.get(mp, [])
            missing = []
            for field_name in required_fields:
                val = cleaned.get(field_name)
                if val in (None, ""):
                    self.add_error(field_name, "Acest câmp este obligatoriu pentru tipul de produs selectat.")
                    missing.append(self.fields[field_name].label or field_name)

            if missing:
                raise forms.ValidationError(
                    "Te rugăm să completezi toate dimensiunile obligatorii: %s."
                    % ", ".join(missing)
                )

        if category and hasattr(category, "get_effective_size_group"):
            sg = category.get_effective_size_group()
            if sg == Category.SizeGroup.ACCESSORIES:
                if not cleaned.get("size"):
                    cleaned["size"] = "One Size"
                if not cleaned.get("size_alpha"):
                    cleaned["size_alpha"] = "One Size"

        return cleaned
