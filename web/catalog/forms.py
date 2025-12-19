# catalog/forms.py
from django import forms

from .models import Product, Subcategory


class SearchForm(forms.Form):
    q = forms.CharField(
        label="",
        widget=forms.TextInput(
            attrs={"placeholder": "Caută produse…", "class": "form-control"}
        ),
    )


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            return files.getlist(name)
        file_obj = files.get(name)
        if not file_obj:
            return []
        return [file_obj]


class MultiImageField(forms.Field):
    widget = MultiFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value is None:
            return []
        return list(value)


class ProductForm(forms.ModelForm):
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

    class Meta:
        model = Product
        fields = [
            "title",
            "description",
            "price",
            "category",
            "subcategory",
            "brand",
            "brand_other",
            "size",
            "size_alpha",
            "material",
            "main_image",
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
            "inseam_cm",
            "outseam_cm",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            ),
            "price": forms.NumberInput(
                attrs={"class": "form-control", "min": "10", "step": "0.01"}
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "subcategory": forms.Select(attrs={"class": "form-select"}),
            "brand": forms.Select(attrs={"class": "form-select"}),
            "brand_other": forms.TextInput(attrs={"class": "form-control"}),
            "size": forms.Select(attrs={"class": "form-select"}),
            "size_alpha": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: S, M, L, 2XL",
                }
            ),
            "material": forms.Select(attrs={"class": "form-select"}),
            "main_image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "shoulders_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "bust_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "waist_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "hips_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "length_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "sleeve_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "inseam_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "outseam_cm": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
        }

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
            self.add_error(
                "subcategory",
                "Subcategoria aleasă nu aparține categoriei selectate.",
            )

        brand = cleaned.get("brand")
        if not brand and not brand_other:
            self.add_error(
                "brand",
                "Alege un brand din listă sau completează câmpul „Alt brand”.",
            )

        main_image = cleaned.get("main_image") or getattr(
            instance, "main_image", None
        )

        new_extra_images = cleaned.get("extra_images") or []
        existing_extra_count = instance.images.count() if instance.pk else 0

        total_photos = (1 if main_image else 0) + existing_extra_count + len(
            new_extra_images
        )

        # 🔴 acum: minim 4 poze, nu 3
        if total_photos < 4:
            raise forms.ValidationError(
                "Produsul trebuie să aibă minim 4 poze "
                "(imagine principală + cel puțin 3 imagini suplimentare)."
            )

        dim_cm_fields = [
            "shoulders_cm",
            "bust_cm",
            "waist_cm",
            "hips_cm",
            "length_cm",
            "sleeve_cm",
            "inseam_cm",
            "outseam_cm",
        ]
        filled_dims = [
            f for f in dim_cm_fields if cleaned.get(f) not in (None, "")
        ]
        if len(filled_dims) < 3:
            raise forms.ValidationError(
                "Te rog să completezi cel puțin 3 măsurători în cm "
                "(ex: bust, talie, șold, lungime etc.)."
            )

        return cleaned
