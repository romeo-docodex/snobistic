# catalog/views_wizard.py
import os
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from formtools.wizard.views import SessionWizardView

from .forms_wizard import (
    ProductPhotosForm,
    ProductTitleDescriptionForm,
    ProductCategoryBrandForm,
    ProductSizeDetailsForm,
    ProductDimensionsForm,      # ✅ nou în import
    ProductPricePackageForm,
    ProductSustainabilityForm,
    ProductReviewForm,
)
from .models import Product, ProductImage, Category, ProductMaterial


# ✅ Ordine pași wizard – conform cerinței
PRODUCT_WIZARD_FORMS = [
    ("photos", ProductPhotosForm),                # 1 – Imagini
    ("title_desc", ProductTitleDescriptionForm),  # 2 – Titlu & descriere
    ("category_brand", ProductCategoryBrandForm), # 3 – Gen + categorie + subcategorie + brand
    ("size_details", ProductSizeDetailsForm),     # 4 – Mărime + stare + material + culori
    ("dimensions", ProductDimensionsForm),        # 5 – Dimensiuni
    ("price_package", ProductPricePackageForm),   # 6 – Preț + mărime colet
    ("sustainability", ProductSustainabilityForm),# 7 – Sustenabilitate
    ("review", ProductReviewForm),                # 8 – Confirmă listarea
]


PACKAGE_SIZE_DIMENSIONS = {
    "S": (30, 25, 5),   # Mic – plic mare
    "M": (35, 25, 15),  # Mediu – cutie de pantofi
    "L": (60, 40, 40),  # Mare – cutie de mutare
}


def _resolve_category_for_size(category_brand_data, product=None):
    """
    Întoarce un obiect Category pentru logica de size_group,
    indiferent dacă utilizatorul a ales doar categorie sau și subcategorie.
    """
    category = None
    subcategory = None

    if category_brand_data:
        category = category_brand_data.get("category")
        subcategory = category_brand_data.get("subcategory")

    if not category and subcategory is not None:
        category = getattr(subcategory, "category", None)

    if product and not category:
        category = getattr(product, "category", None)
        if not category:
            subc = getattr(product, "subcategory", None)
            if subc is not None:
                category = getattr(subc, "category", None)

    # ne asigurăm că e chiar Category (nu stric, dar e util ca tip)
    if category and not isinstance(category, Category):
        category = getattr(category, "category", category)

    return category


