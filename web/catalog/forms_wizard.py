# catalog/forms_wizard.py (fragment complet pentru helpers + ProductPhotosForm)
from __future__ import annotations

import unicodedata
from decimal import Decimal
from typing import Any

from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .forms import MultiFileInput, MultiImageField
from .models import Brand, Category, Color, Material, Product, Subcategory, SustainabilityTag


def _flatten_files(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.extend(_flatten_files(v))
        return out
    return [value]


def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip()


def _is_gloves_subcat(subcat: Subcategory | None) -> bool:
    if not subcat:
        return False
    n = _norm(getattr(subcat, "name", ""))
    return "manus" in n


_CLOTHING_NUMERIC_SUBCATS = {_norm(x) for x in ["Blugi", "Pantaloni", "Fuste", "Rochii", "Salopete"]}


def _is_numeric_clothing_subcat(subcat: Subcategory | None) -> bool:
    if not subcat:
        return False
    n = _norm(getattr(subcat, "name", ""))
    return n in _CLOTHING_NUMERIC_SUBCATS


def _default_numeric_system_code(brand_obj: Brand | None, brand_other: str = "") -> str:
    candidates = []
    if brand_obj is not None:
        for attr in ("country_code", "country", "origin_country", "origin"):
            v = getattr(brand_obj, attr, None)
            if v:
                candidates.append(str(v))
        candidates.append(getattr(brand_obj, "slug", "") or "")
        candidates.append(getattr(brand_obj, "name", "") or "")
    candidates.append(brand_other or "")

    blob = _norm(" ".join(candidates))

    if "uk" in blob or "united kingdom" in blob or "great britain" in blob or "gb" in blob:
        return "GB 2–30"
    if "italy" in blob or "italia" in blob or "it" in blob:
        return "IT 32–66"

    return "FR 28–58"


class ProductPhotosForm(forms.Form):
    photos_order = forms.CharField(required=False, widget=forms.HiddenInput())
    main_choice = forms.CharField(required=False, widget=forms.HiddenInput())

    main_image = forms.ImageField(
        label=_("Imagine principală"),
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
    )

    extra_images = MultiImageField(
        required=False,
        label=_("Imagini suplimentare"),
        help_text=_("Poți selecta mai multe imagini. Ideal ai minim 4 în total."),
        widget=MultiFileInput(
            attrs={"class": "form-control", "accept": "image/*", "multiple": True}
        ),
    )

    def __init__(
        self,
        *args,
        require_min_photos: bool = True,
        existing_photos_count: int = 0,
        **kwargs,
    ):
        self.require_min_photos = require_min_photos
        self.existing_photos_count = int(existing_photos_count or 0)
        super().__init__(*args, **kwargs)

    def _files_from_request(self):
        """
        Ia fișierele DIRECT din self.files (getlist), inclusiv cazul în care wizard-ul a salvat chei split:
          photos-extra_images__0, __1...
        """
        main_key = self.add_prefix("main_image")
        extra_key = self.add_prefix("extra_images")

        main_file = None
        extra_files = []

        if hasattr(self, "files") and self.files:
            # main (single)
            main_file = self.files.get(main_key)

            # extras (multiple)
            if hasattr(self.files, "getlist"):
                extra_files = list(self.files.getlist(extra_key) or [])

            # fallback: chei split
            if not extra_files:
                for k in self.files.keys():
                    k = str(k)
                    if k.startswith(extra_key + "__"):
                        f = self.files.get(k)
                        if f:
                            extra_files.append(f)

        # normalizări
        if isinstance(main_file, (list, tuple)):
            main_file = main_file[0] if main_file else None

        extra_files = [x for x in _flatten_files(extra_files) if x]
        return main_file, extra_files

    def clean(self):
        cleaned = super().clean()

        # ✅ IMPORTANT: nu depindem de ce întoarce MultiImageField
        main_file, extra_files = self._files_from_request()

        file_by_key = {}
        keys_in_input_order = []

        if main_file:
            file_by_key["m"] = main_file
            keys_in_input_order.append("m")

        for idx, f in enumerate(extra_files):
            k = f"e{idx}"
            file_by_key[k] = f
            keys_in_input_order.append(k)

        raw_order = (cleaned.get("photos_order") or "").strip()
        order = []
        seen = set()

        if raw_order:
            order = [x.strip() for x in raw_order.split(",") if x.strip()]
            order = [k for k in order if (k in file_by_key and not (k in seen or seen.add(k)))]
            for k in keys_in_input_order:
                if k in file_by_key and k not in seen:
                    order.append(k)
                    seen.add(k)

        if not order:
            order = keys_in_input_order

        main_choice = (cleaned.get("main_choice") or "").strip()
        if main_choice not in file_by_key:
            main_choice = order[0] if order else ""

        if main_choice and main_choice in file_by_key:
            rebuilt_main = file_by_key[main_choice]
            rebuilt_extra = [file_by_key[k] for k in order if k != main_choice]
        else:
            rebuilt_main = file_by_key.get("m")
            rebuilt_extra = [file_by_key[k] for k in order if k != "m"]

        if self.require_min_photos:
            uploaded_total = (1 if rebuilt_main else 0) + len(rebuilt_extra)
            total = self.existing_photos_count + uploaded_total
            if total < 4:
                raise forms.ValidationError(
                    _("Produsul trebuie să aibă minim 4 poze (imagine principală + cel puțin 3 imagini suplimentare).")
                )

        if self.fields["main_image"].required and not rebuilt_main:
            raise forms.ValidationError(_("Te rog să încarci imaginea principală a produsului."))

        cleaned["main_image"] = rebuilt_main
        cleaned["extra_images"] = rebuilt_extra
        return cleaned


class ProductTitleDescriptionForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: Rochie midi satinată verde",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Descrie produsul (material, croi, cum se așază, defecte etc.)",
                }
            ),
        }


