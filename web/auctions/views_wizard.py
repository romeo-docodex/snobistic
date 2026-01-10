# auctions/views_wizard.py
from __future__ import annotations

import os

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from formtools.wizard.views import SessionWizardView

from catalog.forms_wizard import ProductDimensionsForm, ProductSizeDetailsForm
from catalog.models import Category, Product, ProductImage

from .forms_wizard import (
    AuctionCategoryBrandForm,
    AuctionExistingPhotosMetaForm,
    AuctionPhotosMetaForm,
    AuctionSettingsForm,
)
from .models import Auction

AUCTION_WIZARD_FORMS = [
    ("photos_meta", AuctionPhotosMetaForm),  # 1 (CREATE upload)
    ("category_brand", AuctionCategoryBrandForm),  # 2
    ("size_details", ProductSizeDetailsForm),  # 3 (reuse)
    ("dimensions", ProductDimensionsForm),  # 4 (reuse)
    ("auction_settings", AuctionSettingsForm),  # 5
]

AUCTION_EDIT_WIZARD_FORMS = [
    ("photos_meta", AuctionExistingPhotosMetaForm),  # 1 (EDIT existing-only)
    ("category_brand", AuctionCategoryBrandForm),  # 2
    ("size_details", ProductSizeDetailsForm),  # 3
    ("dimensions", ProductDimensionsForm),  # 4
    ("auction_settings", AuctionSettingsForm),  # 5
]

WIZ_TMP_SUBDIR = "auction_wizard_tmp"
WIZ_TMP_STORAGE = FileSystemStorage(
    location=os.path.join(settings.MEDIA_ROOT, WIZ_TMP_SUBDIR),
    base_url=(settings.MEDIA_URL.rstrip("/") + f"/{WIZ_TMP_SUBDIR}/"),
)

SYNC_LEGACY_COLORS_M2M = getattr(settings, "SNOBISTIC_SYNC_LEGACY_COLORS_M2M", True)
REMODERATE_ON_USER_EDIT = getattr(settings, "SNOBISTIC_REMODERATE_ON_USER_EDIT", True)


def _user_is_seller(user) -> bool:
    try:
        prof = getattr(user, "profile", None)
        if prof is not None and getattr(prof, "role_seller", False):
            return True
    except Exception:
        pass
    return bool(getattr(user, "is_seller", False))


def _resolve_category_for_size(category_brand_data, product: Product | None = None):
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


def _existing_extra_images_count(obj: Product) -> int:
    try:
        return int(obj.images.count())
    except Exception:
        return int(ProductImage.objects.filter(product=obj).count())


def _apply_existing_photos_order_and_main(
    *, product: Product, order: list[str], main_choice: str
) -> None:
    """
    Keys:
      - 'm' = product.main_image
      - 'e<ID>' = ProductImage pk
    Behavior:
      - dacă main_choice e e<ID>, facem swap între product.main_image și ProductImage.image (ca să nu duplicăm)
      - apoi setăm ProductImage.position după order (ignorăm 'm' la poziții)
    """
    try:
        extras_qs = product.images.all().order_by("position", "id")
    except Exception:
        extras_qs = ProductImage.objects.filter(product=product).order_by("position", "id")

    extra_by_key = {f"e{im.pk}": im for im in extras_qs}

    # 1) ensure main exists if possible
    if not getattr(product, "main_image", None):
        if extras_qs.exists():
            first = extras_qs.first()
            if first and first.image:
                product.main_image = first.image
                first.delete()
                product.save(update_fields=["main_image"])
                try:
                    extras_qs = product.images.all().order_by("position", "id")
                except Exception:
                    extras_qs = ProductImage.objects.filter(product=product).order_by(
                        "position", "id"
                    )
                extra_by_key = {f"e{im.pk}": im for im in extras_qs}

    # 2) swap main if needed
    if main_choice and main_choice != "m":
        chosen = extra_by_key.get(main_choice)
        if chosen and chosen.image:
            old_main = getattr(product, "main_image", None)
            if old_main:
                product.main_image = chosen.image
                product.save(update_fields=["main_image"])

                chosen.image = old_main
                chosen.save(update_fields=["image"])
            else:
                product.main_image = chosen.image
                product.save(update_fields=["main_image"])
                chosen.delete()
                try:
                    extras_qs = product.images.all().order_by("position", "id")
                except Exception:
                    extras_qs = ProductImage.objects.filter(product=product).order_by(
                        "position", "id"
                    )
                extra_by_key = {f"e{im.pk}": im for im in extras_qs}

    # 3) positions
    seen = set()
    pos = 0
    for k in order or []:
        if k == "m":
            continue
        im = extra_by_key.get(k)
        if not im:
            continue
        seen.add(k)
        if im.position != pos:
            im.position = pos
            im.save(update_fields=["position"])
        pos += 1

    for k, im in extra_by_key.items():
        if k in seen:
            continue
        if im.position != pos:
            im.position = pos
            im.save(update_fields=["position"])
        pos += 1


