# catalog/context_processors.py
from .views import _get_session_favorites
from .models import Category


def favorites_badge(request):
    try:
        if getattr(request, "user", None) and request.user.is_authenticated:
            from .models import Favorite

            return {
                "favorites_count": Favorite.objects.filter(
                    user=request.user
                ).count()
            }
        return {"favorites_count": len(_get_session_favorites(request))}
    except Exception:
        return {"favorites_count": 0}


def mega_menu_categories(request):
    """
    Construiește listele de categorii pentru mega-menu,
    pe baza produselor existente în DB.

    - nav_categories_men   -> categorii care au cel puțin un Product cu gender='M'
    - nav_categories_women -> categorii care au cel puțin un Product cu gender='F'
    """

    # Bărbați
    men_categories = (
        Category.objects
        .filter(
            products__gender="M",
            products__is_active=True,
        )
        .prefetch_related("subcategories")
        .order_by("name")
        .distinct()
    )

    # Femei
    women_categories = (
        Category.objects
        .filter(
            products__gender="F",
            products__is_active=True,
        )
        .prefetch_related("subcategories")
        .order_by("name")
        .distinct()
    )

    return {
        "nav_categories_men": men_categories,
        "nav_categories_women": women_categories,
    }