class ProductCategoryBrandForm(forms.Form):
    GENDER_CHOICES = [
        ("F", _("Femei")),
        ("M", _("Bărbați")),
    ]

    gender = forms.ChoiceField(label=_("Gen"), choices=GENDER_CHOICES, widget=forms.RadioSelect)

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
        gender_value = None
        category_obj = None

        if data:
            gender_key = self.add_prefix("gender")
            category_key = self.add_prefix("category")

            if gender_key in data:
                gender_value = data.get(gender_key)

            if category_key in data:
                try:
                    category_id = int(data.get(category_key))
                    category_obj = Category.objects.filter(pk=category_id).first()
                    if category_obj:
                        sub_qs = Subcategory.objects.filter(category=category_obj)
                except (TypeError, ValueError):
                    pass

        if not category_obj and self.initial.get("category"):
            category_obj = self.initial["category"]
            sub_qs = Subcategory.objects.filter(category=category_obj)

        if not gender_value:
            gender_value = self.initial.get("gender")

        if gender_value in ("F", "M") and sub_qs.exists():
            sub_qs = sub_qs.filter(
                Q(gender__isnull=True) | Q(gender="") | Q(gender="U") | Q(gender=gender_value)
            )

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
        gender = cleaned.get("gender")

        if brand and brand_other:
            self.add_error("brand_other", _("Alege fie un brand din listă, fie completează „Alt brand”, nu ambele."))

        if not brand and not brand_other:
            self.add_error("brand", _("Alege un brand din listă sau completează câmpul „Alt brand”."))

        if not category:
            self.add_error("category", _("Alege o categorie."))

        if subcategory and category and subcategory.category_id != category.id:
            self.add_error("subcategory", _("Subcategoria aleasă nu aparține categoriei selectate."))

        if subcategory and gender and getattr(subcategory, "gender", None):
            if hasattr(subcategory, "allows_gender") and not subcategory.allows_gender(gender):
                self.add_error("subcategory", _("Subcategoria aleasă nu este disponibilă pentru genul selectat."))

        return cleaned


