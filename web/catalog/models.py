# catalog/models.py
import datetime
import re
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

User = settings.AUTH_USER_MODEL


def _path_and_rename(filename: str, prefix: str) -> str:
    """
    Generează un nume scurt și unic pentru fișier, de forma:
    <prefix>/<uuid>.<ext>a

    Exemplu:
    products/main/3f9c2a1b8f2d4c0e9a7b.png
    """
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    new_name = f"{uuid.uuid4().hex}.{ext}"
    return f"{prefix}/{new_name}"


def product_main_image_upload_to(instance, filename):
    return _path_and_rename(filename, "products/main")


def product_extra_image_upload_to(instance, filename):
    return _path_and_rename(filename, "products/extra")


def category_cover_upload_to(instance, filename):
    return _path_and_rename(filename, "categories/cover")


class Gender(models.TextChoices):
    FEMALE = "F", _("Femei")
    MALE = "M", _("Bărbați")
    UNISEX = "U", _("Unisex")


class Category(models.Model):
    """
    Categorie principală:
    - Îmbrăcăminte
    - Încălțăminte
    - Accesorii
    """

    class SizeGroup(models.TextChoices):
        CLOTHING = "CLOTHING", _("Îmbrăcăminte")
        SHOES = "SHOES", _("Încălțăminte")
        ACCESSORIES = "ACCESSORIES", _("Accesorii")
        GENERIC = "GENERIC", _("Generic / toate mărimile")

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    size_group = models.CharField(
        max_length=20,
        choices=SizeGroup.choices,
        blank=True,
        help_text=_(
            "Controlează ce tip de mărimi sunt disponibile în mod implicit "
            "pentru produsele din această categorie (îmbrăcăminte / încălțăminte / accesorii)."
        ),
    )

    cover_image = models.ImageField(
        upload_to=category_cover_upload_to,
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Imagine cover folosită pe homepage și în listările de categorii."),
    )

    class Meta:
        verbose_name = _("Categorie")
        verbose_name_plural = _("Categorii")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:category_list", args=[self.slug])

    def get_effective_size_group(self):
        if self.size_group:
            return self.size_group
        return self.SizeGroup.GENERIC


