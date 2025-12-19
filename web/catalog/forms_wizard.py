# catalog/forms_wizard.py
from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import (
    Product,
    Color,
    Category,
    Subcategory,
    Brand,
    SustainabilityTag,
    Material,
)
from .forms import MultiFileInput, MultiImageField


# PAS 1 – IMAGINI
class ProductPhotosForm(forms.Form):
    def __init__(self, *args, require_min_photos=True, **kwargs):
        self.require_min_photos = require_min_photos
        super().__init__(*args, **kwargs)

    main_image = forms.ImageField(
        label=_("Imagine principală"),
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": "image/*"}
        ),
    )

    extra_images = MultiImageField(
        required=False,
        label=_("Imagini suplimentare"),
        help_text=_("Poți selecta mai multe imagini. Ideal ai minim 4 în total."),
        widget=MultiFileInput(
            attrs={
                "class": "form-control",
                "accept": "image/*",
                "multiple": True,
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        main_image = cleaned.get("main_image")
        extra = cleaned.get("extra_images") or []

        if not main_image:
            raise forms.ValidationError(
                _("Te rog să încarci imaginea principală a produsului.")
            )

        # conform planului: minim 4 imagini (1 principală + 3 detalii)
        if self.require_min_photos:
            total = (1 if main_image else 0) + len(extra)
            if total < 4:
                raise forms.ValidationError(
                    _(
                        "Produsul trebuie să aibă minim 4 poze "
                        "(imagine principală + cel puțin 3 imagini suplimentare)."
                    )
                )

        return cleaned


# PAS 2 – TITLU & DESCRIERE
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


# PAS 3 – GEN, CATEGORIE, SUBCATEGORIE, BRAND
class ProductCategoryBrandForm(forms.Form):
    GENDER_CHOICES = [
        ("F", _("Femei")),
        ("M", _("Bărbați")),
    ]

    gender = forms.ChoiceField(
        label=_("Gen"),
        choices=GENDER_CHOICES,
        widget=forms.RadioSelect,
    )

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

        # populăm mereu listele de bază
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

        # filtrăm subcategoriile după gen, dacă e cazul
        if gender_value in ("F", "M") and sub_qs.exists():
            sub_qs = sub_qs.filter(
                Q(gender__isnull=True)
                | Q(gender="")
                | Q(gender="U")
                | Q(gender=gender_value)
            )

        # dacă avem deja o subcategorie inițială (la edit), o includem în queryset
        initial_sub = self.initial.get("subcategory")
        if initial_sub:
            sub_qs = (
                sub_qs
                | Subcategory.objects.filter(
                    pk=getattr(initial_sub, "pk", initial_sub)
                )
            ).distinct()

        self.fields["subcategory"].queryset = sub_qs.order_by("name")

    def clean(self):
        cleaned = super().clean()

        brand = cleaned.get("brand")
        brand_other = (cleaned.get("brand_other") or "").strip()
        cleaned["brand_other"] = brand_other

        category = cleaned.get("category")
        subcategory = cleaned.get("subcategory")
        gender = cleaned.get("gender")

        if not brand and not brand_other:
            self.add_error(
                "brand",
                _("Alege un brand din listă sau completează câmpul „Alt brand”."),
            )

        if not category:
            self.add_error(
                "category",
                _("Alege o categorie."),
            )

        if subcategory and category and subcategory.category_id != category.id:
            self.add_error(
                "subcategory",
                _("Subcategoria aleasă nu aparține categoriei selectate."),
            )

        if subcategory and gender and getattr(subcategory, "gender", None):
            if not subcategory.allows_gender(gender):
                self.add_error(
                    "subcategory",
                    _(
                        "Subcategoria aleasă nu este disponibilă pentru genul selectat."
                    ),
                )

        return cleaned


# PAS 7 – SUSTENABILITATE (logică + validare)
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

    def __init__(self, *args, base_material=None, compositions=None, **kwargs):
        """
        base_material – Material principal (din pasul de mărimi & detalii)
        compositions – listă de tuple (Material, procent) din _compositions
        """
        self.base_material = base_material
        self.compositions = compositions or []
        super().__init__(*args, **kwargs)

        self.fields["sustainability_tags"].queryset = (
            SustainabilityTag.objects.all().order_by("name")
        )

    def clean(self):
        cleaned = super().clean()

        tags_qs = cleaned.get("sustainability_tags")
        none_flag = cleaned.get("sustainability_none")

        # „Nici una” exclusivă
        if none_flag and tags_qs:
            self.add_error(
                "sustainability_none",
                _(
                    "Nu poți bifa „Nici una” și în același timp alte opțiuni de sustenabilitate."
                ),
            )

        if tags_qs:
            keys = {t.key for t in tags_qs}
            if SustainabilityTag.Key.SUSTAINABLE_MATERIALS in keys:
                has_sustainable = False

                # material principal
                main_material = self.base_material
                if main_material and getattr(main_material, "is_sustainable", False):
                    has_sustainable = True

                # materiale din compoziție
                if not has_sustainable:
                    for mat, _pct in self.compositions or []:
                        if getattr(mat, "is_sustainable", False):
                            has_sustainable = True
                            break

                if not has_sustainable:
                    self.add_error(
                        "sustainability_tags",
                        _(
                            "Produsul nu conține materiale sustenabile conform listei "
                            "Snobistic, deci nu poți bifa „Materiale sustenabile”."
                        ),
                    )

        return cleaned


# PAS 4 – MĂRIME, STARE, MATERIAL, CULORI (+ compoziție)
class ProductSizeDetailsForm(forms.ModelForm):
    # --- dropdown pantofi EU 35.0–46.5 din 0.5 în 0.5 ---
    SHOE_SIZE_CHOICES = [
        ("", _("Alege mărimea EU")),
    ] + [
        (str(v / 10), f"{v / 10:g}")  # 35, 35.5, 36 ... 46.5
        for v in range(350, 466, 5)
    ]

    # --- dropdown FR/IT/GB din 2 în 2 ---
    SIZE_FR_CHOICES = [("", "---")] + [
        (str(i), str(i)) for i in range(28, 59, 2)  # 28–58
    ]
    SIZE_IT_CHOICES = [("", "---")] + [
        (str(i), str(i)) for i in range(32, 67, 2)  # 32–66
    ]
    SIZE_GB_CHOICES = [("", "---")] + [
        (str(i), str(i)) for i in range(2, 31, 2)   # 2–30
    ]

    # culoare principală
    colors = forms.ModelChoiceField(
        queryset=Color.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Culoare"),
    )

    # mărime pantofi ca dropdown
    shoe_size_eu = forms.TypedChoiceField(
        label=_("Mărime încălțăminte EU (35–46.5)"),
        required=False,
        choices=SHOE_SIZE_CHOICES,
        coerce=Decimal,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # mărimi numerice FR / IT / GB
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

    # compoziție detaliată – până la 3 materiale
    comp1_material = forms.ModelChoiceField(
        queryset=Material.objects.none(),
        required=False,
        label=_("Material 1"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comp1_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        label=_("Procent material 1 (%)"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0", "max": "100", "step": "0.1"}
        ),
    )

    comp2_material = forms.ModelChoiceField(
        queryset=Material.objects.none(),
        required=False,
        label=_("Material 2"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comp2_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        label=_("Procent material 2 (%)"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0", "max": "100", "step": "0.1"}
        ),
    )

    comp3_material = forms.ModelChoiceField(
        queryset=Material.objects.none(),
        required=False,
        label=_("Material 3"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comp3_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        label=_("Procent material 3 (%)"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0", "max": "100", "step": "0.1"}
        ),
    )

    def __init__(
        self,
        *args,
        category_obj=None,
        measurement_profile=None,  # nu îl folosim direct aici, dar îl păstrăm pentru viitor
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # flag pentru mesaj în template: dacă user-ul a completat FR/IT/GB,
        # dar a uitat mărimea literă, NU blocăm formularul, doar afișăm un hint.
        self.show_size_alpha_hint = False

        self.measurement_profile = measurement_profile
        self.size_group = None

        # culoare – queryset ordonat
        self.fields["colors"].queryset = Color.objects.all().order_by("name")

        # --- size_group din categorie pentru logica de mărimi ---
        if category_obj is not None and hasattr(
            category_obj, "get_effective_size_group"
        ):
            self.size_group = category_obj.get_effective_size_group()

        # --- mărime "tip selector" (Product.SIZE_CHOICES) fără OTHER ---
        size_choices_all = [
            (code, label)
            for code, label in Product.SIZE_CHOICES
            if code != "OTHER"  # scoatem „Altă mărime” din wizard
        ]

        allowed_codes = {code for code, _ in size_choices_all}

        if self.size_group == Category.SizeGroup.SHOES:
            # doar EU 35–46.5 pentru pantofi
            allowed_codes = {"EU 35–46.5"}
        elif self.size_group == Category.SizeGroup.ACCESSORIES:
            # accesorii: One Size
            allowed_codes = {"One Size"}
        elif self.size_group == Category.SizeGroup.CLOTHING:
            # îmbrăcăminte: litere + One Size + grupurile FR/GB/IT
            allowed_codes = {
                "XXS",
                "XS",
                "S",
                "M",
                "L",
                "XL",
                "2XL",
                "3XL",
                "One Size",
                "FR 28–58",
                "GB 2–30",
                "IT 32–66",
            }

        current_value = (
            self.initial.get("size")
            or getattr(getattr(self, "instance", None), "size", None)
        )
        if current_value and current_value not in allowed_codes:
            allowed_codes.add(current_value)

        self.fields["size"].choices = [
            (code, label)
            for code, label in size_choices_all
            if code in allowed_codes
        ]

        # --- materiale filtrate după tip & propagate în compoziții ---
        material_field = self.fields.get("material")
        if material_field:
            material_qs = Material.objects.all().order_by("name")

            if self.size_group == Category.SizeGroup.CLOTHING:
                material_qs = material_qs.filter(
                    category_type__in=[
                        Material.CategoryType.CLOTHING,
                        Material.CategoryType.GENERIC,
                    ]
                )
            elif self.size_group == Category.SizeGroup.SHOES:
                material_qs = material_qs.filter(
                    category_type__in=[
                        Material.CategoryType.SHOES,
                        Material.CategoryType.GENERIC,
                    ]
                )
            elif self.size_group == Category.SizeGroup.ACCESSORIES:
                material_qs = material_qs.filter(
                    category_type__in=[
                        Material.CategoryType.ACCESSORIES,
                        Material.CategoryType.GENERIC,
                    ]
                )

            current_material = (
                self.initial.get("material")
                or getattr(getattr(self, "instance", None), "material", None)
            )
            if current_material and getattr(current_material, "pk", None):
                material_qs = (
                    material_qs
                    | Material.objects.filter(pk=current_material.pk)
                ).distinct()

            material_field.queryset = material_qs
            material_field.widget.attrs.setdefault("class", "form-select")

            for key in ("comp1_material", "comp2_material", "comp3_material"):
                if key in self.fields:
                    self.fields[key].queryset = material_qs

    class Meta:
        model = Product
        fields = [
            "size",
            "size_alpha",
            # "size_other_label"  # rămâne scos din wizard
            "condition",
            "condition_notes",
            "material",
            # mărimi numerice
            "shoe_size_eu",
            "size_fr",
            "size_it",
            "size_gb",
            # culoare + compoziție
            "colors",
        ]
        labels = {
            "size": _("Mărime (tip selector)"),
            "size_alpha": _("Mărime literă (XXS–3XL / One Size)"),
            "condition": _("Stare"),
            "condition_notes": _("Detalii despre stare"),
            "material": _("Material principal"),
            "colors": _("Culoare"),
        }
        widgets = {
            "size": forms.Select(attrs={"class": "form-select"}),
            "size_alpha": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: S, M, L, 2XL sau One Size",
                }
            ),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "condition_notes": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: purtat de 2 ori, fără defecte vizibile",
                }
            ),
            "material": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned = super().clean()

        # curățăm size_alpha (fără spații)
        size_alpha = (cleaned.get("size_alpha") or "").strip()
        cleaned["size_alpha"] = size_alpha

        # === Compoziție materiale – până la 3 rânduri, în _compositions ===
        from decimal import Decimal as D

        compositions = []
        total_percent = D("0")
        comp_errors = False

        for idx in (1, 2, 3):
            mat = cleaned.get(f"comp{idx}_material")
            pct = cleaned.get(f"comp{idx}_percent")

            if mat is None and pct in (None, ""):
                continue

            if mat is None or pct in (None, ""):
                if mat is None:
                    self.add_error(
                        f"comp{idx}_material",
                        _(
                            "Completează și materialul și procentul sau lasă "
                            "ambele câmpuri goale."
                        ),
                    )
                else:
                    self.add_error(
                        f"comp{idx}_percent",
                        _(
                            "Completează și materialul și procentul sau lasă "
                            "ambele câmpuri goale."
                        ),
                    )
                comp_errors = True
                continue

            try:
                pct_dec = D(pct)
            except Exception:
                self.add_error(
                    f"comp{idx}_percent",
                    _("Procentul trebuie să fie un număr."),
                )
                comp_errors = True
                continue

            if pct_dec < 0 or pct_dec > 100:
                self.add_error(
                    f"comp{idx}_percent",
                    _("Procentul trebuie să fie între 0 și 100."),
                )
                comp_errors = True
                continue

            compositions.append((mat, pct_dec))
            total_percent += pct_dec

        if compositions and not comp_errors:
            if total_percent <= 0 or total_percent > 100:
                self.add_error(
                    "comp1_percent",
                    _(
                        "Suma procentelor de material trebuie să fie între 1 și 100 "
                        "(ideal 100%)."
                    ),
                )
                comp_errors = True

        cleaned["_compositions"] = compositions if not comp_errors else []

        # === Reguli de mărime în funcție de size_group ===
        size_group = self.size_group
        shoe_size_eu = cleaned.get("shoe_size_eu")
        size_fr = cleaned.get("size_fr")
        size_it = cleaned.get("size_it")
        size_gb = cleaned.get("size_gb")

        # FR/IT/GB completate?
        numeric_filled = any(v not in (None, "") for v in (size_fr, size_it, size_gb))

        # resetăm hint-ul la fiecare clean
        self.show_size_alpha_hint = False

        if size_group == Category.SizeGroup.CLOTHING:
            # CLOTHING:
            # - ideal: size_alpha obligatoriu
            # - dacă user-ul completează FR/IT/GB dar uită litera: NU blocăm,
            #   doar setăm un hint pentru template.
            if not size_alpha:
                if numeric_filled:
                    # nu ridicăm eroare, doar informăm template-ul
                    self.show_size_alpha_hint = True
                else:
                    self.add_error(
                        "size_alpha",
                        _(
                            "Pentru articolele de îmbrăcăminte te rugăm să estimezi "
                            "o mărime literă (XXS–3XL / One Size)."
                        ),
                    )

        elif size_group == Category.SizeGroup.SHOES:
            # încălțăminte – mărime numerică EU obligatorie
            if shoe_size_eu is None:
                self.add_error(
                    "shoe_size_eu",
                    _("Te rog să alegi mărimea încălțămintei EU (35–46.5)."),
                )

        elif size_group == Category.SizeGroup.ACCESSORIES:
            # accesorii – One Size implicit
            if not cleaned.get("size"):
                cleaned["size"] = "One Size"
            if not size_alpha:
                cleaned["size_alpha"] = "One Size"

        return cleaned


# PAS 5 – DIMENSIUNI (separat, cu logică pe measurement_profile)
# catalog/forms_wizard.py

class ProductDimensionsForm(forms.ModelForm):
    """
    Dimensiuni în cm, cu câmpuri obligatorii în funcție de measurement_profile
    (TOP / DRESS / JUMPSUIT / PANTS / SKIRT / SHOES / BAGS / BELTS / JEWELRY etc.).
    """

    # câmpuri obligatorii pe profil (deja le aveai corect)
    REQUIRED_BY_PROFILE = {
        Subcategory.MeasurementProfile.TOP: [
            "bust_cm",
            "waist_cm",
            "length_cm",
        ],
        Subcategory.MeasurementProfile.DRESS: [
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
        ],
        Subcategory.MeasurementProfile.JUMPSUIT: [
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "inseam_cm",
        ],
        Subcategory.MeasurementProfile.PANTS: [
            "waist_cm",
            "hips_cm",
            "inseam_cm",
            "length_cm",
        ],
        Subcategory.MeasurementProfile.SKIRT: [
            "waist_cm",
            "hips_cm",
            "length_cm",
        ],
        Subcategory.MeasurementProfile.SHOES: [
            "shoe_insole_length_cm",
        ],
        Subcategory.MeasurementProfile.BAGS: [
            "bag_width_cm",
            "bag_height_cm",
        ],
        Subcategory.MeasurementProfile.BELTS: [
            "belt_length_total_cm",
            "belt_length_usable_cm",
            "belt_width_cm",
        ],
        Subcategory.MeasurementProfile.JEWELRY: [],
        Subcategory.MeasurementProfile.ACCESSORY_GENERIC: [],
    }

    # câmpuri *vizibile* pentru fiecare profil (restul devin hidden)
    VISIBLE_BY_PROFILE = {
        # 3.1. Topuri / bluze / tricouri / cămăși / pulovere / sacouri
        Subcategory.MeasurementProfile.TOP: [
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
        ],
        # 3.2. Rochii
        Subcategory.MeasurementProfile.DRESS: [
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
        ],
        # 3.3. Salopete
        Subcategory.MeasurementProfile.JUMPSUIT: [
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
            "inseam_cm",
            "outseam_cm",
        ],
        # 3.4. Pantaloni / blugi / leggings
        Subcategory.MeasurementProfile.PANTS: [
            "waist_cm",
            "hips_cm",
            "inseam_cm",
            "outseam_cm",
            "length_cm",
        ],
        # 3.5. Fuste
        Subcategory.MeasurementProfile.SKIRT: [
            "waist_cm",
            "hips_cm",
            "length_cm",
        ],
        # 3.6. Încălțăminte
        Subcategory.MeasurementProfile.SHOES: [
            "shoe_insole_length_cm",
            "shoe_width_cm",
            "shoe_heel_height_cm",
            "shoe_total_height_cm",
        ],
        # 3.7. Genți
        Subcategory.MeasurementProfile.BAGS: [
            "bag_width_cm",
            "bag_height_cm",
            "bag_depth_cm",
            "strap_length_cm",
        ],
        # 3.8. Curele
        Subcategory.MeasurementProfile.BELTS: [
            "belt_length_total_cm",
            "belt_length_usable_cm",
            "belt_width_cm",
        ],
        # 3.9. Bijuterii / accesorii mici
        Subcategory.MeasurementProfile.JEWELRY: [
            "jewelry_chain_length_cm",
            "jewelry_drop_length_cm",
            "jewelry_pendant_size_cm",
        ],
        # accesorii generice – putem combina logică de genți + bijuterii
        Subcategory.MeasurementProfile.ACCESSORY_GENERIC: [
            "bag_width_cm",
            "bag_height_cm",
            "bag_depth_cm",
            "strap_length_cm",
            "jewelry_chain_length_cm",
            "jewelry_drop_length_cm",
            "jewelry_pendant_size_cm",
        ],
    }

    def __init__(self, *args, measurement_profile=None, **kwargs):
        self.measurement_profile = measurement_profile
        super().__init__(*args, **kwargs)

        # min="0" pe toate number input-urile
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.setdefault("min", "0")

        # determinăm câmpurile vizibile pentru profilul curent
        mp = self.measurement_profile
        if mp:
            visible = self.VISIBLE_BY_PROFILE.get(mp, list(self.fields.keys()))
        else:
            # dacă nu avem measurement_profile (fallback) – afișăm tot
            visible = list(self.fields.keys())

        self.visible_field_names = set(visible)

        # restul câmpurilor devin hidden (rămân în POST, dar nu se văd în UI)
        for name, field in self.fields.items():
            if name not in self.visible_field_names:
                field.widget = forms.HiddenInput()

    class Meta:
        model = Product
        fields = [
            # dimensiuni îmbrăcăminte
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
            "inseam_cm",
            "outseam_cm",
            # încălțăminte
            "shoe_insole_length_cm",
            "shoe_width_cm",
            "shoe_heel_height_cm",
            "shoe_total_height_cm",
            # genți
            "bag_width_cm",
            "bag_height_cm",
            "bag_depth_cm",
            "strap_length_cm",
            # curele
            "belt_length_total_cm",
            "belt_length_usable_cm",
            "belt_width_cm",
            # bijuterii / accesorii mici
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
        widgets = {
            name: forms.NumberInput(attrs={"class": "form-control"})
            for name in fields
        }

    def clean(self):
        cleaned = super().clean()

        mp = self.measurement_profile
        if not mp:
            # dacă nu știm profilul, nu impunem reguli extra
            return cleaned

        required_fields = self.REQUIRED_BY_PROFILE.get(mp, [])
        missing_labels = []

        for field_name in required_fields:
            val = cleaned.get(field_name)
            if val in (None, ""):
                self.add_error(
                    field_name,
                    _("Acest câmp este obligatoriu pentru tipul de produs selectat."),
                )
                missing_labels.append(self.fields[field_name].label or field_name)

        if missing_labels:
            raise forms.ValidationError(
                _(
                    "Te rugăm să completezi toate dimensiunile obligatorii: %(fields)s."
                )
                % {"fields": ", ".join(missing_labels)}
            )

        return cleaned


# PAS 6 – PREȚ + MĂRIME COLET
class ProductPricePackageForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["price", "package_size"]
        labels = {
            "price": _("Preț de vânzare (RON)"),
            "package_size": _("Mărime colet"),
        }
        widgets = {
            "price": forms.NumberInput(
                attrs={"class": "form-control", "min": "10", "step": "0.01"}
            ),
            "package_size": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None:
            raise forms.ValidationError(_("Te rog să introduci un preț."))
        if price < Decimal("10.00"):
            raise forms.ValidationError(_("Prețul minim este 10 RON."))
        return price


# PAS 8 – CONFIRMĂ LISTAREA (fără câmpuri – doar recapitulare)
class ProductReviewForm(forms.Form):
    """
    Pas final de review; nu are câmpuri.
    Template-ul afișează datele din context['review'] și un buton „Confirmă listarea”.
    """
    pass