def _wizard_cleanup_tmp_files(wiz: SessionWizardView) -> None:
    """
    Șterge fișierele uploadate temporar în wizard (din file_storage),
    ca să nu rămână junk în MEDIA/auction_wizard_tmp.
    """
    try:
        form_list = wiz.get_form_list() or {}
        for step in form_list.keys():
            step_files = wiz.storage.get_step_files(step) or {}
            for _k, f in step_files.items():
                try:
                    name = getattr(f, "name", None)
                    if name:
                        wiz.file_storage.delete(name)
                except Exception:
                    pass
    except Exception:
        pass


class PhotosMultiFileWizardMixin:
    """
    Aceeași strategie ca la catalog: spargem extra_images în chei unice în storage,
    apoi le recombinăm în get_form() ca listă.
    """

    def _photos_keys(self, step: str):
        prefix = self.get_form_prefix(step)
        main_key = f"{prefix}-main_image"
        extra_key = f"{prefix}-extra_images"
        return main_key, extra_key

    def get_form_step_files(self, form):
        files = super().get_form_step_files(form)

        if (self.steps.current or "") != "photos_meta":
            return files

        _main_key, extra_key = self._photos_keys("photos_meta")

        if not hasattr(files, "getlist"):
            return files

        extras = files.getlist(extra_key)
        if not extras:
            return files

        out = {}

        for k in files.keys():
            if k == extra_key:
                continue
            vals = files.getlist(k)
            if not vals:
                continue
            if len(vals) == 1:
                out[k] = vals[0]
            else:
                for i, v in enumerate(vals):
                    out[f"{k}__{i}"] = v

        for i, f in enumerate(extras):
            out[f"{extra_key}__{i}"] = f

        return out

    def get_form(self, step=None, data=None, files=None):
        if (step or self.steps.current) == "photos_meta" and files:
            _main_key, extra_key = self._photos_keys("photos_meta")

            has_split = any(str(k).startswith(extra_key + "__") for k in files.keys())
            if has_split and hasattr(MultiValueDict, "setlist"):
                mv = MultiValueDict()

                for k, v in files.items():
                    if str(k).startswith(extra_key + "__"):
                        continue
                    mv.setlist(k, [v] if not isinstance(v, (list, tuple)) else list(v))

                extras = []
                split_keys = sorted(
                    [k for k in files.keys() if str(k).startswith(extra_key + "__")],
                    key=lambda x: int(str(x).split("__")[-1])
                    if str(x).split("__")[-1].isdigit()
                    else 0,
                )
                for k in split_keys:
                    extras.append(files.get(k))

                mv.setlist(extra_key, [x for x in extras if x])
                files = mv

        return super().get_form(step, data, files)


