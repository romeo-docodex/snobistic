# fix_subcategories.py
from decimal import Decimal

from django.utils.text import slugify
from catalog.models import Category, Subcategory, Gender


SUBCATEGORY_CONFIG = {
    # --- ACCESORII ---

    ("Accesorii", "Accesorii de păr"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.05"),
        "co2_avoided_kg": Decimal("1.25"),
        "trees_equivalent": Decimal("0.06"),
    },
    ("Accesorii", "Alte accesorii"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.20"),
        "co2_avoided_kg": Decimal("5.00"),
        "trees_equivalent": Decimal("0.25"),
    },
    ("Accesorii", "Bijuterii"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.JEWELRY,
        "avg_weight_kg": Decimal("0.08"),
        "co2_avoided_kg": Decimal("2.00"),
        "trees_equivalent": Decimal("0.10"),
    },
    ("Accesorii", "Curele"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.BELTS,
        "avg_weight_kg": Decimal("0.20"),
        "co2_avoided_kg": Decimal("5.00"),
        "trees_equivalent": Decimal("0.25"),
    },
    ("Accesorii", "Căciuli / pălării / bentițe"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.15"),
        "co2_avoided_kg": Decimal("3.75"),
        "trees_equivalent": Decimal("0.19"),
    },
    ("Accesorii", "Eșarfe / fulare / șaluri"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.20"),
        "co2_avoided_kg": Decimal("5.00"),
        "trees_equivalent": Decimal("0.25"),
    },
    ("Accesorii", "Genți & rucsacuri"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.BAGS,
        "avg_weight_kg": Decimal("0.60"),
        "co2_avoided_kg": Decimal("15.00"),
        "trees_equivalent": Decimal("0.75"),
    },
    ("Accesorii", "Mănuși"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.10"),
        "co2_avoided_kg": Decimal("2.50"),
        "trees_equivalent": Decimal("0.13"),
    },
    ("Accesorii", "Ochelari de soare / vedere"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.10"),
        "co2_avoided_kg": Decimal("2.50"),
        "trees_equivalent": Decimal("0.13"),
    },
    ("Accesorii", "Portofele"): {
        "size_group": Category.SizeGroup.ACCESSORIES,
        "measurement_profile": Subcategory.MeasurementProfile.ACCESSORY_GENERIC,
        "avg_weight_kg": Decimal("0.15"),
        "co2_avoided_kg": Decimal("3.75"),
        "trees_equivalent": Decimal("0.19"),
    },

    # --- ÎMBRĂCĂMINTE ---

    ("Îmbrăcăminte", "Alt tip de Îmbrăcăminte"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        # fără valori de impact în tabel – lăsăm None
    },
    ("Îmbrăcăminte", "Blugi"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.PANTS,
        "avg_weight_kg": Decimal("0.60"),
        "co2_avoided_kg": Decimal("15.00"),
        "trees_equivalent": Decimal("0.75"),
    },
    ("Îmbrăcăminte", "Bluze"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.23"),
        "co2_avoided_kg": Decimal("5.75"),
        "trees_equivalent": Decimal("0.29"),
    },
    ("Îmbrăcăminte", "Cardigane"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.35"),
        "co2_avoided_kg": Decimal("8.75"),
        "trees_equivalent": Decimal("0.44"),
    },
    ("Îmbrăcăminte", "Costume de baie / lenjerie intima"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.DRESS,
        "avg_weight_kg": Decimal("0.10"),
        "co2_avoided_kg": Decimal("2.50"),
        "trees_equivalent": Decimal("0.13"),
    },
    ("Îmbrăcăminte", "Costume de baie / lenjerie intimă"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.DRESS,
        "is_non_returnable": True,
        "avg_weight_kg": Decimal("0.10"),
        "co2_avoided_kg": Decimal("2.50"),
        "trees_equivalent": Decimal("0.13"),
    },
    ("Îmbrăcăminte", "Cămăși"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.23"),
        "co2_avoided_kg": Decimal("5.75"),
        "trees_equivalent": Decimal("0.29"),
    },
    ("Îmbrăcăminte", "Fuste"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.SKIRT,
        "gender": Gender.FEMALE,
        "avg_weight_kg": Decimal("0.25"),
        "co2_avoided_kg": Decimal("6.25"),
        "trees_equivalent": Decimal("0.31"),
    },
    ("Îmbrăcăminte", "Geci / Jachete"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.40"),
        "co2_avoided_kg": Decimal("10.00"),
        "trees_equivalent": Decimal("0.50"),
    },
    ("Îmbrăcăminte", "Hanorace"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.40"),
        "co2_avoided_kg": Decimal("10.00"),
        "trees_equivalent": Decimal("0.50"),
    },
    ("Îmbrăcăminte", "Leggings / colanți"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.PANTS,
        "avg_weight_kg": Decimal("0.35"),
        "co2_avoided_kg": Decimal("8.75"),
        "trees_equivalent": Decimal("0.44"),
    },
    ("Îmbrăcăminte", "Paltoane"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.80"),
        "co2_avoided_kg": Decimal("20.00"),
        "trees_equivalent": Decimal("1.00"),
    },
    ("Îmbrăcăminte", "Pantaloni"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.PANTS,
        "avg_weight_kg": Decimal("0.35"),
        "co2_avoided_kg": Decimal("8.75"),
        "trees_equivalent": Decimal("0.44"),
    },
    ("Îmbrăcăminte", "Pulovere"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.35"),
        "co2_avoided_kg": Decimal("8.75"),
        "trees_equivalent": Decimal("0.44"),
    },
    ("Îmbrăcăminte", "Rochii"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.DRESS,
        "gender": Gender.FEMALE,
        "avg_weight_kg": Decimal("0.35"),
        "co2_avoided_kg": Decimal("8.75"),
        "trees_equivalent": Decimal("0.44"),
    },
    ("Îmbrăcăminte", "Sacouri / Blazere"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.55"),
        "co2_avoided_kg": Decimal("13.75"),
        "trees_equivalent": Decimal("0.69"),
    },
    ("Îmbrăcăminte", "Salopete"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.JUMPSUIT,
        "avg_weight_kg": Decimal("0.50"),
        "co2_avoided_kg": Decimal("12.50"),
        "trees_equivalent": Decimal("0.63"),
    },
    ("Îmbrăcăminte", "Tricouri / Topuri"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.16"),
        "co2_avoided_kg": Decimal("4.00"),
        "trees_equivalent": Decimal("0.20"),
    },
    ("Îmbrăcăminte", "Veste"): {
        "size_group": Category.SizeGroup.CLOTHING,
        "measurement_profile": Subcategory.MeasurementProfile.TOP,
        "avg_weight_kg": Decimal("0.25"),
        "co2_avoided_kg": Decimal("6.25"),
        "trees_equivalent": Decimal("0.31"),
    },

    # --- ÎNCĂLȚĂMINTE ---

    ("Încălțăminte", "Alt tip de Încălțăminte"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        # fără rând dedicat în tabel – lăsăm impactul gol
    },
    ("Încălțăminte", "Cizme"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        "avg_weight_kg": Decimal("1.60"),
        "co2_avoided_kg": Decimal("40.00"),
        "trees_equivalent": Decimal("2.00"),
    },
    ("Încălțăminte", "Ghete / botine"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        "avg_weight_kg": Decimal("1.20"),
        "co2_avoided_kg": Decimal("30.00"),
        "trees_equivalent": Decimal("1.50"),
    },
    ("Încălțăminte", "Pantofi cu toc"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        "avg_weight_kg": Decimal("0.80"),
        "co2_avoided_kg": Decimal("20.00"),
        "trees_equivalent": Decimal("1.00"),
    },
    ("Încălțăminte", "Pantofi fără toc / loafers / balerini"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        "avg_weight_kg": Decimal("0.70"),
        "co2_avoided_kg": Decimal("17.50"),
        "trees_equivalent": Decimal("0.88"),
    },
    ("Încălțăminte", "Pantofi sport / sneakers"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        "avg_weight_kg": Decimal("0.90"),
        "co2_avoided_kg": Decimal("22.50"),
        "trees_equivalent": Decimal("1.13"),
    },
    ("Încălțăminte", "Sandale"): {
        "size_group": Category.SizeGroup.SHOES,
        "measurement_profile": Subcategory.MeasurementProfile.SHOES,
        "avg_weight_kg": Decimal("0.60"),
        "co2_avoided_kg": Decimal("15.00"),
        "trees_equivalent": Decimal("0.75"),
    },
}


