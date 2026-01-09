# core/context_processors.py
from .models import SiteSetting


def site_settings(request):
    """
    Injecteaza:
      - site_settings: mereu un obiect SiteSetting (fallback in-memory daca nu exista in DB)
      - canonical_url: URL absolut fara querystring
      - og/twitter defaults: ca sa nu crape template-ul daca nu sunt setate in view
    """
    obj = SiteSetting.objects.first()
    if obj is None:
        obj = SiteSetting()

    canonical_url = request.build_absolute_uri(request.path)

    # Defaults (pot fi override in view)
    meta_title = getattr(obj, "default_meta_title", "") or "Snobistic"
    meta_description = getattr(obj, "default_meta_description", "") or ""
    meta_robots = getattr(obj, "default_meta_robots", "") or "index, follow, max-snippet:-1, max-image-preview:large"

    return {
        "site_settings": obj,
        "canonical_url": canonical_url,

        # safe defaults (no VariableDoesNotExist)
        "og_title": None,
        "og_description": None,
        "og_image": None,
        "twitter_title": None,
        "twitter_description": None,
        "twitter_image": None,

        # optionally also provide meta defaults (safe)
        "meta_title_default": meta_title,
        "meta_description_default": meta_description,
        "meta_robots_default": meta_robots,
    }
