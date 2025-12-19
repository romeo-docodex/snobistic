# catalog/management/commands/seed_catalog_masterdata.py

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from catalog.models import (
    Category,
    Subcategory,
    Brand,
    Color,
    Material,
    SustainabilityTag,
)


def smart_get_or_create(model, lookup, defaults=None):
    """
    Caută întâi după lookup (ex. slug), dacă nu găsește încearcă după name (dacă există),
    apoi creează. Nu suprascrie ce există deja.
    """
    defaults = defaults or {}
    obj = model.objects.filter(**lookup).first()
    if obj:
        return obj, False

    name = lookup.get("name") or defaults.get("name")
    if name and hasattr(model, "name"):
        by_name = model.objects.filter(name=name).first()
        if by_name:
            # dacă există deja, nu rescriem, doar îl folosim
            return by_name, False

    obj, created = model.objects.get_or_create(**lookup, defaults=defaults)
    return obj, created


class Command(BaseCommand):
    help = "Populează master data pentru catalog (categorii, subcategorii, branduri, culori, materiale, tag-uri de sustenabilitate)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("== Seeding master data pentru catalog =="))

        self._seed_categories()
        self._seed_subcategories()
        self._seed_brands()
        self._seed_materials()
        self._seed_sustainability_tags()

        self.stdout.write(self.style.SUCCESS("✔ Gata, master data pentru catalog a fost seed-uit."))

    # -----------------------
    # 1. Categorii principale
    # -----------------------
    def _seed_categories(self):
        self.stdout.write("→ Categorii principale...")

        categories = [
            {"name": "Îmbrăcăminte", "slug": "imbracaminte"},
            {"name": "Încălțăminte", "slug": "incaltaminte"},
            {"name": "Accesorii", "slug": "accesorii"},
        ]

        for data in categories:
            obj, created = smart_get_or_create(
                Category,
                {"slug": data["slug"]},
                defaults={"name": data["name"]},
            )
            self.stdout.write(f"  - {obj.name} ({'creat' if created else 'existent'})")

        self.cat_imbracaminte = Category.objects.get(slug="imbracaminte")
        self.cat_incaltaminte = Category.objects.get(slug="incaltaminte")
        self.cat_accesorii = Category.objects.get(slug="accesorii")

    # -----------------------
    # 2. Subcategorii
    # -----------------------
    def _seed_subcategories(self):
        self.stdout.write("→ Subcategorii...")

        # Fallback-uri dacă constantelor li se zice altfel în model
        SIZE_GROUP_CLOTHING = getattr(Subcategory, "SIZE_GROUP_CLOTHING", "clothing")
        SIZE_GROUP_SHOES = getattr(Subcategory, "SIZE_GROUP_SHOES", "shoes")
        SIZE_GROUP_ACCESSORIES = getattr(Subcategory, "SIZE_GROUP_ACCESSORIES", "accessories")

        MP_TOP = getattr(Subcategory, "MP_TOP", "top")
        MP_DRESS = getattr(Subcategory, "MP_DRESS", "dress")
        MP_JUMPSUIT = getattr(Subcategory, "MP_JUMPSUIT", "jumpsuit")
        MP_PANTS = getattr(Subcategory, "MP_PANTS", "pants")
        MP_SKIRT = getattr(Subcategory, "MP_SKIRT", "skirt")
        MP_SHOES = getattr(Subcategory, "MP_SHOES", "shoes")
        MP_BAGS = getattr(Subcategory, "MP_BAGS", "bags")
        MP_BELTS = getattr(Subcategory, "MP_BELTS", "belts")
        MP_JEWELRY = getattr(Subcategory, "MP_JEWELRY", "jewelry")
        MP_ACCESSORY_GENERIC = getattr(
            Subcategory, "MP_ACCESSORY_GENERIC", "accessory_generic"
        )

        # valori din tabelul clientului (greutate, CO₂, copaci)
        subs = [
            # A. Îmbrăcăminte
            {
                "name": "Rochii",
                "slug": "rochii",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_DRESS,
                "avg_weight_kg": Decimal("0.35"),
                "co2_avoided_kg": Decimal("8.75"),
                "trees_equivalent": Decimal("0.44"),
                "is_non_returnable": False,
            },
            {
                "name": "Salopete",
                "slug": "salopete",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_JUMPSUIT,
                "avg_weight_kg": Decimal("0.50"),
                "co2_avoided_kg": Decimal("12.50"),
                "trees_equivalent": Decimal("0.63"),
                "is_non_returnable": False,
            },
            {
                "name": "Fuste",
                "slug": "fuste",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_SKIRT,
                "avg_weight_kg": Decimal("0.25"),
                "co2_avoided_kg": Decimal("6.25"),
                "trees_equivalent": Decimal("0.31"),
                "is_non_returnable": False,
            },
            {
                "name": "Pantaloni",
                "slug": "pantaloni",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_PANTS,
                "avg_weight_kg": Decimal("0.35"),
                "co2_avoided_kg": Decimal("8.75"),
                "trees_equivalent": Decimal("0.44"),
                "is_non_returnable": False,
            },
            {
                "name": "Blugi",
                "slug": "blugi",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_PANTS,
                "avg_weight_kg": Decimal("0.60"),
                "co2_avoided_kg": Decimal("15.00"),
                "trees_equivalent": Decimal("0.75"),
                "is_non_returnable": False,
            },
            {
                "name": "Leggings / colanți",
                "slug": "leggings-colanti",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_PANTS,
                "avg_weight_kg": Decimal("0.35"),
                "co2_avoided_kg": Decimal("8.75"),
                "trees_equivalent": Decimal("0.44"),
                "is_non_returnable": False,
            },
            {
                "name": "Tricouri / Topuri",
                "slug": "tricouri-topuri",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.16"),
                "co2_avoided_kg": Decimal("4.00"),
                "trees_equivalent": Decimal("0.20"),
                "is_non_returnable": False,
            },
            {
                "name": "Bluze",
                "slug": "bluze",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.23"),
                "co2_avoided_kg": Decimal("5.75"),
                "trees_equivalent": Decimal("0.29"),
                "is_non_returnable": False,
            },
            {
                "name": "Cămăși",
                "slug": "camasi",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.23"),
                "co2_avoided_kg": Decimal("5.75"),
                "trees_equivalent": Decimal("0.29"),
                "is_non_returnable": False,
            },
            {
                "name": "Pulovere",
                "slug": "pulovere",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.35"),
                "co2_avoided_kg": Decimal("8.75"),
                "trees_equivalent": Decimal("0.44"),
                "is_non_returnable": False,
            },
            {
                "name": "Cardigane",
                "slug": "cardigane",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.35"),
                "co2_avoided_kg": Decimal("8.75"),
                "trees_equivalent": Decimal("0.44"),
                "is_non_returnable": False,
            },
            {
                "name": "Hanorace",
                "slug": "hanorace",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.40"),
                "co2_avoided_kg": Decimal("10.00"),
                "trees_equivalent": Decimal("0.50"),
                "is_non_returnable": False,
            },
            {
                "name": "Sacouri / Blazere",
                "slug": "sacouri-blazere",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.55"),
                "co2_avoided_kg": Decimal("13.75"),
                "trees_equivalent": Decimal("0.69"),
                "is_non_returnable": False,
            },
            {
                "name": "Veste",
                "slug": "veste",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.25"),
                "co2_avoided_kg": Decimal("6.25"),
                "trees_equivalent": Decimal("0.31"),
                "is_non_returnable": False,
            },
            {
                "name": "Geci / Jachete",
                "slug": "geci-jachete",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.40"),
                "co2_avoided_kg": Decimal("10.00"),
                "trees_equivalent": Decimal("0.50"),
                "is_non_returnable": False,
            },
            {
                "name": "Paltoane",
                "slug": "paltoane",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.80"),
                "co2_avoided_kg": Decimal("20.00"),
                "trees_equivalent": Decimal("1.00"),
                "is_non_returnable": False,
            },
            {
                "name": "Costume de baie / lenjerie intimă",
                "slug": "costume-baie-lenjerie",
                "category": self.cat_imbracaminte,
                "size_group": SIZE_GROUP_CLOTHING,
                "measurement_profile": MP_TOP,
                "avg_weight_kg": Decimal("0.10"),
                "co2_avoided_kg": Decimal("2.50"),
                "trees_equivalent": Decimal("0.13"),
                "is_non_returnable": True,
            },
            # B. Încălțăminte
            {
                "name": "Pantofi sport / sneakers",
                "slug": "pantofi-sport-sneakers",
                "category": self.cat_incaltaminte,
                "size_group": SIZE_GROUP_SHOES,
                "measurement_profile": MP_SHOES,
                "avg_weight_kg": Decimal("0.90"),
                "co2_avoided_kg": Decimal("22.50"),
                "trees_equivalent": Decimal("1.13"),
                "is_non_returnable": False,
            },
            {
                "name": "Pantofi cu toc",
                "slug": "pantofi-cu-toc",
                "category": self.cat_incaltaminte,
                "size_group": SIZE_GROUP_SHOES,
                "measurement_profile": MP_SHOES,
                "avg_weight_kg": Decimal("0.80"),
                "co2_avoided_kg": Decimal("20.00"),
                "trees_equivalent": Decimal("1.00"),
                "is_non_returnable": False,
            },
            {
                "name": "Pantofi fără toc / loafers / balerini",
                "slug": "pantofi-fara-toc-loafers-balerini",
                "category": self.cat_incaltaminte,
                "size_group": SIZE_GROUP_SHOES,
                "measurement_profile": MP_SHOES,
                "avg_weight_kg": Decimal("0.70"),
                "co2_avoided_kg": Decimal("17.50"),
                "trees_equivalent": Decimal("0.88"),
                "is_non_returnable": False,
            },
            {
                "name": "Sandale",
                "slug": "sandale",
                "category": self.cat_incaltaminte,
                "size_group": SIZE_GROUP_SHOES,
                "measurement_profile": MP_SHOES,
                "avg_weight_kg": Decimal("0.60"),
                "co2_avoided_kg": Decimal("15.00"),
                "trees_equivalent": Decimal("0.75"),
                "is_non_returnable": False,
            },
            {
                "name": "Ghete / botine",
                "slug": "ghete-botine",
                "category": self.cat_incaltaminte,
                "size_group": SIZE_GROUP_SHOES,
                "measurement_profile": MP_SHOES,
                "avg_weight_kg": Decimal("1.20"),
                "co2_avoided_kg": Decimal("30.00"),
                "trees_equivalent": Decimal("1.50"),
                "is_non_returnable": False,
            },
            {
                "name": "Cizme",
                "slug": "cizme",
                "category": self.cat_incaltaminte,
                "size_group": SIZE_GROUP_SHOES,
                "measurement_profile": MP_SHOES,
                "avg_weight_kg": Decimal("1.60"),
                "co2_avoided_kg": Decimal("40.00"),
                "trees_equivalent": Decimal("2.00"),
                "is_non_returnable": False,
            },
            # C. Accesorii
            {
                "name": "Genți & rucsacuri",
                "slug": "genti-rucsacuri",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_BAGS,
                "avg_weight_kg": Decimal("0.60"),
                "co2_avoided_kg": Decimal("15.00"),
                "trees_equivalent": Decimal("0.75"),
                "is_non_returnable": False,
            },
            {
                "name": "Curele",
                "slug": "curele",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_BELTS,
                "avg_weight_kg": Decimal("0.20"),
                "co2_avoided_kg": Decimal("5.00"),
                "trees_equivalent": Decimal("0.25"),
                "is_non_returnable": False,
            },
            {
                "name": "Portofele",
                "slug": "portofele",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.15"),
                "co2_avoided_kg": Decimal("3.75"),
                "trees_equivalent": Decimal("0.19"),
                "is_non_returnable": False,
            },
            {
                "name": "Mănuși",
                "slug": "manusi",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.10"),
                "co2_avoided_kg": Decimal("2.50"),
                "trees_equivalent": Decimal("0.13"),
                "is_non_returnable": False,
            },
            {
                "name": "Căciuli / pălării / bentițe",
                "slug": "caciuli-palarii-bentite",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.15"),
                "co2_avoided_kg": Decimal("3.75"),
                "trees_equivalent": Decimal("0.19"),
                "is_non_returnable": False,
            },
            {
                "name": "Eșarfe / fulare / șaluri",
                "slug": "esarfe-fulare-saluri",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.20"),
                "co2_avoided_kg": Decimal("5.00"),
                "trees_equivalent": Decimal("0.25"),
                "is_non_returnable": False,
            },
            {
                "name": "Bijuterii",
                "slug": "bijuterii",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_JEWELRY,
                "avg_weight_kg": Decimal("0.08"),
                "co2_avoided_kg": Decimal("2.00"),
                "trees_equivalent": Decimal("0.10"),
                "is_non_returnable": False,
            },
            {
                "name": "Ochelari de soare / vedere",
                "slug": "ochelari",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.10"),
                "co2_avoided_kg": Decimal("2.50"),
                "trees_equivalent": Decimal("0.13"),
                "is_non_returnable": False,
            },
            {
                "name": "Accesorii de păr",
                "slug": "accesorii-par",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.05"),
                "co2_avoided_kg": Decimal("1.25"),
                "trees_equivalent": Decimal("0.06"),
                "is_non_returnable": False,
            },
            {
                "name": "Alte accesorii",
                "slug": "alte-accesorii",
                "category": self.cat_accesorii,
                "size_group": SIZE_GROUP_ACCESSORIES,
                "measurement_profile": MP_ACCESSORY_GENERIC,
                "avg_weight_kg": Decimal("0.20"),
                "co2_avoided_kg": Decimal("5.00"),
                "trees_equivalent": Decimal("0.25"),
                "is_non_returnable": False,
            },
        ]

        for data in subs:
            lookup = {"slug": data["slug"]}
            defaults = {
                "name": data["name"],
                "category": data["category"],
                "size_group": data["size_group"],
                "measurement_profile": data["measurement_profile"],
                "avg_weight_kg": data["avg_weight_kg"],
                "co2_avoided_kg": data["co2_avoided_kg"],
                "trees_equivalent": data["trees_equivalent"],
                "is_non_returnable": data["is_non_returnable"],
            }
            obj, created = smart_get_or_create(Subcategory, lookup, defaults=defaults)
            self.stdout.write(f"  - {obj.name} ({'creat' if created else 'existent'})")

    # -----------------------
    # 3. Branduri
    # -----------------------
    def _seed_brands(self):
        self.stdout.write("→ Branduri...")

        brands = [
            {"name": "Max Mara Group", "slug": "max-mara-group", "group_attr": "GROUP_MAX_MARA_GROUP", "is_fast_fashion": False},
            {"name": "Ralph Lauren", "slug": "ralph-lauren", "group_attr": "GROUP_RALPH_LAUREN", "is_fast_fashion": False},
            {"name": "COS", "slug": "cos", "group_attr": "GROUP_COS", "is_fast_fashion": False},
            {"name": "Gant", "slug": "gant", "group_attr": "GROUP_GANT", "is_fast_fashion": False},
            {"name": "Tommy Hilfiger", "slug": "tommy-hilfiger", "group_attr": "GROUP_TOMMY_HILFIGER", "is_fast_fashion": False},
            {"name": "Guess", "slug": "guess", "group_attr": "GROUP_GUESS", "is_fast_fashion": False},
            {"name": "Gas", "slug": "gas", "group_attr": "GROUP_GAS", "is_fast_fashion": False},
            {"name": "Pablo", "slug": "pablo", "group_attr": "GROUP_PABLO", "is_fast_fashion": False},
            {"name": "Fast fashion", "slug": "fast-fashion", "group_attr": "GROUP_FAST_FASHION", "is_fast_fashion": True},
            {"name": "Altele", "slug": "altele", "group_attr": "GROUP_OTHER", "is_fast_fashion": False},
        ]

        for data in brands:
            group_value = getattr(Brand, data["group_attr"], None) if hasattr(Brand, data["group_attr"]) else None
            lookup = {"slug": data["slug"]}
            defaults = {
                "name": data["name"],
                "is_fast_fashion": data["is_fast_fashion"],
            }
            if group_value is not None and hasattr(Brand, "group"):
                defaults["group"] = group_value

            obj, created = smart_get_or_create(Brand, lookup, defaults=defaults)
            self.stdout.write(f"  - {obj.name} ({'creat' if created else 'existent'})")

    # -----------------------
    # 5. Materiale
    # -----------------------
    def _seed_materials(self):
        self.stdout.write("→ Materiale...")

        # Valorile reale ale choices-urilor, ca să nu băgăm "clothing" sau alte valori invalide
        CT = getattr(Material, "CategoryType", None)

        if CT is not None:
            TYPE_CLOTHING = getattr(CT, "CLOTHING", "CLOTHING")
            TYPE_SHOES = getattr(CT, "SHOES", "SHOES")
            TYPE_ACCESSORIES = getattr(CT, "ACCESSORIES", "ACCESSORIES")
            TYPE_GENERIC = getattr(CT, "GENERIC", "GENERIC")
        else:
            TYPE_CLOTHING = "CLOTHING"
            TYPE_SHOES = "SHOES"
            TYPE_ACCESSORIES = "ACCESSORIES"
            TYPE_GENERIC = "GENERIC"

        sustainable_set = {
            "Bumbac organic",
            "In",
            "Lyocell / Tencel",
            "Cupro",
            "Poliester reciclat",
            "Poliamidă reciclată",
            "Piele ecologică / PU",
            "Piele ecologică / PU (încălțăminte)",
            "Piele ecologică / PU (accesorii)",
        }

        materials = [
            # 4.1 Fibre naturale (îmbrăcăminte)
            ("Bumbac", TYPE_CLOTHING),
            ("Bumbac organic", TYPE_CLOTHING),
            ("Lână", TYPE_CLOTHING),
            ("Cașmir", TYPE_CLOTHING),
            ("Mohair", TYPE_CLOTHING),
            ("Angora", TYPE_CLOTHING),
            ("Mătase", TYPE_CLOTHING),
            ("In", TYPE_CLOTHING),
            ("Alpaca", TYPE_CLOTHING),

            # 4.2 Fibre artificiale
            ("Vascoză", TYPE_CLOTHING),
            ("Modal", TYPE_CLOTHING),
            ("Lyocell / Tencel", TYPE_CLOTHING),
            ("Cupro", TYPE_CLOTHING),

            # 4.3 Fibre sintetice
            ("Poliester", TYPE_CLOTHING),
            ("Poliester reciclat", TYPE_CLOTHING),
            ("Poliamidă / Nylon", TYPE_CLOTHING),
            ("Poliamidă reciclată", TYPE_CLOTHING),
            ("Acril", TYPE_CLOTHING),
            ("Elastan", TYPE_CLOTHING),
            ("Polipropilenă", TYPE_CLOTHING),
            ("Poliuretan (PU)", TYPE_CLOTHING),

            # 4.4 Încălțăminte
            ("Piele naturală (încălțăminte)", TYPE_SHOES),
            ("Piele ecologică / PU (încălțăminte)", TYPE_SHOES),
            ("Cauciuc (încălțăminte)", TYPE_SHOES),
            ("EVA (încălțăminte)", TYPE_SHOES),
            ("Textile (încălțăminte)", TYPE_SHOES),
            ("Generic (încălțăminte)", TYPE_SHOES),

            # 4.4 Accesorii
            ("Piele naturală (accesorii)", TYPE_ACCESSORIES),
            ("Piele ecologică / PU (accesorii)", TYPE_ACCESSORIES),
            ("Cauciuc (accesorii)", TYPE_ACCESSORIES),
            ("EVA (accesorii)", TYPE_ACCESSORIES),
            ("Textile (accesorii)", TYPE_ACCESSORIES),
            ("Generic (accesorii)", TYPE_ACCESSORIES),
            ("Metal", TYPE_ACCESSORIES),
            ("Oțel inoxidabil", TYPE_ACCESSORIES),
            ("Aliaj", TYPE_ACCESSORIES),
            ("Plastic", TYPE_ACCESSORIES),
            ("Lemn", TYPE_ACCESSORIES),
            ("Sticlă", TYPE_ACCESSORIES),
            ("Cristale", TYPE_ACCESSORIES),
            ("Pietre semiprețioase", TYPE_ACCESSORIES),
        ]

        for name, cat_type in materials:
            # Material NU are slug, îl identificăm după nume
            lookup = {"name": name}
            is_sustainable = name in sustainable_set

            defaults = {}
            if hasattr(Material, "category_type"):
                defaults["category_type"] = cat_type
            if hasattr(Material, "is_sustainable"):
                defaults["is_sustainable"] = is_sustainable

            obj, created = smart_get_or_create(Material, lookup, defaults=defaults)
            self.stdout.write(
                f"  - {obj.name} ({'creat' if created else 'existent'})"
                + (" [sustenabil]" if is_sustainable else "")
            )

    # -----------------------
    # 6. Tag-uri de sustenabilitate
    # -----------------------
    def _seed_sustainability_tags(self):
        self.stdout.write("→ Tag-uri de sustenabilitate...")

        Key = SustainabilityTag.Key

        tags = [
            {
                "key": Key.DEADSTOCK,
                "name": "Deadstock / stoc nevândut",
            },
            {
                "key": Key.PRELOVED,
                "name": "Preloved / second hand",
            },
            {
                "key": Key.VINTAGE,
                "name": "Vintage",
            },
            {
                "key": Key.UPCYLED if hasattr(Key, "UPCYLED") else Key.UPCYCLED,
                "name": "Upcycled / recondiționat",
            },
            {
                "key": Key.SUSTAINABLE_MATERIALS,
                "name": "Materiale sustenabile",
            },
        ]

        for data in tags:
            lookup = {"key": data["key"]}
            defaults = {
                "name": data["name"],
            }

            obj, created = smart_get_or_create(
                SustainabilityTag,
                lookup,
                defaults=defaults,
            )
            # slug-ul va fi completat automat în model.save()
            self.stdout.write(
                f"  - {obj.name} ({'creat' if created else 'existent'})"
            )