class ProductCreateWizard(SessionWizardView):
    """
    Wizard pentru creare produs de tip vânzare la preț fix.
    Licitațiile sunt gestionate separat, NU prin acest wizard.
    """

    form_list = PRODUCT_WIZARD_FORMS

    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "product_wizard_tmp")
    )

    def get_template_names(self):
        # catalog/sell/step_<step_key>.html
        return [f"catalog/sell/step_{self.steps.current}.html"]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        current_step = step or self.steps.current

        if current_step == "photos":
            kwargs["require_min_photos"] = True

        if current_step == "size_details":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            category_obj = _resolve_category_for_size(category_brand)
            kwargs["category_obj"] = category_obj

            subcategory_obj = category_brand.get("subcategory")
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        # ✅ pas nou – transmitem measurement_profile către formularul de DIMENSIUNI
        if current_step == "dimensions":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            subcategory_obj = category_brand.get("subcategory")
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        if current_step == "sustainability":
            # avem deja materialul și compozițiile din pasul anterior (size_details)
            size_details = self.get_cleaned_data_for_step("size_details") or {}
            kwargs["base_material"] = size_details.get("material")
            kwargs["compositions"] = size_details.get("_compositions") or []

        return kwargs

    def _get_commission_percent(self):
        default_commission = getattr(
            settings, "SNOBISTIC_DEFAULT_SELLER_COMMISSION", 10
        )
        seller_profile = getattr(self.request.user, "seller_profile", None)
        seller_commission = getattr(
            seller_profile, "commission_percent", default_commission
        )
        try:
            return Decimal(str(seller_commission))
        except Exception:
            return Decimal("10.0")

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        photos = self.get_cleaned_data_for_step("photos") or {}
        title_desc = self.get_cleaned_data_for_step("title_desc") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}     # ✅ nou
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        # preluăm categoria finală pentru preview (subcategorie > categorie)
        category_obj = (
            category_brand.get("subcategory")
            or category_brand.get("category")
        )

        core_preview = {
            "title": title_desc.get("title"),
            "description": title_desc.get("description"),
            "gender": category_brand.get("gender"),
            "category": category_obj,
            "brand": category_brand.get("brand"),
            "size": size_details.get("size"),
            "condition": size_details.get("condition"),
        }

        # normalizăm colors la listă (chiar dacă e un singur Color)
        color_cd = size_details.get("colors")
        if color_cd:
            colors_list = [color_cd]
        else:
            colors_list = []

        details_preview = {
            "material": size_details.get("material"),
            "colors": colors_list,
            # opțional: putem folosi compozițiile și în template de review
            "compositions": size_details.get("_compositions") or [],
        }

        ctx["core_preview"] = core_preview
        ctx["details_preview"] = details_preview
        ctx["price_preview"] = price_package.get("price")
        ctx["package_size_preview"] = price_package.get("package_size")

        commission_percent = (
            self._get_commission_percent()
            if self.request.user.is_authenticated
            else Decimal("10.0")
        )
        ctx["commission_percent"] = commission_percent

        price = price_package.get("price")
        if price:
            ctx["net_for_seller"] = price * (
                Decimal("1.00") - commission_percent / Decimal("100")
            )
        else:
            ctx["net_for_seller"] = None

        # pentru pasul „review” trimitem toate datele, inclusiv DIMENSIUNI
        if self.steps.current == "review":
            size_details_review = dict(size_details)
            size_details_review["colors"] = colors_list

            ctx["review"] = {
                "title_desc": title_desc,
                "category_brand": category_brand,
                "size_details": size_details_review,
                "dimensions": dimensions,      # ✅ nou
                "price_package": price_package,
                "sustainability": sustainability,
            }

        ctx["editing"] = False
        ctx["mode_headline"] = "Adaugă produs"
        ctx["cancel_url"] = reverse("dashboard:products_list")
        return ctx

    @transaction.atomic
    def done(self, form_list, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect("account_login")

        photos = self.get_cleaned_data_for_step("photos") or {}
        title_desc = self.get_cleaned_data_for_step("title_desc") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}  # ✅ nou
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        category_obj = category_brand.get("category")
        subcategory_obj = category_brand.get("subcategory")

        product = Product(
            owner=self.request.user,
            title=title_desc["title"],
            description=title_desc["description"],
            gender=category_brand["gender"],
            category=category_obj,
            subcategory=subcategory_obj,
            brand=category_brand.get("brand"),
            brand_other=category_brand.get("brand_other", ""),
            size=size_details["size"],
            size_alpha=size_details.get("size_alpha", ""),
            size_other_label=size_details.get("size_other_label", ""),
            condition=size_details["condition"],
            condition_notes=size_details.get("condition_notes", ""),
            material=size_details.get("material"),
            # mărimi numerice
            shoe_size_eu=size_details.get("shoe_size_eu"),
            size_fr=size_details.get("size_fr"),
            size_it=size_details.get("size_it"),
            size_gb=size_details.get("size_gb"),
            # ✅ dimensiuni îmbrăcăminte – acum din pasul DIMENSIONS
            shoulders_cm=dimensions.get("shoulders_cm"),
            bust_cm=dimensions.get("bust_cm"),
            waist_cm=dimensions.get("waist_cm"),
            hips_cm=dimensions.get("hips_cm"),
            length_cm=dimensions.get("length_cm"),
            sleeve_cm=dimensions.get("sleeve_cm"),
            inseam_cm=dimensions.get("inseam_cm"),
            outseam_cm=dimensions.get("outseam_cm"),
            # ✅ dimensiuni specifice
            shoe_insole_length_cm=dimensions.get("shoe_insole_length_cm"),
            shoe_width_cm=dimensions.get("shoe_width_cm"),
            shoe_heel_height_cm=dimensions.get("shoe_heel_height_cm"),
            shoe_total_height_cm=dimensions.get("shoe_total_height_cm"),
            bag_width_cm=dimensions.get("bag_width_cm"),
            bag_height_cm=dimensions.get("bag_height_cm"),
            bag_depth_cm=dimensions.get("bag_depth_cm"),
            strap_length_cm=dimensions.get("strap_length_cm"),
            belt_length_total_cm=dimensions.get("belt_length_total_cm"),
            belt_length_usable_cm=dimensions.get("belt_length_usable_cm"),
            belt_width_cm=dimensions.get("belt_width_cm"),
            jewelry_chain_length_cm=dimensions.get("jewelry_chain_length_cm"),
            jewelry_drop_length_cm=dimensions.get("jewelry_drop_length_cm"),
            jewelry_pendant_size_cm=dimensions.get("jewelry_pendant_size_cm"),
            # sustenabilitate – din pasul dedicat
            sustainability_none=sustainability.get("sustainability_none", False),
            # setări generice
            sale_type="FIXED",
            is_active=True,
            moderation_status="APPROVED",
        )

        # preț & mărime colet
        product.price = price_package["price"]
        product.package_size = price_package.get("package_size") or ""

        pkg_key = product.package_size
        if pkg_key in PACKAGE_SIZE_DIMENSIONS:
            l, w, h = PACKAGE_SIZE_DIMENSIONS[pkg_key]
            product.package_l_cm = l
            product.package_w_cm = w
            product.package_h_cm = h

        product.main_image = photos.get("main_image")
        product.save()

        # culori
        color = size_details.get("colors")
        if color:
            product.base_color = color
            product.real_color_name = color.name
            product.save(update_fields=["base_color", "real_color_name"])
            product.colors.set([color])

        # sustenabilitate – M2M din step-ul nou
        tags = sustainability.get("sustainability_tags") or []
        product.sustainability_tags.set(tags)

        # compoziție materiale
        compositions = size_details.get("_compositions") or []
        for material, percent in compositions:
            ProductMaterial.objects.create(
                product=product,
                material=material,
                percent=percent,
            )

        # imagini suplimentare
        extra_images = photos.get("extra_images") or []
        for idx, img in enumerate(extra_images):
            ProductImage.objects.create(
                product=product,
                image=img,
                position=idx,
            )

        return redirect("dashboard:products_list")