class AuctionCreateWizard(PhotosMultiFileWizardMixin, SessionWizardView):
    form_list = AUCTION_WIZARD_FORMS
    file_storage = WIZ_TMP_STORAGE

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not _user_is_seller(request.user):
            return HttpResponseForbidden("Doar vânzătorii pot crea licitații.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # ✅ Cancel din wizard (nu vrem să salvăm nimic + curățăm tmp uploads)
        if request.method == "POST" and request.POST.get("wizard_cancel"):
            _wizard_cleanup_tmp_files(self)
            try:
                self.storage.reset()
            except Exception:
                pass
            messages.info(request, "Ai renunțat la crearea licitației.")
            return redirect("dashboard:products_list")
        return super().post(request, *args, **kwargs)

    def get_template_names(self):
        return [f"auctions/wizard/step_{self.steps.current}.html"]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        current_step = step or self.steps.current

        if current_step == "photos_meta":
            # ✅ min 4 photos enforcement (main + 3 extras)
            kwargs["require_min_photos"] = True
            kwargs["existing_photos_count"] = 0

        if current_step == "size_details":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            category_obj = self._resolve_category_for_size_local(category_brand)
            kwargs["category_obj"] = category_obj

            subcategory_obj = category_brand.get("subcategory")
            brand_obj = category_brand.get("brand")
            brand_other = category_brand.get("brand_other") or ""

            kwargs["subcategory_obj"] = subcategory_obj
            kwargs["brand_obj"] = brand_obj
            kwargs["brand_other"] = brand_other

            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        if current_step == "dimensions":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            subcategory_obj = category_brand.get("subcategory")
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        return kwargs

    def _resolve_category_for_size_local(self, category_brand):
        return _resolve_category_for_size(category_brand)

    def _build_photos_preview(self):
        photos = self.get_cleaned_data_for_step("photos_meta") or {}
        main = photos.get("main_image")
        extras = photos.get("extra_images") or []

        out = []
        if main:
            out.append(
                {
                    "url": self.file_storage.url(main.name),
                    "is_main": True,
                    "is_new": True,
                }
            )
        for f in extras:
            if not f:
                continue
            out.append(
                {
                    "url": self.file_storage.url(f.name),
                    "is_main": False,
                    "is_new": True,
                }
            )
        return out

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        photos_meta = self.get_cleaned_data_for_step("photos_meta") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}
        auction_settings = self.get_cleaned_data_for_step("auction_settings") or {}

        ctx["photos_preview"] = self._build_photos_preview()
        ctx["core_preview"] = {
            "title": photos_meta.get("title"),
            "description": photos_meta.get("description"),
            "category": category_brand.get("subcategory") or category_brand.get("category"),
            "brand": category_brand.get("brand") or category_brand.get("brand_other"),
            "size": size_details.get("size"),
            "condition": size_details.get("condition"),
            "material": size_details.get("material"),
            "base_color": size_details.get("base_color"),
        }
        ctx["dimensions_preview"] = dimensions
        ctx["auction_preview"] = auction_settings

        ctx["editing"] = False
        ctx["mode_headline"] = "Creează licitație"
        ctx["cancel_url"] = reverse("dashboard:products_list")
        return ctx

    @transaction.atomic
    def done(self, form_list, **kwargs):
        try:
            photos_meta = self.get_cleaned_data_for_step("photos_meta") or {}
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            size_details = self.get_cleaned_data_for_step("size_details") or {}
            dimensions = self.get_cleaned_data_for_step("dimensions") or {}
            auction_settings = self.get_cleaned_data_for_step("auction_settings") or {}

            category_obj = category_brand.get("category")
            subcategory_obj = category_brand.get("subcategory")
            base_color = size_details.get("base_color")

            product = Product(
                owner=self.request.user,
                title=photos_meta["title"],
                description=photos_meta["description"],
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
                sale_type="AUCTION",
                is_active=True,
                moderation_status="PENDING",
                moderation_notes="",
                moderated_by=None,
                moderated_at=None,
            )

            start_price = auction_settings["start_price"]
            product.price = start_price
            product.auction_start_price = start_price
            product.auction_reserve_price = auction_settings.get("reserve_price") or None

            product.main_image = photos_meta.get("main_image")
            product.save()

            if SYNC_LEGACY_COLORS_M2M:
                if base_color:
                    product.colors.set([base_color])
                else:
                    product.colors.clear()

            extra_images = photos_meta.get("extra_images") or []
            for idx, img in enumerate(extra_images):
                ProductImage.objects.create(product=product, image=img, position=idx)

            start_time = auction_settings.get("start_time") or timezone.now()

            auction = Auction.objects.create(
                product=product,
                creator=self.request.user,
                start_price=auction_settings["start_price"],
                reserve_price=auction_settings.get("reserve_price"),
                duration_days=auction_settings.get("duration_days") or 7,
                min_increment_percent=auction_settings.get("min_increment_percent") or 10,
                payment_window_hours=auction_settings.get("payment_window_hours") or 48,
                start_time=start_time,
                status=Auction.Status.PENDING,
            )

            if auction.start_time <= timezone.now():
                auction.activate()

            return redirect("dashboard:products_list")
        finally:
            # ✅ cleanup tmp uploads + reset session wizard storage
            _wizard_cleanup_tmp_files(self)
            try:
                self.storage.reset()
            except Exception:
                pass

    # local alias
    _resolve_category_for_size_local = staticmethod(_resolve_category_for_size)


