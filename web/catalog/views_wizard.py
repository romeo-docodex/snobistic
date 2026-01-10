# catalog/views_wizard.py
import os
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from formtools.wizard.views import SessionWizardView

from .forms_wizard import (
    ProductCategoryBrandForm,
    ProductDimensionsForm,
    ProductPhotosForm,
    ProductPricePackageForm,
    ProductReviewForm,
    ProductSizeDetailsForm,
    ProductSustainabilityForm,
    ProductTitleDescriptionForm,
)
from .models import Category, Product, ProductImage

PRODUCT_WIZARD_FORMS = [
    ("photos", ProductPhotosForm),  # 1 – Imagini
    ("title_desc", ProductTitleDescriptionForm),  # 2 – Titlu & descriere
    ("category_brand", ProductCategoryBrandForm),  # 3 – Gen + categorie + subcategorie + brand
    ("size_details", ProductSizeDetailsForm),  # 4 – Mărime + stare + material + culoare de bază
    ("dimensions", ProductDimensionsForm),  # 5 – Dimensiuni
    ("price_package", ProductPricePackageForm),  # 6 – Preț + mărime colet
    ("sustainability", ProductSustainabilityForm),  # 7 – Sustenabilitate
    ("review", ProductReviewForm),  # 8 – Confirmă listarea
]

PACKAGE_SIZE_DIMENSIONS = {
    "S": (30, 25, 5),
    "M": (35, 25, 15),
    "L": (60, 40, 40),
}

SYNC_LEGACY_COLORS_M2M = getattr(settings, "SNOBISTIC_SYNC_LEGACY_COLORS_M2M", True)
REMODERATE_ON_USER_EDIT = getattr(settings, "SNOBISTIC_REMODERATE_ON_USER_EDIT", True)

# ✅ important: base_url corect pentru preview (altfel url() pointează greșit)
WIZ_TMP_SUBDIR = "product_wizard_tmp"
WIZ_TMP_STORAGE = FileSystemStorage(
    location=os.path.join(settings.MEDIA_ROOT, WIZ_TMP_SUBDIR),
    base_url=(settings.MEDIA_URL.rstrip("/") + f"/{WIZ_TMP_SUBDIR}/"),
)


def _resolve_category_for_size(category_brand_data, product=None):
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

    if category and not isinstance(category, Category):
        category = getattr(category, "category", category)

    return category


def _should_reset_moderation_on_edit(*, obj: Product, request) -> bool:
    if not REMODERATE_ON_USER_EDIT:
        return False
    if not request.user.is_authenticated:
        return False
    if request.user.is_staff or request.user.is_superuser:
        return False
    return obj.moderation_status in {"APPROVED", "PUBLISHED"}


def _reset_moderation_fields(obj: Product) -> None:
    obj.moderation_status = "PENDING"
    obj.moderation_notes = ""
    obj.moderated_by = None
    obj.moderated_at = None


def _existing_photos_count(obj: Product) -> int:
    main = 1 if getattr(obj, "main_image", None) else 0
    try:
        extras = obj.images.count()
    except Exception:
        extras = ProductImage.objects.filter(product=obj).count()
    return int(main + extras)