def fix_subcategories():
    print("\n--- Fix Subcategories ---")

    for (cat_name, sub_name), cfg in SUBCATEGORY_CONFIG.items():
        # căutăm subcategoria rădăcină (fără parent)
        try:
            sub = Subcategory.objects.get(
                category__name=cat_name,
                name=sub_name,
                parent__isnull=True,
            )
            created = False
        except Subcategory.DoesNotExist:
            try:
                cat = Category.objects.get(name=cat_name)
            except Category.DoesNotExist:
                print(f"[WARN] Categoria '{cat_name}' nu există, sar peste '{sub_name}'")
                continue
            sub = Subcategory(category=cat, name=sub_name)
            created = True

        # slug dacă lipsește
        if not sub.slug:
            sub.slug = slugify(sub.name)

        # aplicăm configurarea
        for field, value in cfg.items():
            setattr(sub, field, value)

        sub.save()
        status = "CREATED" if created else "UPDATED"
        print(f"[Subcategory] {status}: {cat_name} / {sub_name}")

    print("\n--- Summary table (like admin) ---")
    for sub in (
        Subcategory.objects.select_related("category")
        .filter(parent__isnull=True)
        .order_by("category__name", "name")
    ):
        print(
            f"{sub.name:40} | {sub.category.name:12} | "
            f"gender={sub.get_gender_display() or '-':7} | "
            f"size_group={sub.get_effective_size_group():12} | "
            f"measure_profile={sub.get_measurement_profile_display() or '-':40} | "
            f"non_returnable={sub.is_non_returnable} | "
            f"avg_w={sub.avg_weight_kg} | co2={sub.co2_avoided_kg} | trees={sub.trees_equivalent}"
        )

    print("\nDone.\n")


if __name__ == "__main__":
    fix_subcategories()