class Subcategory(models.Model):
    """
    Subcategorie (cu suport de parent pentru sub-subcategorii).
    """

    class MeasurementProfile(models.TextChoices):
        TOP = "TOP", _("Top / bluze / tricouri / cămăși / pulovere / sacouri")
        DRESS = "DRESS", _("Rochii")
        JUMPSUIT = "JUMPSUIT", _("Salopete")
        PANTS = "PANTS", _("Pantaloni / blugi / leggings")
        SKIRT = "SKIRT", _("Fuste")
        SHOES = "SHOES", _("Încălțăminte")
        BAGS = "BAGS", _("Genți & rucsacuri")
        BELTS = "BELTS", _("Curele")
        JEWELRY = "JEWELRY", _("Bijuterii / accesorii mici")
        ACCESSORY_GENERIC = "ACCESSORY_GENERIC", _("Accesorii diverse")

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text=_("Dacă este setat, această subcategorie este un nivel 2 (ex: 'Geci bomber' sub 'Geci')."),
    )

    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
        help_text=_(
            "Dacă este setat, subcategoria este afișată doar pentru produse cu acel gen "
            "(Femei / Bărbați / Unisex). Lăsată necompletată = valabilă pentru toate."
        ),
    )

    size_group = models.CharField(
        max_length=20,
        choices=Category.SizeGroup.choices,
        blank=True,
        help_text=_("Dacă este setat, suprascrie grupa de mărimi a categoriei principale."),
    )

    measurement_profile = models.CharField(
        max_length=32,
        choices=MeasurementProfile.choices,
        blank=True,
        help_text=_(
            "Controlează ce măsurători în cm sunt obligatorii/opționale pentru produsele "
            "din această subcategorie (top, rochie, pantofi, genți etc.)."
        ),
    )

    is_non_returnable = models.BooleanField(
        default=False,
        help_text=_("Dacă este bifat, produsele din această subcategorie sunt marcate ca nereturnabile."),
    )

    avg_weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Greutatea medie a unui articol din această subcategorie (kg)."),
    )
    co2_avoided_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("CO₂ evitat per articol (kg)."),
    )
    trees_equivalent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Număr de copaci echivalenți per articol."),
    )

    class Meta:
        verbose_name = _("Subcategorie")
        verbose_name_plural = _("Subcategorii")
        ordering = ["category__name", "name"]
        unique_together = ("category", "parent", "name")

    def __str__(self):
        parts = [self.category.name]
        if self.parent:
            parts.append(self.parent.name)
        parts.append(self.name)
        return " / ".join(parts)

    def get_absolute_url(self):
        return self.category.get_absolute_url()

    def get_effective_size_group(self):
        if self.size_group:
            return self.size_group
        if self.category:
            return self.category.get_effective_size_group()
        return Category.SizeGroup.GENERIC

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def is_child(self) -> bool:
        return self.parent_id is not None

    @property
    def is_alt_type(self) -> bool:
        name = (self.name or "").strip().lower()
        return name.startswith("alt tip")

    @property
    def is_swimwear_or_lingerie(self) -> bool:
        lower_name = (self.name or "").lower()
        return any(
            phrase in lower_name
            for phrase in [
                "costume de baie",
                "costum de baie",
                "lenjerie intim",
            ]
        )

    def get_breadcrumb(self) -> str:
        parts = [self.name]
        p = self.parent
        while p is not None:
            parts.append(p.name)
            p = p.parent
        parts.append(self.category.name)
        return " / ".join(reversed(parts))

    def allows_gender(self, product_gender: str) -> bool:
        if not self.gender:
            return True
        if not product_gender:
            return True
        if self.gender == Gender.UNISEX:
            return True
        return self.gender == product_gender

    def clean(self):
        super().clean()
        if self.parent and self.parent.category_id != self.category_id:
            raise ValidationError(_("Categoria trebuie să fie aceeași cu a subcategoriei părinte."))

        if self.is_swimwear_or_lingerie:
            self.is_non_returnable = True

    def get_effective_impact_values(self):
        avg = self.avg_weight_kg
        co2 = self.co2_avoided_kg
        trees = self.trees_equivalent

        if avg is not None or co2 is not None or trees is not None:
            return avg, co2, trees

        if self.is_alt_type:
            if self.parent:
                parent = self.parent
                if (
                    parent.avg_weight_kg is not None
                    or parent.co2_avoided_kg is not None
                    or parent.trees_equivalent is not None
                ):
                    return (
                        parent.avg_weight_kg,
                        parent.co2_avoided_kg,
                        parent.trees_equivalent,
                    )

            siblings_qs = self.__class__.objects.filter(category=self.category)
            if self.parent:
                siblings_qs = siblings_qs.filter(parent=self.parent)

            siblings_qs = siblings_qs.exclude(pk=self.pk).exclude(name__istartswith="Alt tip")
            siblings_qs = siblings_qs.exclude(
                avg_weight_kg__isnull=True,
                co2_avoided_kg__isnull=True,
                trees_equivalent__isnull=True,
            )

            sibling = siblings_qs.first()
            if sibling:
                return (
                    sibling.avg_weight_kg,
                    sibling.co2_avoided_kg,
                    sibling.trees_equivalent,
                )

        return None, None, None


class Material(models.Model):
    class CategoryType(models.TextChoices):
        CLOTHING = "CLOTHING", _("Îmbrăcăminte")
        SHOES = "SHOES", _("Încălțăminte")
        ACCESSORIES = "ACCESSORIES", _("Accesorii")
        GENERIC = "GENERIC", _("Generic / comun")

    name = models.CharField(max_length=50, unique=True)

    category_type = models.CharField(
        max_length=20,
        choices=CategoryType.choices,
        default=CategoryType.GENERIC,
        db_index=True,
        help_text=_("Tipul principal de produs pentru acest material."),
    )

    is_sustainable = models.BooleanField(
        default=False,
        help_text=_(
            "Bifează dacă materialul este considerat sustenabil "
            "(ex: bumbac organic, in, lyocell, poliester reciclat etc.)."
        ),
    )

    class Meta:
        verbose_name = _("Material")
        verbose_name_plural = _("Materiale")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk is None:
            normalized_name = (self.name or "").strip().lower()

            sustainable_keywords = [
                "bumbac organic",
                "organic cotton",
                "organic",
                "bio",
                "hemp",
                "cânepă",
                "tencel",
                "lyocell",
                "modal",
                "poliester reciclat",
                "recycled polyester",
                "lână reciclată",
                "wool recycled",
                "bambus",
                "bamboo",
                "cupro",
                "in ",
                " in",
                "linen",
                "lenzing ecovero",
                "ecovero",
                "ramie",
            ]
            grey_keywords = [
                "poliester",
                "polyester",
                "acrilic",
                "acrylic",
                "poliamidă",
                "polyamide",
                "elastan",
                "elastane",
                "nylon",
                "viscoză",
                "viscose",
                "poliuretan",
                "polyurethane",
                "spandex",
                "pvc",
            ]

            if any(kw in normalized_name for kw in sustainable_keywords):
                self.is_sustainable = True
            elif any(kw in normalized_name for kw in grey_keywords):
                self.is_sustainable = False

        super().save(*args, **kwargs)