class PhotosMultiFileWizardMixin:
    """
    Django formtools wizard NU e safe cu multiple files pe același field.
    Aici:
      - la storage: spargem extra_images în chei unice (...__0, ...__1)
      - la rebuild form: le recombinăm înapoi ca listă pe key-ul original
    """

    def _photos_keys(self, step: str):
        prefix = self.get_form_prefix(step)  # de obicei == step
        main_key = f"{prefix}-main_image"
        extra_key = f"{prefix}-extra_images"
        return main_key, extra_key

    def get_form_step_files(self, form):
        files = super().get_form_step_files(form)

        if (self.steps.current or "") != "photos":
            return files

        main_key, extra_key = self._photos_keys("photos")

        # files poate fi MultiValueDict; vrem să păstrăm toate valorile
        if not hasattr(files, "getlist"):
            return files

        extras = files.getlist(extra_key)
        if not extras:
            return files

        out = {}

        # păstrăm toate celelalte chei (exceptând extra_key original)
        for k in files.keys():
            if k == extra_key:
                continue
            # pentru safety: dacă există mai multe la o cheie, le punem pe toate
            vals = files.getlist(k)
            if not vals:
                continue
            if len(vals) == 1:
                out[k] = vals[0]
            else:
                # rar, dar posibil; le salvăm ca chei unice
                for i, v in enumerate(vals):
                    out[f"{k}__{i}"] = v

        # spargem extra_images în chei unice
        for i, f in enumerate(extras):
            out[f"{extra_key}__{i}"] = f

        return out

    def get_form(self, step=None, data=None, files=None):
        if (step or self.steps.current) == "photos" and files:
            main_key, extra_key = self._photos_keys("photos")

            # dacă vin cheile sparte, le recombinăm
            has_split = any(str(k).startswith(extra_key + "__") for k in files.keys())
            if has_split and hasattr(MultiValueDict, "setlist"):
                mv = MultiValueDict()

                # copiem cheile non-split
                for k, v in files.items():
                    if str(k).startswith(extra_key + "__"):
                        continue
                    mv.setlist(k, [v] if not isinstance(v, (list, tuple)) else list(v))

                # reconstruim lista extras
                extras = []
                # sortăm ca __0, __1...
                split_keys = sorted(
                    [k for k in files.keys() if str(k).startswith(extra_key + "__")],
                    key=lambda x: int(str(x).split("__")[-1]) if str(x).split("__")[-1].isdigit() else 0,
                )
                for k in split_keys:
                    extras.append(files.get(k))

                mv.setlist(extra_key, [x for x in extras if x])
                files = mv

        return super().get_form(step, data, files)