class AuctionEditWizard(PhotosMultiFileWizardMixin, SessionWizardView):
    form_list = AUCTION_EDIT_WIZARD_FORMS
    file_storage = WIZ_TMP_STORAGE

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not _user_is_seller(request.user):
            return HttpResponseForbidden("Doar vânzătorii pot edita licitații.")
        self.product = get_object_or_404(Product, pk=kwargs["pk"], owner=request.user)
        self.auction = get_object_or_404(Auction, product=self.product)

        if self.auction.status != Auction.Status.PENDING:
            return HttpResponseForbidden("Poți edita doar licitațiile în așteptare.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # ✅ Cancel din wizard_edit:
        # dacă licitația e un draft creat de "start auction for existing product",
        # vrem să NU rămână în DB.
        if request.method == "POST" and request.POST.get("wizard_cancel"):
            _wizard_cleanup_tmp_files(self)

            try:
                self.storage.reset()
            except Exception:
                pass

            # ștergem draft-ul doar dacă produsul NU e deja AUCTION listing
            try:
                sale_type = getattr(self.product, "sale_type", None)
                is_real_auction_listing = (sale_type == "AUCTION")
            except Exception:
                is_real_auction_listing = False

            if (not is_real_auction_listing and self.auction.status == Auction.Status.PENDING):
                has_bids = False
                try:
                    has_bids = self.auction.bids.exists()
                except Exception:
                    has_bids = False

                if not has_bids:
                    try:
                        self.auction.delete()
                        messages.info(request, "Ai renunțat. Licitația draft a fost ștearsă.")
                    except Exception:
                        messages.info(request, "Ai renunțat.")
                else:
                    messages.info(
                        request,
                        "Ai renunțat. Licitația are deja oferte, nu a fost ștearsă.",
                    )
            else:
                messages.info(request, "Ai renunțat la editare.")

            return redirect("dashboard:products_list")

        return super().post(request, *args, **kwargs)

    def get_template_names(self):
        return [f"auctions/wizard/step_{self.steps.current}.html"]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        current_step = step or self.steps.current

        if current_step == "photos_meta":
            kwargs["product"] = self.product  # ✅ edit existing-only
            # ✅ min 4 photos enforcement based on existing photos in product
            kwargs["require_min_photos"] = True
            kwargs["existing_photos_count"] = _existing_photos_count(self.product)

        if current_step == "size_details":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            category_obj = _resolve_category_for_size(category_brand, product=self.product)
            kwargs["category_obj"] = category_obj

            subcategory_obj = category_brand.get("subcategory") or self.product.subcategory
            brand_obj = category_brand.get("brand") if category_brand else None
            if brand_obj is None:
                brand_obj = self.product.brand
            brand_other = (category_brand.get("brand_other") if category_brand else None)
            if brand_other is None:
                brand_other = self.product.brand_other or ""

            kwargs["subcategory_obj"] = subcategory_obj
            kwargs["brand_obj"] = brand_obj
            kwargs["brand_other"] = brand_other

            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        if current_step == "dimensions":
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            subcategory_obj = category_brand.get("subcategory") or self.product.subcategory
            if subcategory_obj is not None:
                kwargs["measurement_profile"] = getattr(
                    subcategory_obj, "measurement_profile", None
                )

        return kwargs

    def _build_photos_items(self):
        p = self.product
        items = []

        if p.main_image:
            items.append({"key": "m", "url": p.main_image.url, "is_main": True})

        try:
            qs = p.images.all().order_by("position", "id")
        except Exception:
            qs = ProductImage.objects.filter(product=p).order_by("position", "id")

        for im in qs:
            if im.image:
                items.append({"key": f"e{im.pk}", "url": im.image.url, "is_main": False})

        photos_meta = self.get_cleaned_data_for_step("photos_meta") or {}
        order = photos_meta.get("photos_order_norm") or None
        main_choice = photos_meta.get("main_choice_norm") or None

        if order:
            by_key = {x["key"]: x for x in items}
            rebuilt = []
            for k in order:
                if k in by_key:
                    rebuilt.append(by_key[k])
            for k, v in by_key.items():
                if k not in order:
                    rebuilt.append(v)
            items = rebuilt

        if main_choice:
            for it in items:
                it["is_main"] = (it["key"] == main_choice)

        return items

    def get_form_initial(self, step):
        p = self.product
        a = self.auction

        if step == "photos_meta":
            return {"title": p.title, "description": p.description}

        if step == "category_brand":
            return {
                "category": p.category,
                "subcategory": p.subcategory,
                "brand": p.brand,
                "brand_other": p.brand_other,
            }

        if step == "size_details":
            return {
                "size": p.size,
                "size_alpha": p.size_alpha,
                "condition": p.condition,
                "condition_notes": p.condition_notes,
                "material": p.material,
                "shoe_size_eu": p.shoe_size_eu,
                "size_fr": p.size_fr,
                "size_it": p.size_it,
                "size_gb": p.size_gb,
                "base_color": p.base_color or p.colors.first(),
            }

        if step == "dimensions":
            return {
                "shoulders_cm": p.shoulders_cm,
                "bust_cm": p.bust_cm,
                "waist_cm": p.waist_cm,
                "hips_cm": p.hips_cm,
                "length_cm": p.length_cm,
                "sleeve_cm": p.sleeve_cm,
                "inseam_cm": p.inseam_cm,
                "outseam_cm": p.outseam_cm,
                "shoe_insole_length_cm": p.shoe_insole_length_cm,
                "shoe_width_cm": p.shoe_width_cm,
                "shoe_heel_height_cm": p.shoe_heel_height_cm,
                "shoe_total_height_cm": p.shoe_total_height_cm,
                "bag_width_cm": p.bag_width_cm,
                "bag_height_cm": p.bag_height_cm,
                "bag_depth_cm": p.bag_depth_cm,
                "strap_length_cm": p.strap_length_cm,
                "belt_length_total_cm": p.belt_length_total_cm,
                "belt_length_usable_cm": p.belt_length_usable_cm,
                "belt_width_cm": p.belt_width_cm,
                "jewelry_chain_length_cm": p.jewelry_chain_length_cm,
                "jewelry_drop_length_cm": p.jewelry_drop_length_cm,
                "jewelry_pendant_size_cm": p.jewelry_pendant_size_cm,
            }

        if step == "auction_settings":
            return {
                "start_price": a.start_price,
                "reserve_price": a.reserve_price,
                "duration_days": a.duration_days,
                "min_increment_percent": a.min_increment_percent,
                "payment_window_hours": a.payment_window_hours,
                "start_time": a.start_time,
            }

        return {}

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        photos_meta = self.get_cleaned_data_for_step("photos_meta") or {}
        category_brand = self.get_cleaned_data_for_step("category_brand") or {}
        size_details = self.get_cleaned_data_for_step("size_details") or {}
        dimensions = self.get_cleaned_data_for_step("dimensions") or {}
        auction_settings = self.get_cleaned_data_for_step("auction_settings") or {}

        ctx["photos_items"] = self._build_photos_items()
        ctx["photos_preview"] = []

        ctx["core_preview"] = {
            "title": photos_meta.get("title", self.product.title),
            "description": photos_meta.get("description", self.product.description),
            "category": (
                category_brand.get("subcategory")
                or category_brand.get("category")
                or self.product.subcategory
                or self.product.category
            ),
            "brand": (
                category_brand.get("brand")
                or category_brand.get("brand_other")
                or self.product.brand
                or self.product.brand_other
            ),
            "size": size_details.get("size", self.product.size),
            "condition": size_details.get("condition", self.product.condition),
            "material": size_details.get("material", self.product.material),
            "base_color": size_details.get("base_color", self.product.base_color),
        }
        ctx["dimensions_preview"] = dimensions
        ctx["auction_preview"] = auction_settings

        ctx["editing"] = True
        ctx["mode_headline"] = "Editează licitație"
        ctx["cancel_url"] = reverse("dashboard:products_list")
        ctx["product"] = self.product
        ctx["auction"] = self.auction
        return ctx

    @transaction.atomic
    def done(self, form_list, **kwargs):
        try:
            p = self.product
            a = self.auction

            photos_meta = self.get_cleaned_data_for_step("photos_meta") or {}
            category_brand = self.get_cleaned_data_for_step("category_brand") or {}
            size_details = self.get_cleaned_data_for_step("size_details") or {}
            dimensions = self.get_cleaned_data_for_step("dimensions") or {}
            auction_settings = self.get_cleaned_data_for_step("auction_settings") or {}

            if photos_meta:
                p.title = photos_meta.get("title", p.title)
                p.description = photos_meta.get("description", p.description)

                order = photos_meta.get("photos_order_norm") or []
                main_choice = photos_meta.get("main_choice_norm") or "m"
                _apply_existing_photos_order_and_main(
                    product=p, order=order, main_choice=main_choice
                )

            if category_brand:
                p.category = category_brand.get("category") or p.category
                p.subcategory = category_brand.get("subcategory") or p.subcategory
                p.brand = category_brand.get("brand")
                p.brand_other = category_brand.get("brand_other", "")
                if p.brand:
                    p.brand_other = ""

            if size_details:
                p.size = size_details.get("size", p.size)
                p.size_alpha = size_details.get("size_alpha", p.size_alpha)
                p.condition = size_details.get("condition", p.condition)
                p.condition_notes = size_details.get("condition_notes", p.condition_notes)
                p.material = size_details.get("material", p.material)

                p.shoe_size_eu = size_details.get("shoe_size_eu", p.shoe_size_eu)
                p.size_fr = size_details.get("size_fr", p.size_fr)
                p.size_it = size_details.get("size_it", p.size_it)
                p.size_gb = size_details.get("size_gb", p.size_gb)

                if "base_color" in size_details:
                    base_color = size_details.get("base_color")
                    p.base_color = base_color
                    p.real_color_name = base_color.name if base_color else ""

            if dimensions:
                for k, v in dimensions.items():
                    if hasattr(p, k):
                        setattr(p, k, v if v is not None else getattr(p, k))

            if auction_settings:
                a.start_price = auction_settings.get("start_price", a.start_price)
                a.reserve_price = auction_settings.get("reserve_price", a.reserve_price)
                a.duration_days = auction_settings.get("duration_days", a.duration_days)
                a.min_increment_percent = auction_settings.get(
                    "min_increment_percent", a.min_increment_percent
                )
                a.payment_window_hours = auction_settings.get(
                    "payment_window_hours", a.payment_window_hours
                )
                if auction_settings.get("start_time"):
                    a.start_time = auction_settings["start_time"]

            p.sale_type = "AUCTION"
            p.price = a.start_price
            p.auction_start_price = a.start_price
            p.auction_reserve_price = a.reserve_price

            if _should_reset_moderation_on_edit(obj=p, request=self.request):
                _reset_moderation_fields(p)

            p.save()

            if SYNC_LEGACY_COLORS_M2M and (size_details and "base_color" in size_details):
                if p.base_color:
                    p.colors.set([p.base_color])
                else:
                    p.colors.clear()

            a.save()

            p.auction_end_at = a.end_time
            p.auction_start_price = a.start_price
            p.auction_reserve_price = a.reserve_price
            p.price = a.start_price
            p.save(
                update_fields=[
                    "auction_end_at",
                    "auction_start_price",
                    "auction_reserve_price",
                    "price",
                ]
            )

            if a.status == Auction.Status.PENDING and a.start_time and a.start_time <= timezone.now():
                a.activate()

            return redirect("dashboard:products_list")
        finally:
            # edit wizard: safe reset (și cleanup dacă au existat uploads)
            _wizard_cleanup_tmp_files(self)
            try:
                self.storage.reset()
            except Exception:
                pass