class ProductSizeDetailsForm(forms.ModelForm):
    """
    Step 4: Mărime + Stare + Material (UN SINGUR) + Culoare (base_color).
    Fără compoziție și fără procente.
    """

    SHOE_SIZE_CHOICES = [("", _("Alege mărimea EU"))] + [
        (str(Decimal(v) / Decimal(10)), f"{Decimal(v) / Decimal(10):g}") for v in range(350, 466, 5)
    ]

    SIZE_FR_CHOICES = [("", "---")] + [(str(i), str(i)) for i in range(28, 59, 2)]
    SIZE_IT_CHOICES = [("", "---")] + [(str(i), str(i)) for i in range(32, 67, 2)]
    SIZE_GB_CHOICES = [("", "---")] + [(str(i), str(i)) for i in range(2, 31, 2)]

    ALPHA_CODES = ["XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL"]

    base_color = forms.ModelChoiceField(
        queryset=Color.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Culoare"),
    )

    shoe_size_eu = forms.TypedChoiceField(
        label=_("Mărime încălțăminte EU (35–46.5)"),
        required=False,
        choices=SHOE_SIZE_CHOICES,
        coerce=Decimal,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    size_fr = forms.TypedChoiceField(
        label=_("Mărime numerică FR (28–58)"),
        required=False,
        choices=SIZE_FR_CHOICES,
        coerce=int,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    size_it = forms.TypedChoiceField(
        label=_("Mărime numerică IT (32–66)"),
        required=False,
        choices=SIZE_IT_CHOICES,
        coerce=int,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    size_gb = forms.TypedChoiceField(
        label=_("Mărime numerică GB (2–30)"),
        required=False,
        choices=SIZE_GB_CHOICES,
        coerce=int,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(
        self,
        *args,
        category_obj=None,
        subcategory_obj=None,
        brand_obj=None,
        brand_other: str = "",
        measurement_profile=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.measurement_profile = measurement_profile
        self.size_group = None
        self.size_variant = "GENERIC"
        self.size_mode_label = ""
        self.show_numeric_block = False

        self.fields["base_color"].queryset = Color.objects.all().order_by("name")

        if category_obj is not None and hasattr(category_obj, "get_effective_size_group"):
            self.size_group = category_obj.get_effective_size_group()

        if self.size_group == Category.SizeGroup.SHOES:
            self.size_variant = "SHOES_EU"
            self.size_mode_label = "Încălțăminte — EU 35–46.5"
        elif self.size_group == Category.SizeGroup.ACCESSORIES:
            if _is_gloves_subcat(subcategory_obj):
                self.size_variant = "ACCESSORY_GLOVES_ALPHA"
                self.size_mode_label = "Accesorii — Mănuși (Alpha XXS–3XL)"
            else:
                self.size_variant = "ACCESSORY_ONE"
                self.size_mode_label = "Accesorii — One Size"
        elif self.size_group == Category.SizeGroup.CLOTHING:
            if _is_numeric_clothing_subcat(subcategory_obj):
                self.size_variant = "CLOTHING_NUMERIC"
                self.size_mode_label = "Îmbrăcăminte — Numeric (FR/GB/IT)"
            else:
                self.size_variant = "CLOTHING_ALPHA"
                self.size_mode_label = "Îmbrăcăminte — Alpha (XXS–3XL)"
        else:
            self.size_variant = "GENERIC"
            self.size_mode_label = "Generic"

        size_choices_all = [(code, label) for code, label in Product.SIZE_CHOICES if code != "OTHER"]

        def _set_hidden(field_name: str):
            if field_name in self.fields:
                self.fields[field_name].widget = forms.HiddenInput()
                self.fields[field_name].required = False

        def _show(field_name: str):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.setdefault("class", "form-select")

        if "size_alpha" in self.fields:
            _set_hidden("size_alpha")

        if self.size_variant == "SHOES_EU":
            if "size" in self.fields:
                self.fields["size"].required = False
                self.fields["size"].initial = "EU 35–46.5"
                self.fields["size"].widget = forms.HiddenInput()

            _show("shoe_size_eu")
            _set_hidden("size_fr")
            _set_hidden("size_it")
            _set_hidden("size_gb")
            self.show_numeric_block = True

        elif self.size_variant == "ACCESSORY_ONE":
            if "size" in self.fields:
                self.fields["size"].required = False
                self.fields["size"].initial = "One Size"
                self.fields["size"].widget = forms.HiddenInput()

            _set_hidden("shoe_size_eu")
            _set_hidden("size_fr")
            _set_hidden("size_it")
            _set_hidden("size_gb")
            self.show_numeric_block = False

        elif self.size_variant in {"CLOTHING_ALPHA", "ACCESSORY_GLOVES_ALPHA"}:
            allowed = set(self.ALPHA_CODES)

            current_value = None
            if self.is_bound:
                current_value = (self.data.get(self.add_prefix("size")) or "").strip() or None
            if not current_value:
                current_value = self.initial.get("size") or getattr(getattr(self, "instance", None), "size", None)

            if current_value and current_value not in allowed:
                allowed.add(current_value)

            self.fields["size"].choices = [(c, l) for c, l in size_choices_all if c in allowed]
            self.fields["size"].widget.attrs.setdefault("class", "form-select")

            _set_hidden("shoe_size_eu")
            _set_hidden("size_fr")
            _set_hidden("size_it")
            _set_hidden("size_gb")
            self.show_numeric_block = False

        elif self.size_variant == "CLOTHING_NUMERIC":
            allowed = {"FR 28–58", "GB 2–30", "IT 32–66"}
            default_size_code = _default_numeric_system_code(brand_obj, brand_other)

            if "size" in self.fields:
                self.fields["size"].choices = [(c, l) for c, l in size_choices_all if c in allowed]
                self.fields["size"].widget.attrs.setdefault("class", "form-select")
                self.fields["size"].required = True

            if self.is_bound:
                selected = (self.data.get(self.add_prefix("size")) or "").strip() or default_size_code
            else:
                selected = (self.initial.get("size") or "").strip() or default_size_code

            if selected not in allowed:
                selected = default_size_code

            if not self.is_bound:
                self.initial["size"] = selected

            if selected == "FR 28–58":
                _show("size_fr")
                _set_hidden("size_it")
                _set_hidden("size_gb")
            elif selected == "IT 32–66":
                _show("size_it")
                _set_hidden("size_fr")
                _set_hidden("size_gb")
            elif selected == "GB 2–30":
                _show("size_gb")
                _set_hidden("size_fr")
                _set_hidden("size_it")

            _set_hidden("shoe_size_eu")
            self.show_numeric_block = True

        material_field = self.fields.get("material")
        if material_field:
            material_qs = Material.objects.all().order_by("name")

            if self.size_group == Category.SizeGroup.CLOTHING:
                material_qs = material_qs.filter(
                    category_type__in=[Material.CategoryType.CLOTHING, Material.CategoryType.GENERIC]
                )
            elif self.size_group == Category.SizeGroup.SHOES:
                material_qs = material_qs.filter(
                    category_type__in=[Material.CategoryType.SHOES, Material.CategoryType.GENERIC]
                )
            elif self.size_group == Category.SizeGroup.ACCESSORIES:
                material_qs = material_qs.filter(
                    category_type__in=[Material.CategoryType.ACCESSORIES, Material.CategoryType.GENERIC]
                )

            current_material = self.initial.get("material") or getattr(getattr(self, "instance", None), "material", None)
            if current_material and getattr(current_material, "pk", None):
                material_qs = (material_qs | Material.objects.filter(pk=current_material.pk)).distinct()

            material_field.queryset = material_qs
            material_field.widget.attrs.setdefault("class", "form-select")

    class Meta:
        model = Product
        fields = [
            "size",
            "size_alpha",
            "condition",
            "condition_notes",
            "material",
            "shoe_size_eu",
            "size_fr",
            "size_it",
            "size_gb",
            "base_color",
        ]
        labels = {
            "size": _("Mărime"),
            "size_alpha": _("Mărime literă (XXS–3XL / One Size)"),
            "condition": _("Stare"),
            "condition_notes": _("Detalii despre stare"),
            "material": _("Material"),
            "base_color": _("Culoare"),
        }
        widgets = {
            "size": forms.Select(attrs={"class": "form-select"}),
            "size_alpha": forms.TextInput(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "condition_notes": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex: purtat de 2 ori, fără defecte vizibile"}
            ),
            "material": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned = super().clean()

        size_selected = (cleaned.get("size") or "").strip() if cleaned.get("size") else None
        shoe_size_eu = cleaned.get("shoe_size_eu")
        size_fr = cleaned.get("size_fr")
        size_it = cleaned.get("size_it")
        size_gb = cleaned.get("size_gb")

        cleaned["size_alpha"] = (cleaned.get("size_alpha") or "").strip()

        if self.size_variant == "SHOES_EU":
            cleaned["size"] = "EU 35–46.5"
            cleaned["size_alpha"] = ""
            if shoe_size_eu is None:
                self.add_error("shoe_size_eu", _("Te rog să alegi mărimea încălțămintei EU (35–46.5)."))
            cleaned["size_fr"] = None
            cleaned["size_it"] = None
            cleaned["size_gb"] = None

        elif self.size_variant == "ACCESSORY_ONE":
            cleaned["size"] = "One Size"
            cleaned["size_alpha"] = "One Size"
            cleaned["shoe_size_eu"] = None
            cleaned["size_fr"] = None
            cleaned["size_it"] = None
            cleaned["size_gb"] = None

        elif self.size_variant in {"CLOTHING_ALPHA", "ACCESSORY_GLOVES_ALPHA"}:
            if size_selected not in set(self.ALPHA_CODES):
                self.add_error("size", _("Alege o mărime Alpha (XXS–3XL)."))
            cleaned["size_alpha"] = size_selected or ""
            cleaned["shoe_size_eu"] = None
            cleaned["size_fr"] = None
            cleaned["size_it"] = None
            cleaned["size_gb"] = None

        elif self.size_variant == "CLOTHING_NUMERIC":
            if size_selected not in {"FR 28–58", "GB 2–30", "IT 32–66"}:
                self.add_error("size", _("Alege sistemul numeric: FR / GB / IT."))

            cleaned["size_alpha"] = ""
            cleaned["shoe_size_eu"] = None

            if size_selected == "FR 28–58":
                if size_fr in (None, ""):
                    self.add_error("size_fr", _("Te rog să alegi mărimea numerică FR."))
                cleaned["size_it"] = None
                cleaned["size_gb"] = None
            elif size_selected == "IT 32–66":
                if size_it in (None, ""):
                    self.add_error("size_it", _("Te rog să alegi mărimea numerică IT."))
                cleaned["size_fr"] = None
                cleaned["size_gb"] = None
            elif size_selected == "GB 2–30":
                if size_gb in (None, ""):
                    self.add_error("size_gb", _("Te rog să alegi mărimea numerică GB."))
                cleaned["size_fr"] = None
                cleaned["size_it"] = None

        else:
            if size_selected in set(self.ALPHA_CODES):
                cleaned["size_alpha"] = size_selected
            cleaned["shoe_size_eu"] = None
            cleaned["size_fr"] = None
            cleaned["size_it"] = None
            cleaned["size_gb"] = None

        return cleaned


class ProductDimensionsForm(forms.ModelForm):
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

    VISIBLE_BY_PROFILE = {
        Subcategory.MeasurementProfile.TOP: ["shoulders_cm", "bust_cm", "waist_cm", "hips_cm", "length_cm", "sleeve_cm"],
        Subcategory.MeasurementProfile.DRESS: ["shoulders_cm", "bust_cm", "waist_cm", "hips_cm", "length_cm", "sleeve_cm"],
        Subcategory.MeasurementProfile.JUMPSUIT: [
            "shoulders_cm", "bust_cm", "waist_cm", "hips_cm", "length_cm", "sleeve_cm", "inseam_cm", "outseam_cm"
        ],
        Subcategory.MeasurementProfile.PANTS: ["waist_cm", "hips_cm", "inseam_cm", "outseam_cm", "length_cm"],
        Subcategory.MeasurementProfile.SKIRT: ["waist_cm", "hips_cm", "length_cm"],
        Subcategory.MeasurementProfile.SHOES: ["shoe_insole_length_cm", "shoe_width_cm", "shoe_heel_height_cm", "shoe_total_height_cm"],
        Subcategory.MeasurementProfile.BAGS: ["bag_width_cm", "bag_height_cm", "bag_depth_cm", "strap_length_cm"],
        Subcategory.MeasurementProfile.BELTS: ["belt_length_total_cm", "belt_length_usable_cm", "belt_width_cm"],
        Subcategory.MeasurementProfile.JEWELRY: ["jewelry_chain_length_cm", "jewelry_drop_length_cm", "jewelry_pendant_size_cm"],
        Subcategory.MeasurementProfile.ACCESSORY_GENERIC: [
            "bag_width_cm", "bag_height_cm", "bag_depth_cm", "strap_length_cm",
            "jewelry_chain_length_cm", "jewelry_drop_length_cm", "jewelry_pendant_size_cm",
        ],
    }

    def __init__(self, *args, measurement_profile=None, **kwargs):
        self.measurement_profile = measurement_profile
        super().__init__(*args, **kwargs)

        mp = self.measurement_profile
        visible = self.VISIBLE_BY_PROFILE.get(mp, list(self.fields.keys())) if mp else list(self.fields.keys())
        self.visible_field_names = set(visible)

        for name, field in self.fields.items():
            if name not in self.visible_field_names:
                field.widget = forms.HiddenInput()
                continue

            field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.setdefault("min", "0")

    class Meta:
        model = Product
        fields = [
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
            "inseam_cm",
            "outseam_cm",
            "shoe_insole_length_cm",
            "shoe_width_cm",
            "shoe_heel_height_cm",
            "shoe_total_height_cm",
            "bag_width_cm",
            "bag_height_cm",
            "bag_depth_cm",
            "strap_length_cm",
            "belt_length_total_cm",
            "belt_length_usable_cm",
            "belt_width_cm",
            "jewelry_chain_length_cm",
            "jewelry_drop_length_cm",
            "jewelry_pendant_size_cm",
        ]
        labels = {
            "shoulders_cm": _("Umeri (cm)"),
            "bust_cm": _("Bust (cm)"),
            "waist_cm": _("Talie (cm)"),
            "hips_cm": _("Șold (cm)"),
            "length_cm": _("Lungime totală (cm)"),
            "sleeve_cm": _("Lungime mânecă (cm)"),
            "inseam_cm": _("Crac interior (cm)"),
            "outseam_cm": _("Lungime totală din talie până jos (cm)"),
            "shoe_insole_length_cm": _("Lungime branț / interior (cm)"),
            "shoe_width_cm": _("Lățime talpă (cm)"),
            "shoe_heel_height_cm": _("Înălțime toc (cm)"),
            "shoe_total_height_cm": _("Înălțime totală (cm)"),
            "bag_width_cm": _("Lățime geantă (cm)"),
            "bag_height_cm": _("Înălțime geantă (cm)"),
            "bag_depth_cm": _("Adâncime geantă (cm)"),
            "strap_length_cm": _("Lungime barete / lanț (cm)"),
            "belt_length_total_cm": _("Lungime totală curea (cm)"),
            "belt_length_usable_cm": _("Lungime utilă (cm)"),
            "belt_width_cm": _("Lățime curea (cm)"),
            "jewelry_chain_length_cm": _("Lungime lanț / lănțișor (cm)"),
            "jewelry_drop_length_cm": _("Lungime cercei / drop (cm)"),
            "jewelry_pendant_size_cm": _("Dimensiune pandantiv (cm)"),
        }

    def clean(self):
        cleaned = super().clean()
        mp = self.measurement_profile
        if not mp:
            return cleaned

        required_fields = self.REQUIRED_BY_PROFILE.get(mp, [])
        missing_labels = []

        for field_name in required_fields:
            val = cleaned.get(field_name)
            if val in (None, ""):
                self.add_error(field_name, _("Acest câmp este obligatoriu pentru tipul de produs selectat."))
                missing_labels.append(str(self.fields[field_name].label or field_name))

        if missing_labels:
            raise forms.ValidationError(
                _("Te rugăm să completezi toate dimensiunile obligatorii: %(fields)s.")
                % {"fields": ", ".join(missing_labels)}
            )

        return cleaned


class ProductPricePackageForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["price", "package_size"]
        labels = {
            "price": _("Preț de vânzare (RON)"),
            "package_size": _("Mărime colet"),
        }
        widgets = {
            "price": forms.NumberInput(attrs={"class": "form-control", "min": "10", "step": "0.01"}),
            "package_size": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None:
            raise forms.ValidationError(_("Te rog să introduci un preț."))
        if price < Decimal("10.00"):
            raise forms.ValidationError(_("Prețul minim este 10 RON."))
        return price


class ProductSustainabilityForm(forms.Form):
    sustainability_tags = forms.ModelMultipleChoiceField(
        queryset=SustainabilityTag.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Elemente de sustenabilitate"),
    )

    sustainability_none = forms.BooleanField(
        required=False,
        label=_("Produsul nu are niciun element de sustenabilitate"),
    )

    def __init__(self, *args, base_material=None, **kwargs):
        self.base_material = base_material
        super().__init__(*args, **kwargs)
        self.fields["sustainability_tags"].queryset = SustainabilityTag.objects.all().order_by("name")

    def clean(self):
        cleaned = super().clean()

        tags_qs = cleaned.get("sustainability_tags")
        none_flag = cleaned.get("sustainability_none")

        if none_flag and tags_qs:
            self.add_error(
                "sustainability_none",
                _("Nu poți bifa „Nici una” și în același timp alte opțiuni de sustenabilitate."),
            )

        if tags_qs:
            keys = {getattr(t, "key", None) for t in tags_qs}

            sustainable_key = None
            if hasattr(SustainabilityTag, "Key") and hasattr(SustainabilityTag.Key, "SUSTAINABLE_MATERIALS"):
                sustainable_key = SustainabilityTag.Key.SUSTAINABLE_MATERIALS

            if sustainable_key and sustainable_key in keys:
                has_sustainable = bool(self.base_material and getattr(self.base_material, "is_sustainable", False))
                if not has_sustainable:
                    self.add_error(
                        "sustainability_tags",
                        _("Produsul nu are material principal sustenabil, deci nu poți bifa „Materiale sustenabile”."),
                    )

        return cleaned


class ProductReviewForm(forms.Form):
    pass