class ProductCreateWizard(PhotosMultiFileWizardMixin, SessionWizardView):
    form_list = PRODUCT_WIZARD_FORMS
    file_storage = WIZ_TMP_STORAGE

    def get_template_names(self):
        return [f"catalog/wizard/step_{self.steps.current}.html"]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        current_step = step or self.steps.current

        if current_step == "photos":
            kwargs["require_min_photos"] = True
            kwargs["existing_photos_count"] = 0

        if current_step == "size_details":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            category_obj = _resolve_category_for_size(category_brand)
            kwargs["category_obj"] = category_obj

            subcategory_obj = category_brand.get("subcategory")
            brand_obj = category_brand.get("brand")
            brand_other = category_brand.get("brand_other") or ""

            kwargs["subcategory_obj"] = subcategory_obj
            kwargs["brand_obj"] = brand_obj
            kwargs["brand_other"] = brand_other

            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(subcategory_obj, "measurement_profile", None)

        if current_step == "dimensions":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            subcategory_obj = category_brand.get("subcategory")
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(subcategory_obj, "measurement_profile", None)

        if current_step == "sustainability":
            size_details = self.get_cleaned_data_for_step("size_details") or {}
            kwargs["base_material"] = size_details.get("material")

        return kwargs

    def _get_commission_percent(self):
        default_commission = getattr(settings, "SNOBISTIC_DEFAULT_SELLER_COMMISSION", 10)
        seller_profile = getattr(self.request.user, "seller_profile", None)
        seller_commission = getattr(seller_profile, "commission_percent", default_commission)
        try:
            return Decimal(str(seller_commission))
        except Exception:
            return Decimal("10.0")

    def _build_photos_preview(self):
        photos = self.get_cleaned_data_for_step("photos") or {}
        main = photos.get("main_image")
        extras = photos.get("extra_images") or []

        out = []
        if main:
            out.append({"url": self.file_storage.url(main.name), "is_main": True, "is_new": True})
        for f in extras:
            if not f:
                continue
            out.append({"url": self.file_storage.url(f.name), "is_main": False, "is_new": True})
        return out

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        photos = self.get_cleaned_data_for_step("photos") or {}
        title_desc = self.get_cleaned_data_for_step("title_desc") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        category_obj = category_brand.get("subcategory") or category_brand.get("category")

        core_preview = {
            "title": title_desc.get("title"),
            "description": title_desc.get("description"),
            "gender": category_brand.get("gender"),
            "category": category_obj,
            "brand": category_brand.get("brand") or category_brand.get("brand_other"),
            "size": size_details.get("size"),
            "condition": size_details.get("condition"),
        }

        base_color_cd = size_details.get("base_color")
        colors_list = [base_color_cd] if base_color_cd else []

        details_preview = {
            "material": size_details.get("material"),
            "base_color": base_color_cd,
            "colors": colors_list,
        }

        ctx["core_preview"] = core_preview
        ctx["details_preview"] = details_preview
        ctx["price_preview"] = price_package.get("price")
        ctx["package_size_preview"] = price_package.get("package_size")

        commission_percent = self._get_commission_percent() if self.request.user.is_authenticated else Decimal("10.0")
        ctx["commission_percent"] = commission_percent

        price = price_package.get("price")
        if price:
            ctx["net_for_seller"] = price * (Decimal("1.00") - commission_percent / Decimal("100"))
        else:
            ctx["net_for_seller"] = None

        # ✅ preview imagini pentru review
        ctx["photos_preview"] = self._build_photos_preview()

        if self.steps.current == "review":
            size_details_review = dict(size_details)
            size_details_review["base_color"] = base_color_cd
            size_details_review["colors"] = colors_list

            ctx["review"] = {
                "photos": photos,
                "title_desc": title_desc,
                "category_brand": category_brand,
                "size_details": size_details_review,
                "dimensions": dimensions,
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
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        category_obj = category_brand.get("category")
        subcategory_obj = category_brand.get("subcategory")
        base_color = size_details.get("base_color")

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
            condition=size_details["condition"],
            condition_notes=size_details.get("condition_notes", ""),
            material=size_details.get("material"),
            shoe_size_eu=size_details.get("shoe_size_eu"),
            size_fr=size_details.get("size_fr"),
            size_it=size_details.get("size_it"),
            size_gb=size_details.get("size_gb"),
            base_color=base_color,
            real_color_name=(base_color.name if base_color else ""),
            shoulders_cm=dimensions.get("shoulders_cm"),
            bust_cm=dimensions.get("bust_cm"),
            waist_cm=dimensions.get("waist_cm"),
            hips_cm=dimensions.get("hips_cm"),
            length_cm=dimensions.get("length_cm"),
            sleeve_cm=dimensions.get("sleeve_cm"),
            inseam_cm=dimensions.get("inseam_cm"),
            outseam_cm=dimensions.get("outseam_cm"),
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
            sustainability_none=sustainability.get("sustainability_none", False),
            sale_type="FIXED",
            is_active=True,
            moderation_status="PENDING",
            moderation_notes="",
            moderated_by=None,
            moderated_at=None,
        )

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

        if SYNC_LEGACY_COLORS_M2M:
            if base_color:
                product.colors.set([base_color])
            else:
                product.colors.clear()

        tags = sustainability.get("sustainability_tags") or []
        product.sustainability_tags.set(tags)

        extra_images = photos.get("extra_images") or []
        for idx, img in enumerate(extra_images):
            ProductImage.objects.create(product=product, image=img, position=idx)

        return redirect("dashboard:products_list")