class ProductEditWizard(SessionWizardView):
    """
    Wizard pentru editare produs existent (preț fix, owner-only).
    """

    form_list = PRODUCT_WIZARD_FORMS

    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "product_wizard_tmp")
    )

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(
            Product, pk=kwargs["pk"], owner=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [f"catalog/sell/step_{self.steps.current}.html"]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        current_step = step or self.steps.current

        if current_step == "photos":
            kwargs["require_min_photos"] = False

        if current_step == "size_details":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            category_obj = _resolve_category_for_size(category_brand, product=self.object)
            kwargs["category_obj"] = category_obj

            subcategory_obj = (
                category_brand.get("subcategory") or self.object.subcategory
            )
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        # ✅ measurement_profile și pentru formularul de DIMENSIUNI
        if current_step == "dimensions":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            subcategory_obj = (
                category_brand.get("subcategory") or self.object.subcategory
            )
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        if current_step == "sustainability":
            size_details = self.get_cleaned_data_for_step("size_details") or {}
            base_material = size_details.get("material", self.object.material)

            compositions = size_details.get("_compositions")
            if compositions is None:
                # folosim direct Material objects, nu doar ID-uri
                compositions = [
                    (pm.material, pm.percent)
                    for pm in self.object.compositions.select_related("material").all()
                ]

            kwargs["base_material"] = base_material
            kwargs["compositions"] = compositions

        return kwargs

    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)
        current_step = step or self.steps.current
        if current_step == "photos":
            form.fields["main_image"].required = False
        return form

    def _get_commission_percent(self):
        default_commission = getattr(
            settings, "SNOBISTIC_DEFAULT_SELLER_COMMISSION", 10
        )
        seller_profile = getattr(self.request.user, "seller_profile", None)
        seller_commission = getattr(
            seller_profile, "commission_percent", default_commission
        )
        try:
            return Decimal(str(seller_commission))
        except Exception:
            return Decimal("10.0")

    def get_form_initial(self, step):
        obj = getattr(self, "object", None)
        if not obj:
            return {}

        if step == "title_desc":
            return {
                "title": obj.title,
                "description": obj.description,
            }

        if step == "category_brand":
            return {
                "gender": obj.gender,
                "category": obj.category,
                "subcategory": obj.subcategory,
                "brand": obj.brand,
                "brand_other": obj.brand_other,
            }

        # ✅ doar mărimi + stare + material + culori
        if step == "size_details":
            initial = {
                "size": obj.size,
                "size_alpha": obj.size_alpha,
                "size_other_label": obj.size_other_label,
                "condition": obj.condition,
                "condition_notes": obj.condition_notes,
                "material": obj.material,
                # mărimi numerice
                "shoe_size_eu": obj.shoe_size_eu,
                "size_fr": obj.size_fr,
                "size_it": obj.size_it,
                "size_gb": obj.size_gb,
                # culoare
                "colors": obj.base_color or obj.colors.first(),
            }

            # compoziție materiale – populăm până la 3 rânduri
            from .models import ProductMaterial as PM  # doar pentru claritate, nu necesar

            compositions = list(obj.compositions.all().select_related("material"))
            for idx, pm in enumerate(compositions[:3], start=1):
                initial[f"comp{idx}_material"] = pm.material
                initial[f"comp{idx}_percent"] = pm.percent

            return initial

        # ✅ dimensiuni separate în propriul pas
        if step == "dimensions":
            return {
                "shoulders_cm": obj.shoulders_cm,
                "bust_cm": obj.bust_cm,
                "waist_cm": obj.waist_cm,
                "hips_cm": obj.hips_cm,
                "length_cm": obj.length_cm,
                "sleeve_cm": obj.sleeve_cm,
                "inseam_cm": obj.inseam_cm,
                "outseam_cm": obj.outseam_cm,
                "shoe_insole_length_cm": obj.shoe_insole_length_cm,
                "shoe_width_cm": obj.shoe_width_cm,
                "shoe_heel_height_cm": obj.shoe_heel_height_cm,
                "shoe_total_height_cm": obj.shoe_total_height_cm,
                "bag_width_cm": obj.bag_width_cm,
                "bag_height_cm": obj.bag_height_cm,
                "bag_depth_cm": obj.bag_depth_cm,
                "strap_length_cm": obj.strap_length_cm,
                "belt_length_total_cm": obj.belt_length_total_cm,
                "belt_length_usable_cm": obj.belt_length_usable_cm,
                "belt_width_cm": obj.belt_width_cm,
                "jewelry_chain_length_cm": obj.jewelry_chain_length_cm,
                "jewelry_drop_length_cm": obj.jewelry_drop_length_cm,
                "jewelry_pendant_size_cm": obj.jewelry_pendant_size_cm,
            }

        if step == "price_package":
            return {
                "price": obj.price,
                "package_size": obj.package_size,
            }

        if step == "sustainability":
            return {
                "sustainability_tags": obj.sustainability_tags.all(),
                "sustainability_none": obj.sustainability_none,
            }

        return {}

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)
        obj = self.object

        photos = self.get_cleaned_data_for_step("photos") or {}
        title_desc = self.get_cleaned_data_for_step("title_desc") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}    # ✅ nou
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        title = title_desc.get("title", obj.title)
        description = title_desc.get("description", obj.description)

        # categoria / brandul curent (preferăm subcategoria pentru display)
        if category_brand:
            category_obj = (
                category_brand.get("subcategory")
                or category_brand.get("category")
                or obj.subcategory
                or obj.category
            )
            gender = category_brand.get("gender", obj.gender)
            brand = category_brand.get("brand", obj.brand)
        else:
            category_obj = obj.subcategory or obj.category
            gender = obj.gender
            brand = obj.brand

        size = size_details.get("size", obj.size)
        condition = size_details.get("condition", obj.condition)
        material = size_details.get("material", obj.material)

        # normalizez colors la listă
        color_cd = size_details.get("colors")
        if color_cd is not None:
            colors_list = [color_cd]
        else:
            colors_list = [obj.base_color] if obj.base_color else list(obj.colors.all())

        core_preview = {
            "title": title,
            "description": description,
            "gender": gender,
            "category": category_obj,
            "brand": brand,
            "size": size,
            "condition": condition,
        }

        details_preview = {
            "material": material,
            "colors": colors_list,
            "compositions": size_details.get("_compositions")
            or list(
                obj.compositions.all().select_related("material").values_list(
                    "material__name", "percent"
                )
            ),
        }

        ctx["core_preview"] = core_preview
        ctx["details_preview"] = details_preview

        price_value = price_package.get("price", obj.price)
        package_size_value = price_package.get("package_size", obj.package_size)

        ctx["price_preview"] = price_value
        ctx["package_size_preview"] = package_size_value

        commission_percent = (
            self._get_commission_percent()
            if self.request.user.is_authenticated
            else Decimal("10.0")
        )
        ctx["commission_percent"] = commission_percent

        if price_value:
            ctx["net_for_seller"] = price_value * (
                Decimal("1.00") - commission_percent / Decimal("100")
            )
        else:
            ctx["net_for_seller"] = None

        if self.steps.current == "review":
            if size_details:
                size_details_review = dict(size_details)
            else:
                size_details_review = {
                    "size": obj.size,
                    "size_alpha": obj.size_alpha,
                    "size_other_label": obj.size_other_label,
                    "condition": obj.condition,
                    "condition_notes": obj.condition_notes,
                    "material": obj.material,
                }
            size_details_review["colors"] = colors_list

            if not sustainability:
                sustainability = {
                    "sustainability_tags": obj.sustainability_tags.all(),
                    "sustainability_none": obj.sustainability_none,
                }

            ctx["review"] = {
                "title_desc": title_desc
                or {
                    "title": obj.title,
                    "description": obj.description,
                },
                "category_brand": category_brand
                or {
                    "gender": obj.gender,
                    "category": obj.category,
                    "subcategory": obj.subcategory,
                    "brand": obj.brand,
                    "brand_other": obj.brand_other,
                },
                "size_details": size_details_review,
                "dimensions": dimensions or {    # ✅ să avem ceva și dacă nu s-a modificat
                    "shoulders_cm": obj.shoulders_cm,
                    "bust_cm": obj.bust_cm,
                    "waist_cm": obj.waist_cm,
                    "hips_cm": obj.hips_cm,
                    "length_cm": obj.length_cm,
                    "sleeve_cm": obj.sleeve_cm,
                    "inseam_cm": obj.inseam_cm,
                    "outseam_cm": obj.outseam_cm,
                    "shoe_insole_length_cm": obj.shoe_insole_length_cm,
                    "shoe_width_cm": obj.shoe_width_cm,
                    "shoe_heel_height_cm": obj.shoe_heel_height_cm,
                    "shoe_total_height_cm": obj.shoe_total_height_cm,
                    "bag_width_cm": obj.bag_width_cm,
                    "bag_height_cm": obj.bag_height_cm,
                    "bag_depth_cm": obj.bag_depth_cm,
                    "strap_length_cm": obj.strap_length_cm,
                    "belt_length_total_cm": obj.belt_length_total_cm,
                    "belt_length_usable_cm": obj.belt_length_usable_cm,
                    "belt_width_cm": obj.belt_width_cm,
                    "jewelry_chain_length_cm": obj.jewelry_chain_length_cm,
                    "jewelry_drop_length_cm": obj.jewelry_drop_length_cm,
                    "jewelry_pendant_size_cm": obj.jewelry_pendant_size_cm,
                },
                "price_package": price_package
                or {
                    "price": obj.price,
                    "package_size": obj.package_size,
                },
                "sustainability": sustainability,
            }

        ctx["editing"] = True
        ctx["mode_headline"] = "Editează produs"
        ctx["cancel_url"] = reverse("dashboard:products_list")
        ctx["product"] = obj
        return ctx

    @transaction.atomic
    def done(self, form_list, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect("account_login")

        obj = self.object

        photos = self.get_cleaned_data_for_step("photos") or {}
        title_desc = self.get_cleaned_data_for_step("title_desc") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}  # ✅ nou
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        if title_desc:
            obj.title = title_desc.get("title", obj.title)
            obj.description = title_desc.get("description", obj.description)

        if category_brand:
            category_obj = category_brand.get("category") or obj.category
            obj.gender = category_brand.get("gender", obj.gender)
            obj.category = category_obj
            obj.subcategory = category_brand.get("subcategory") or obj.subcategory
            obj.brand = category_brand.get("brand", obj.brand)
            obj.brand_other = category_brand.get(
                "brand_other", obj.brand_other
            )

        if size_details:
            obj.size = size_details.get("size", obj.size)
            obj.size_alpha = size_details.get("size_alpha", obj.size_alpha)
            obj.size_other_label = size_details.get(
                "size_other_label", obj.size_other_label
            )
            obj.condition = size_details.get("condition", obj.condition)
            obj.condition_notes = size_details.get(
                "condition_notes", obj.condition_notes
            )
            obj.material = size_details.get("material", obj.material)

            # mărimi numerice
            obj.shoe_size_eu = size_details.get("shoe_size_eu", obj.shoe_size_eu)
            obj.size_fr = size_details.get("size_fr", obj.size_fr)
            obj.size_it = size_details.get("size_it", obj.size_it)
            obj.size_gb = size_details.get("size_gb", obj.size_gb)

        # ✅ dimensiuni mutat pe formularul DIMENSIONS
        if dimensions:
            obj.shoulders_cm = dimensions.get("shoulders_cm", obj.shoulders_cm)
            obj.bust_cm = dimensions.get("bust_cm", obj.bust_cm)
            obj.waist_cm = dimensions.get("waist_cm", obj.waist_cm)
            obj.hips_cm = dimensions.get("hips_cm", obj.hips_cm)
            obj.length_cm = dimensions.get("length_cm", obj.length_cm)
            obj.sleeve_cm = dimensions.get("sleeve_cm", obj.sleeve_cm)
            obj.inseam_cm = dimensions.get("inseam_cm", obj.inseam_cm)
            obj.outseam_cm = dimensions.get("outseam_cm", obj.outseam_cm)

            obj.shoe_insole_length_cm = dimensions.get(
                "shoe_insole_length_cm", obj.shoe_insole_length_cm
            )
            obj.shoe_width_cm = dimensions.get(
                "shoe_width_cm", obj.shoe_width_cm
            )
            obj.shoe_heel_height_cm = dimensions.get(
                "shoe_heel_height_cm", obj.shoe_heel_height_cm
            )
            obj.shoe_total_height_cm = dimensions.get(
                "shoe_total_height_cm", obj.shoe_total_height_cm
            )
            obj.bag_width_cm = dimensions.get("bag_width_cm", obj.bag_width_cm)
            obj.bag_height_cm = dimensions.get("bag_height_cm", obj.bag_height_cm)
            obj.bag_depth_cm = dimensions.get("bag_depth_cm", obj.bag_depth_cm)
            obj.strap_length_cm = dimensions.get(
                "strap_length_cm", obj.strap_length_cm
            )
            obj.belt_length_total_cm = dimensions.get(
                "belt_length_total_cm", obj.belt_length_total_cm
            )
            obj.belt_length_usable_cm = dimensions.get(
                "belt_length_usable_cm", obj.belt_length_usable_cm
            )
            obj.belt_width_cm = dimensions.get(
                "belt_width_cm", obj.belt_width_cm
            )
            obj.jewelry_chain_length_cm = dimensions.get(
                "jewelry_chain_length_cm", obj.jewelry_chain_length_cm
            )
            obj.jewelry_drop_length_cm = dimensions.get(
                "jewelry_drop_length_cm", obj.jewelry_drop_length_cm
            )
            obj.jewelry_pendant_size_cm = dimensions.get(
                "jewelry_pendant_size_cm", obj.jewelry_pendant_size_cm
            )

        if price_package:
            obj.price = price_package.get("price", obj.price)
            obj.package_size = price_package.get(
                "package_size", obj.package_size
            )

            pkg_key = obj.package_size
            if pkg_key in PACKAGE_SIZE_DIMENSIONS:
                l, w, h = PACKAGE_SIZE_DIMENSIONS[pkg_key]
                obj.package_l_cm = l
                obj.package_w_cm = w
                obj.package_h_cm = h

        if sustainability:
            obj.sustainability_none = sustainability.get(
                "sustainability_none", obj.sustainability_none
            )

        # rămânem pe FIXED
        obj.sale_type = "FIXED"
        obj.auction_start_price = None
        obj.auction_buy_now_price = None
        obj.auction_reserve_price = None
        obj.auction_end_at = None

        main_image = photos.get("main_image")
        if main_image:
            obj.main_image = main_image

        obj.save()

        if size_details and "colors" in size_details:
            color = size_details.get("colors")
            if color is not None:
                obj.base_color = color
                obj.real_color_name = color.name
                obj.save(update_fields=["base_color", "real_color_name"])
                obj.colors.set([color])

        # sustenabilitate – setăm pe baza noului pas
        tags = sustainability.get("sustainability_tags") or []
        obj.sustainability_tags.set(tags)

        # compoziții materiale (rămâne la fel)
        compositions = size_details.get("_compositions") if size_details else None
        if compositions is not None:
            obj.compositions.all().delete()
            for material, percent in compositions:
                ProductMaterial.objects.create(
                    product=obj,
                    material=material,
                    percent=percent,
                )

        extra_images = photos.get("extra_images") or []
        existing_count = obj.images.count()
        for idx, img in enumerate(extra_images, start=existing_count):
            ProductImage.objects.create(
                product=obj,
                image=img,
                position=idx,
            )

        return redirect("dashboard:products_list")