class Color(models.Model):
    name = models.CharField(max_length=40, unique=True)
    hex_code = models.CharField(max_length=7, blank=True, help_text="#RRGGBB (opțional)")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    """
    Brand oficial. Pentru branduri nelistate -> Product.brand_other.
    """

    class BrandGroup(models.TextChoices):
        MAX_MARA_GROUP = "MAX_MARA_GROUP", _("Max Mara Group")
        RALPH_LAUREN = "RALPH_LAUREN", _("Ralph Lauren")
        COS = "COS", _("COS")
        GANT = "GANT", _("Gant")
        TOMMY_HILFIGER = "TOMMY_HILFIGER", _("Tommy Hilfiger")
        GUESS = "GUESS", _("Guess")
        GAS = "GAS", _("Gas")
        PABLO = "PABLO", _("Pablo")
        FAST_FASHION = "FAST_FASHION", _("Fast fashion")
        OTHER = "OTHER", _("Alt brand / altele")

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    group = models.CharField(
        max_length=40,
        choices=BrandGroup.choices,
        blank=True,
        db_index=True,
        help_text=_("Gruparea brandului pentru filtre (Max Mara Group, Ralph Lauren, Fast fashion etc.)."),
    )

    is_fast_fashion = models.BooleanField(
        default=False,
        help_text=_("Setează True pentru branduri de tip fast fashion (Zara, H&M etc.)."),
    )

    is_visible_public = models.BooleanField(
        default=False,
        help_text=_("Dacă apare în filtrele/listările publice."),
    )

    is_pending_approval = models.BooleanField(
        default=False,
        help_text=_("Setat pentru brandurile noi propuse de utilizatori, până sunt aprobate de un admin."),
    )

    class Meta:
        verbose_name = _("Brand")
        verbose_name_plural = _("Branduri")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def segment(self) -> str:
        if self.group == self.BrandGroup.FAST_FASHION:
            return "fast_fashion"
        if self.group in {
            self.BrandGroup.MAX_MARA_GROUP,
            self.BrandGroup.RALPH_LAUREN,
            self.BrandGroup.COS,
            self.BrandGroup.GANT,
            self.BrandGroup.TOMMY_HILFIGER,
            self.BrandGroup.GUESS,
            self.BrandGroup.GAS,
            self.BrandGroup.PABLO,
        }:
            return "premium_mid"
        return "other"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        normalized_name = (self.name or "").strip().lower()

        if not self.group:
            if "max mara" in normalized_name:
                self.group = self.BrandGroup.MAX_MARA_GROUP
            elif "ralph lauren" in normalized_name:
                self.group = self.BrandGroup.RALPH_LAUREN
            elif normalized_name == "cos":
                self.group = self.BrandGroup.COS
            elif "gant" in normalized_name:
                self.group = self.BrandGroup.GANT
            elif "tommy hilfiger" in normalized_name:
                self.group = self.BrandGroup.TOMMY_HILFIGER
            elif "guess" in normalized_name:
                self.group = self.BrandGroup.GUESS
            elif " gas " in f" {normalized_name} ":
                self.group = self.BrandGroup.GAS
            elif "pablo" in normalized_name:
                self.group = self.BrandGroup.PABLO
            elif any(
                ff in normalized_name
                for ff in [
                    "zara",
                    "h&m",
                    "hm ",
                    "stradivarius",
                    "bershka",
                    "pull&bear",
                    "pull and bear",
                    "mango",
                    "reserved",
                    "sinsay",
                    "new yorker",
                ]
            ):
                self.group = self.BrandGroup.FAST_FASHION

        if self.group == self.BrandGroup.FAST_FASHION:
            self.is_fast_fashion = True

        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, is_archived=False)

    def public(self):
        return self.active().filter(moderation_status=Product.ModerationStatus.PUBLISHED)

    def approved_not_published(self):
        return self.active().filter(moderation_status=Product.ModerationStatus.APPROVED)

    def pending(self):
        return self.filter(moderation_status=Product.ModerationStatus.PENDING)

    def rejected(self):
        return self.filter(moderation_status=Product.ModerationStatus.REJECTED)

    def sold(self):
        return self.filter(moderation_status=Product.ModerationStatus.SOLD)