class ProductEditWizard(PhotosMultiFileWizardMixin, SessionWizardView):
    form_list = PRODUCT_WIZARD_FORMS
    file_storage = WIZ_TMP_STORAGE

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(Product, pk=kwargs["pk"], owner=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [f"catalog/wizard/step_{self.steps.current}.html"]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        current_step = step or self.steps.current

        if current_step == "photos":
            kwargs["require_min_photos"] = True
            kwargs["existing_photos_count"] = _existing_photos_count(self.object)

        if current_step == "size_details":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            category_obj = _resolve_category_for_size(category_brand, product=self.object)
            kwargs["category_obj"] = category_obj

            subcategory_obj = category_brand.get("subcategory") or self.object.subcategory
            brand_obj = category_brand.get("brand") if category_brand else None
            if brand_obj is None:
                brand_obj = self.object.brand
            brand_other = (category_brand.get("brand_other") if category_brand else None)
            if brand_other is None:
                brand_other = self.object.brand_other or ""

            kwargs["subcategory_obj"] = subcategory_obj
            kwargs["brand_obj"] = brand_obj
            kwargs["brand_other"] = brand_other

            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(subcategory_obj, "measurement_profile", None)

        if current_step == "dimensions":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            subcategory_obj = category_brand.get("subcategory") or self.object.subcategory
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(subcategory_obj, "measurement_profile", None)

        if current_step == "sustainability":
            size_details = self.get_cleaned_data_for_step("size_details") or {}
            base_material = size_details.get("material", self.object.material)
            kwargs["base_material"] = base_material

        return kwargs

    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)
        current_step = step or self.steps.current
        if current_step == "photos":
            form.fields["main_image"].required = False
        return form

    def _get_commission_percent(self):
        default_commission = getattr(settings, "SNOBISTIC_DEFAULT_SELLER_COMMISSION", 10)
        seller_profile = getattr(self.request.user, "seller_profile", None)
        seller_commission = getattr(seller_profile, "commission_percent", default_commission)
        try:
            return Decimal(str(seller_commission))
        except Exception:
            return Decimal("10.0")

    def _build_photos_preview(self):
        obj = self.object

        # existente
        out = []
        if obj.main_image:
            out.append({"url": obj.main_image.url, "is_main": True, "is_new": False})

        try:
            qs = obj.images.all().order_by("position", "id")
        except Exception:
            qs = ProductImage.objects.filter(product=obj).order_by("position", "id")

        for im in qs:
            if im.image:
                out.append({"url": im.image.url, "is_main": False, "is_new": False})

        # noi (din wizard step)
        photos = self.get_cleaned_data_for_step("photos") or {}
        main = photos.get("main_image")
        extras = photos.get("extra_images") or []

        if main:
            # dacă user a schimbat main, îl punem primul
            out.insert(0, {"url": self.file_storage.url(main.name), "is_main": True, "is_new": True})

        for f in extras:
            if not f:
                continue
            out.append({"url": self.file_storage.url(f.name), "is_main": False, "is_new": True})

        return out

    def get_form_initial(self, step):
        obj = getattr(self, "object", None)
        if not obj:
            return {}

        if step == "title_desc":
            return {"title": obj.title, "description": obj.description}

        if step == "category_brand":
            return {
                "gender": obj.gender,
                "category": obj.category,
                "subcategory": obj.subcategory,
                "brand": obj.brand,
                "brand_other": obj.brand_other,
            }

        if step == "size_details":
            return {
                "size": obj.size,
                "size_alpha": obj.size_alpha,
                "condition": obj.condition,
                "condition_notes": obj.condition_notes,
                "material": obj.material,
                "shoe_size_eu": obj.shoe_size_eu,
                "size_fr": obj.size_fr,
                "size_it": obj.size_it,
                "size_gb": obj.size_gb,
                "base_color": obj.base_color or obj.colors.first(),
            }

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
            return {"price": obj.price, "package_size": obj.package_size}

        if step == "sustainability":
            return {
                "sustainability_tags": obj.sustainability_tags.all(),
                "sustainability_none": obj.sustainability_none,
            }

        return {}

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)
        obj = self.object

        title_desc = self.get_cleaned_data_for_step("title_desc") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}
        photos = self.get_cleaned_data_for_step("photos") or {}

        title = title_desc.get("title", obj.title)
        description = title_desc.get("description", obj.description)

        if category_brand:
            category_obj = (
                category_brand.get("subcategory")
                or category_brand.get("category")
                or obj.subcategory
                or obj.category
            )
            gender = category_brand.get("gender", obj.gender)
            brand = category_brand.get("brand", obj.brand) or category_brand.get("brand_other", obj.brand_other)
        else:
            category_obj = obj.subcategory or obj.category
            gender = obj.gender
            brand = obj.brand or obj.brand_other

        size = size_details.get("size", obj.size)
        condition = size_details.get("condition", obj.condition)
        material = size_details.get("material", obj.material)

        base_color_cd = size_details.get("base_color")
        if base_color_cd is not None:
            colors_list = [base_color_cd] if base_color_cd else []
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
            "base_color": (base_color_cd if base_color_cd is not None else obj.base_color),
            "colors": colors_list,
        }

        ctx["core_preview"] = core_preview
        ctx["details_preview"] = details_preview

        price_value = price_package.get("price", obj.price)
        package_size_value = price_package.get("package_size", obj.package_size)

        ctx["price_preview"] = price_value
        ctx["package_size_preview"] = package_size_value

        commission_percent = self._get_commission_percent() if self.request.user.is_authenticated else Decimal("10.0")
        ctx["commission_percent"] = commission_percent

        if price_value:
            ctx["net_for_seller"] = price_value * (Decimal("1.00") - commission_percent / Decimal("100"))
        else:
            ctx["net_for_seller"] = None

        # ✅ preview imagini pentru review (existente + noi)
        ctx["photos_preview"] = self._build_photos_preview()

        if self.steps.current == "review":
            if size_details:
                size_details_review = dict(size_details)
            else:
                size_details_review = {
                    "size": obj.size,
                    "size_alpha": obj.size_alpha,
                    "condition": obj.condition,
                    "condition_notes": obj.condition_notes,
                    "material": obj.material,
                    "base_color": obj.base_color,
                }

            size_details_review["base_color"] = (base_color_cd if base_color_cd is not None else obj.base_color)
            size_details_review["colors"] = colors_list

            if not sustainability:
                sustainability = {
                    "sustainability_tags": obj.sustainability_tags.all(),
                    "sustainability_none": obj.sustainability_none,
                }

            ctx["review"] = {
                "photos": photos,
                "title_desc": title_desc or {"title": obj.title, "description": obj.description},
                "category_brand": category_brand or {
                    "gender": obj.gender,
                    "category": obj.category,
                    "subcategory": obj.subcategory,
                    "brand": obj.brand,
                    "brand_other": obj.brand_other,
                },
                "size_details": size_details_review,
                "dimensions": dimensions or {},
                "price_package": price_package or {"price": obj.price, "package_size": obj.package_size},
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
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}
        price_package = self.get_cleaned_data_for_step("price_package") or {}
        sustainability = self.get_cleaned_data_for_step("sustainability") or {}

        if title_desc:
            obj.title = title_desc.get("title", obj.title)
            obj.description = title_desc.get("description", obj.description)

        if category_brand:
            obj.gender = category_brand.get("gender", obj.gender)
            obj.category = category_brand.get("category") or obj.category
            obj.subcategory = category_brand.get("subcategory") or obj.subcategory
            obj.brand = category_brand.get("brand")
            obj.brand_other = category_brand.get("brand_other", "")
            if obj.brand:
                obj.brand_other = ""

        if size_details:
            obj.size = size_details.get("size", obj.size)
            obj.size_alpha = size_details.get("size_alpha", obj.size_alpha)
            obj.condition = size_details.get("condition", obj.condition)
            obj.condition_notes = size_details.get("condition_notes", obj.condition_notes)
            obj.material = size_details.get("material", obj.material)

            obj.shoe_size_eu = size_details.get("shoe_size_eu", obj.shoe_size_eu)
            obj.size_fr = size_details.get("size_fr", obj.size_fr)
            obj.size_it = size_details.get("size_it", obj.size_it)
            obj.size_gb = size_details.get("size_gb", obj.size_gb)

            if "base_color" in size_details:
                base_color = size_details.get("base_color")
                obj.base_color = base_color
                obj.real_color_name = base_color.name if base_color else ""

        if dimensions:
            obj.shoulders_cm = dimensions.get("shoulders_cm", obj.shoulders_cm)
            obj.bust_cm = dimensions.get("bust_cm", obj.bust_cm)
            obj.waist_cm = dimensions.get("waist_cm", obj.waist_cm)
            obj.hips_cm = dimensions.get("hips_cm", obj.hips_cm)
            obj.length_cm = dimensions.get("length_cm", obj.length_cm)
            obj.sleeve_cm = dimensions.get("sleeve_cm", obj.sleeve_cm)
            obj.inseam_cm = dimensions.get("inseam_cm", obj.inseam_cm)
            obj.outseam_cm = dimensions.get("outseam_cm", obj.outseam_cm)

            obj.shoe_insole_length_cm = dimensions.get("shoe_insole_length_cm", obj.shoe_insole_length_cm)
            obj.shoe_width_cm = dimensions.get("shoe_width_cm", obj.shoe_width_cm)
            obj.shoe_heel_height_cm = dimensions.get("shoe_heel_height_cm", obj.shoe_heel_height_cm)
            obj.shoe_total_height_cm = dimensions.get("shoe_total_height_cm", obj.shoe_total_height_cm)
            obj.bag_width_cm = dimensions.get("bag_width_cm", obj.bag_width_cm)
            obj.bag_height_cm = dimensions.get("bag_height_cm", obj.bag_height_cm)
            obj.bag_depth_cm = dimensions.get("bag_depth_cm", obj.bag_depth_cm)
            obj.strap_length_cm = dimensions.get("strap_length_cm", obj.strap_length_cm)
            obj.belt_length_total_cm = dimensions.get("belt_length_total_cm", obj.belt_length_total_cm)
            obj.belt_length_usable_cm = dimensions.get("belt_length_usable_cm", obj.belt_length_usable_cm)
            obj.belt_width_cm = dimensions.get("belt_width_cm", obj.belt_width_cm)
            obj.jewelry_chain_length_cm = dimensions.get("jewelry_chain_length_cm", obj.jewelry_chain_length_cm)
            obj.jewelry_drop_length_cm = dimensions.get("jewelry_drop_length_cm", obj.jewelry_drop_length_cm)
            obj.jewelry_pendant_size_cm = dimensions.get("jewelry_pendant_size_cm", obj.jewelry_pendant_size_cm)

        if price_package:
            obj.price = price_package.get("price", obj.price)
            obj.package_size = price_package.get("package_size", obj.package_size)

            pkg_key = obj.package_size
            if pkg_key in PACKAGE_SIZE_DIMENSIONS:
                l, w, h = PACKAGE_SIZE_DIMENSIONS[pkg_key]
                obj.package_l_cm = l
                obj.package_w_cm = w
                obj.package_h_cm = h

        if sustainability:
            obj.sustainability_none = sustainability.get("sustainability_none", obj.sustainability_none)

        obj.sale_type = "FIXED"
        obj.auction_start_price = None
        obj.auction_buy_now_price = None
        obj.auction_reserve_price = None
        obj.auction_end_at = None

        main_image = photos.get("main_image")
        if main_image:
            obj.main_image = main_image

        if _should_reset_moderation_on_edit(obj=obj, request=self.request):
            _reset_moderation_fields(obj)

        obj.save()

        if SYNC_LEGACY_COLORS_M2M and (size_details and "base_color" in size_details):
            if obj.base_color:
                obj.colors.set([obj.base_color])
            else:
                obj.colors.clear()

        tags = sustainability.get("sustainability_tags") or []
        obj.sustainability_tags.set(tags)

        extra_images = photos.get("extra_images") or []
        existing_count = obj.images.count()
        for idx, img in enumerate(extra_images, start=existing_count):
            ProductImage.objects.create(product=obj, image=img, position=idx)

        return redirect("dashboard:products_list")