class Product(models.Model):
    SIZE_CHOICES = [
        ("One Size", "One Size"),
        ("XXS", "XXS"),
        ("XS", "XS"),
        ("S", "S"),
        ("M", "M"),
        ("L", "L"),
        ("XL", "XL"),
        ("2XL", "2XL"),
        ("3XL", "3XL"),
        ("EU 35–46.5", "EU 35–46.5"),
        ("FR 28–58", "FR 28–58"),
        ("GB 2–30", "GB 2–30"),
        ("IT 32–66", "IT 32–66"),
    ]

    SALE_TYPE_CHOICES = [
        ("FIXED", _("Vânzare la preț fix")),
        ("AUCTION", _("Licitație")),
    ]

    CONDITION_CHOICES = [
        ("NEW_TAG", _("Nou cu etichetă")),
        ("NEW_NO_TAG", _("Nou fără etichetă")),
        ("VERY_GOOD", _("Stare foarte bună")),
        ("GOOD", _("Stare bună")),
    ]

    GARMENT_TYPE_CHOICES = [
        ("TOP", _("Top / Bluză / Cămașă")),
        ("DRESS", _("Rochie")),
        ("BOTTOM", _("Pantaloni / Fustă / Jeans")),
        ("OUTERWEAR", _("Geacă / Palton")),
        ("SHOES", _("Încălțăminte")),
        ("ACCESSORY", _("Accesoriu")),
    ]

    FIT_CHOICES = [
        ("SLIM", _("Slim")),
        ("REGULAR", _("Regular")),
        ("LOOSE", _("Lejer")),
    ]

    PACKAGE_SIZE_CHOICES = [
        ("S", _("Mic – plic mare")),
        ("M", _("Mediu – cutie de pantofi")),
        ("L", _("Mare – cutie pentru mutare")),
    ]

    class ModerationStatus(models.TextChoices):
        PENDING = "PENDING", _("În așteptare")
        APPROVED = "APPROVED", _("Aprobat (validat)")
        REJECTED = "REJECTED", _("Respins")
        PUBLISHED = "PUBLISHED", _("Publicat")
        SOLD = "SOLD", _("Vândut")

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products",
        help_text=_("Cine a postat produsul"),
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()

    sale_type = models.CharField(
        max_length=10,
        choices=SALE_TYPE_CHOICES,
        default="FIXED",
        db_index=True,
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("10.00"))],
        help_text=_("Preț minim 10 RON."),
    )
    sku = models.CharField(max_length=100, unique=True, blank=True)

    category = models.ForeignKey("Category", on_delete=models.PROTECT, related_name="products")

    subcategory = models.ForeignKey(
        "Subcategory",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="products",
    )

    brand = models.ForeignKey(
        "Brand",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    brand_other = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Dacă nu găsești brandul în listă, scrie-l aici."),
    )

    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    size = models.CharField(max_length=20, choices=SIZE_CHOICES)

    size_alpha = models.CharField(
        max_length=8,
        blank=True,
        help_text=_("Mărimea literă aproximativă (XXS–3XL) sau One Size."),
    )

    shoe_size_eu = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("35.0")), MaxValueValidator(Decimal("46.5"))],
        help_text=_("Mărime încălțăminte EU (35–46.5, ex: 37.5)."),
    )

    size_fr = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(28), MaxValueValidator(58)],
        help_text=_("Mărime numerică FR (28–58)."),
    )
    size_it = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(32), MaxValueValidator(66)],
        help_text=_("Mărime numerică IT (32–66)."),
    )
    size_gb = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(2), MaxValueValidator(30)],
        help_text=_("Mărime numerică GB (2–30)."),
    )

    main_image = models.ImageField(
        upload_to=product_main_image_upload_to,
        max_length=255,
    )

    # ✅ SINGLE MATERIAL (no composition, no percents)
    material = models.ForeignKey(
        "Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_products",
    )

    garment_type = models.CharField(
        max_length=20,
        choices=GARMENT_TYPE_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )

    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        default=Gender.FEMALE,
    )

    auction_start_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("10.00"))],
        help_text=_("Preț de pornire minim 10 RON."),
    )
    auction_buy_now_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("10.00"))],
        help_text=_("Preț „Cumpără acum” (minim 10 RON)."),
    )
    auction_reserve_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("10.00"))],
        help_text=_("Nu se afișează cumpărătorilor. Minim 10 RON."),
    )
    auction_end_at = models.DateTimeField(null=True, blank=True)

    base_color = models.ForeignKey(
        "Color",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="base_products",
        help_text=_("Culoarea produsului (SINGURA culoare, folosită în filtre și UI)."),
    )

    real_color_name = models.CharField(
        max_length=80,
        blank=True,
        help_text=_("Nuanța reală (ex: Burgundy, Dusty Pink, Sage Green etc.)."),
    )

    colors = models.ManyToManyField("Color", blank=True, related_name="products")

    condition = models.CharField(max_length=12, choices=CONDITION_CHOICES, default="VERY_GOOD")
    condition_notes = models.CharField(max_length=200, blank=True)
    fit = models.CharField(max_length=8, choices=FIT_CHOICES, blank=True)

    shoulders = models.CharField(_("Umeri"), max_length=50, blank=True)
    bust = models.CharField(_("Bust"), max_length=50, blank=True)
    waist = models.CharField(_("Talie"), max_length=50, blank=True)
    hips = models.CharField(_("Șold"), max_length=50, blank=True)
    length = models.CharField(_("Lungime"), max_length=50, blank=True)
    sleeve = models.CharField(_("Mâneca"), max_length=50, blank=True)
    inseam = models.CharField(_("Crac interior"), max_length=50, blank=True)
    outseam = models.CharField(_("Crac exterior"), max_length=50, blank=True)

    shoulders_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    bust_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    waist_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    hips_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    length_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    sleeve_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    inseam_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    outseam_cm = models.PositiveSmallIntegerField(null=True, blank=True)

    shoe_insole_length_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lungimea branțului (talpă interioară) în cm."),
    )
    shoe_width_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lățimea pantofului în cm (punctul cel mai lat)."),
    )
    shoe_heel_height_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Înălțimea tocului în cm."),
    )
    shoe_total_height_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Înălțimea totală a încălțămintei (de la talpă până sus) în cm."),
    )

    bag_width_cm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("Lățimea genții în cm.")
    )
    bag_height_cm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("Înălțimea genții în cm.")
    )
    bag_depth_cm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("Adâncimea genții în cm.")
    )
    strap_length_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lungimea maximă a baretei/șnurului în cm."),
    )

    belt_length_total_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lungimea totală a curelei în cm (de la cap la cap)."),
    )
    belt_length_usable_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lungimea utilă a curelei în cm (de la cataramă până la ultima gaură)."),
    )
    belt_width_cm = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True, help_text=_("Lățimea curelei în cm.")
    )

    jewelry_chain_length_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lungimea lanțului / colierului în cm."),
    )
    jewelry_drop_length_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lungimea „drop-ului” (cercei, pandantiv) în cm."),
    )
    jewelry_pendant_size_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Dimensiunea aproximativă a pandantivului în cm."),
    )

    package_size = models.CharField(
        max_length=1,
        choices=PACKAGE_SIZE_CHOICES,
        blank=True,
        db_index=True,
        help_text=_("Alege dimensiunea estimativă a coletului: Mic, Mediu sau Mare."),
    )

    weight_g = models.PositiveIntegerField(null=True, blank=True)
    package_l_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    package_w_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    package_h_cm = models.PositiveSmallIntegerField(null=True, blank=True)

    pickup_location = models.ForeignKey(
        "accounts.SellerLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )

    sustainability_tags = models.ManyToManyField(
        "SustainabilityTag",
        blank=True,
        related_name="products",
        help_text=_("Deadstock, Preloved, Vintage, Upcycled, Materiale sustenabile."),
    )
    sustainability_none = models.BooleanField(
        default=False,
        help_text=_("Bifează dacă produsul NU are niciun element de sustenabilitate."),
    )

    moderation_status = models.CharField(
        max_length=10,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
        help_text=_(
            "Workflow: PENDING (în așteptare) -> APPROVED (validat, dar nepublic) -> "
            "PUBLISHED (public/vizibil). REJECTED (respins). SOLD (vândut)."
        ),
    )
    moderation_notes = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_products",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "created_at"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["subcategory", "is_active"]),
            models.Index(fields=["owner"]),
            models.Index(fields=["moderation_status"]),
            models.Index(fields=["sale_type"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["size_fr"]),
            models.Index(fields=["size_it"]),
            models.Index(fields=["size_gb"]),
            models.Index(fields=["shoe_size_eu"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:product_detail", args=[self.slug])

    @property
    def color(self):
        return self.base_color

    def _sync_single_color_relations(self) -> None:
        if not self.pk:
            return

        existing_ids = list(self.colors.values_list("id", flat=True)[:2])

        if self.base_color_id:
            if existing_ids != [self.base_color_id] or len(existing_ids) != 1:
                self.colors.set([self.base_color_id])
            return

        if not existing_ids:
            self.colors.clear()
            return

        chosen_id = existing_ids[0]
        self.__class__.objects.filter(pk=self.pk).update(base_color_id=chosen_id)
        self.base_color_id = chosen_id
        self.colors.set([chosen_id])

    @property
    def display_brand(self) -> str:
        if self.brand:
            return self.brand.name
        return self.brand_other or ""

    @property
    def display_size(self) -> str:
        if self.size_alpha:
            return self.size_alpha
        return self.size or ""

    @property
    def is_new_condition(self) -> bool:
        return self.condition in {"NEW_TAG", "NEW_NO_TAG"}

    @property
    def is_pending(self) -> bool:
        return self.moderation_status == self.ModerationStatus.PENDING

    @property
    def is_approved(self) -> bool:
        return self.moderation_status in {
            self.ModerationStatus.APPROVED,
            self.ModerationStatus.PUBLISHED,
            self.ModerationStatus.SOLD,
        }

    @property
    def is_published(self) -> bool:
        return (
            self.moderation_status == self.ModerationStatus.PUBLISHED
            and self.is_active
            and not self.is_archived
        )

    @property
    def is_public_listed(self) -> bool:
        return self.is_published

    @property
    def is_sold(self) -> bool:
        return self.moderation_status == self.ModerationStatus.SOLD

    def can_be_published(self) -> bool:
        if self.is_archived or not self.is_active:
            return False
        if self.moderation_status != self.ModerationStatus.APPROVED:
            return False
        return self.has_minimum_images()

    def mark_pending(self, *, by=None, notes: str = "") -> None:
        self.moderation_status = self.ModerationStatus.PENDING
        self.moderation_notes = notes or ""
        self.moderated_by = by
        self.moderated_at = timezone.now()
        self.published_at = None

    def approve(self, *, by=None, notes: str = "") -> None:
        self.moderation_status = self.ModerationStatus.APPROVED
        self.moderation_notes = notes or ""
        self.moderated_by = by
        self.moderated_at = timezone.now()
        if self.published_at and self.moderation_status != self.ModerationStatus.PUBLISHED:
            self.published_at = None

    def reject(self, *, by=None, notes: str = "") -> None:
        self.moderation_status = self.ModerationStatus.REJECTED
        self.moderation_notes = notes or ""
        self.moderated_by = by
        self.moderated_at = timezone.now()
        self.published_at = None

    def publish(self, *, by=None, notes: str = "") -> None:
        if self.moderation_status == self.ModerationStatus.PUBLISHED:
            return
        if self.moderation_status != self.ModerationStatus.APPROVED:
            raise ValidationError({"moderation_status": _("Poți publica doar produse APPROVED.")})
        if self.is_archived or not self.is_active:
            raise ValidationError({"is_active": _("Nu poți publica un produs inactiv sau arhivat.")})
        self.moderation_status = self.ModerationStatus.PUBLISHED
        self.moderation_notes = notes or self.moderation_notes
        self.moderated_by = by
        self.moderated_at = timezone.now()
        self.published_at = self.published_at or timezone.now()

    def unpublish(self, *, by=None, notes: str = "") -> None:
        if self.moderation_status != self.ModerationStatus.PUBLISHED:
            return
        self.moderation_status = self.ModerationStatus.APPROVED
        self.moderation_notes = notes or self.moderation_notes
        self.moderated_by = by
        self.moderated_at = timezone.now()
        self.published_at = None

    def mark_sold(self, *, by=None, notes: str = "") -> None:
        self.moderation_status = self.ModerationStatus.SOLD
        self.moderation_notes = notes or self.moderation_notes
        self.moderated_by = by
        self.moderated_at = timezone.now()

    @property
    def has_authentication_badge(self) -> bool:
        auth_obj = getattr(self, "authentication", None)
        if not auth_obj:
            return False
        return getattr(auth_obj, "is_verified", False)

    @property
    def has_sustainable_materials(self) -> bool:
        # ✅ ONLY single material now
        return bool(self.material and getattr(self.material, "is_sustainable", False))

    def has_minimum_images(self) -> bool:
        extra = self.images.count()
        main = 1 if self.main_image else 0
        return (main + extra) >= 4

    def _clean_code(self, text: str, length: int = 3) -> str:
        alnum = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()
        if not alnum:
            alnum = "XXX"
        return (alnum[:length]).ljust(length, "X")

    def get_seller_code(self) -> str:
        try:
            return self.owner.email.split("@")[0][:3].upper()
        except Exception:
            return "SEL"

    def get_weight_kg(self):
        grams = self.weight_g or 500
        return (Decimal(grams) / Decimal("1000")).quantize(Decimal("0.01"))

    def get_shipping_rate_for_display(self):
        from logistics.models import Courier, ShippingRate

        try:
            curiera = Courier.objects.get(slug="curiera")
            qs = ShippingRate.objects.filter(courier=curiera, is_active=True)
        except Courier.DoesNotExist:
            qs = ShippingRate.objects.filter(is_active=True)

        return qs.order_by("base_price").first()

    def get_shipping_price_estimate(self):
        rate = self.get_shipping_rate_for_display()
        if not rate:
            return None
        return rate.base_price

    def get_shipping_days_estimate(self):
        rate = self.get_shipping_rate_for_display()
        if not rate:
            return None, None
        return rate.delivery_days_min, rate.delivery_days_max

    def get_subcategory_impact(self):
        if not self.subcategory:
            return None, None, None
        return self.subcategory.get_effective_impact_values()

    @property
    def subcategory_has_impact_data(self) -> bool:
        if not self.subcategory:
            return False
        avg, co2, trees = self.subcategory.get_effective_impact_values()
        return any(v is not None for v in (avg, co2, trees))

    def clean(self):
        super().clean()

        if self.subcategory and self.subcategory.gender:
            if not self.subcategory.allows_gender(self.gender):
                raise ValidationError(
                    {
                        "subcategory": _(
                            "Subcategoria aleasă este definită pentru %(sub_gender)s "
                            "și nu poate fi folosită pentru produse de tip %(prod_gender)s."
                        )
                        % {
                            "sub_gender": self.subcategory.get_gender_display(),
                            "prod_gender": self.get_gender_display(),
                        }
                    }
                )

        if self.base_color and not self.real_color_name:
            self.real_color_name = self.base_color.name

        if not self.pk:
            return

        color_ids = list(self.colors.values_list("id", flat=True))
        if len(color_ids) > 1:
            raise ValidationError({"colors": _("Produsul poate avea o singură culoare.")})
        if self.base_color_id and color_ids and color_ids[0] != self.base_color_id:
            raise ValidationError({"colors": _("Culoarea selectată trebuie să fie aceeași cu „base_color”.")})

        if self.sustainability_none and self.sustainability_tags.exists():
            raise ValidationError(
                {
                    "sustainability_none": _(
                        "Nu poți bifa „Nici una” și în același timp alte opțiuni de sustenabilitate."
                    )
                }
            )

        if (
            self.sustainability_tags.filter(key=SustainabilityTag.Key.SUSTAINABLE_MATERIALS).exists()
            and not self.has_sustainable_materials
        ):
            raise ValidationError(
                {
                    "sustainability_tags": _(
                        "Poți marca „Materiale sustenabile” doar dacă produsul "
                        "are material principal marcat ca sustenabil."
                    )
                }
            )

    def _infer_garment_type(self) -> str:
        mp = None
        if getattr(self, "subcategory", None):
            mp = self.subcategory.measurement_profile

        if mp:
            mp_to_gt = {
                Subcategory.MeasurementProfile.TOP: "TOP",
                Subcategory.MeasurementProfile.DRESS: "DRESS",
                Subcategory.MeasurementProfile.JUMPSUIT: "DRESS",
                Subcategory.MeasurementProfile.PANTS: "BOTTOM",
                Subcategory.MeasurementProfile.SKIRT: "BOTTOM",
                Subcategory.MeasurementProfile.SHOES: "SHOES",
                Subcategory.MeasurementProfile.BAGS: "ACCESSORY",
                Subcategory.MeasurementProfile.BELTS: "ACCESSORY",
                Subcategory.MeasurementProfile.JEWELRY: "ACCESSORY",
                Subcategory.MeasurementProfile.ACCESSORY_GENERIC: "ACCESSORY",
            }
            if mp in mp_to_gt:
                return mp_to_gt[mp]

        cat = getattr(self, "category", None)
        if cat and hasattr(cat, "get_effective_size_group"):
            sg = cat.get_effective_size_group()
            if sg == Category.SizeGroup.CLOTHING:
                return "TOP"
            if sg == Category.SizeGroup.SHOES:
                return "SHOES"
            if sg == Category.SizeGroup.ACCESSORIES:
                return "ACCESSORY"

        return ""

    def save(self, *args, **kwargs):
        old_slug = None
        if self.pk:
            try:
                old = Product.objects.only("slug").get(pk=self.pk)
                old_slug = old.slug
            except Product.DoesNotExist:
                old_slug = None

        if self.pk is None and not getattr(self, "_skip_moderation_guard", False):
            self.moderation_status = self.ModerationStatus.PENDING
            self.published_at = None

        if not self.slug:
            base = slugify(self.title) or "produs"
            slug = base
            Model = self.__class__
            counter = 1
            while Model.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug

        size_source = self.size_alpha or self.size
        if not self.sku:
            if self.subcategory_id and getattr(self, "subcategory", None):
                cat_name = self.subcategory.name
            elif self.category_id and getattr(self, "category", None):
                cat_name = self.category.name
            else:
                cat_name = ""

            parts = [
                self._clean_code(self.get_seller_code(), 3),
                self._clean_code(cat_name, 3),
                self._clean_code(self.title, 3),
                datetime.datetime.now().strftime("%Y%m%d%H%M"),
                self._clean_code(size_source, 3),
            ]
            self.sku = "/".join(parts)

        if not self.garment_type:
            inferred = self._infer_garment_type()
            if inferred:
                self.garment_type = inferred

        if self.moderation_status not in {self.ModerationStatus.PUBLISHED, self.ModerationStatus.SOLD}:
            self.published_at = None
        elif self.moderation_status == self.ModerationStatus.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

        self._sync_single_color_relations()

        if old_slug and old_slug != self.slug:
            ProductSlugHistory.objects.create(product=self, old_slug=old_slug)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_extra_image_upload_to, max_length=255)
    position = models.PositiveIntegerField(default=0, db_index=True)
    alt_text = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Image for {self.product.title}"


class SustainabilityTag(models.Model):
    class Key(models.TextChoices):
        DEADSTOCK = "DEADSTOCK", _("Deadstock / stoc nevândut")
        PRELOVED = "PRELOVED", _("Preloved / second hand")
        VINTAGE = "VINTAGE", _("Vintage")
        UPCYCLED = "UPCYCLED", _("Upcycled / recondiționat")
        SUSTAINABLE_MATERIALS = "SUSTAINABLE_MATERIALS", _("Materiale sustenabile")

    key = models.CharField(max_length=40, choices=Key.choices, unique=True, db_index=True)
    name = models.CharField(
        max_length=80,
        unique=True,
        help_text=_("Denumire afișată (poate coincide cu get_key_display)."),
    )
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        verbose_name = _("Tag de sustenabilitate")
        verbose_name_plural = _("Tag-uri de sustenabilitate")
        ordering = ["name"]

    def __str__(self):
        return self.name or self.get_key_display()

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.get_key_display()
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


Product.add_to_class("tags", models.ManyToManyField("Tag", blank=True, related_name="products"))


class ProductSlugHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="slug_history")
    old_slug = models.SlugField(max_length=200, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.old_slug} -> {self.product.slug}"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ❤️ {self.product_id}"
