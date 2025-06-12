import string
import random
from django.utils.text import slugify
from django.db.models import Model


def unique_slugify(text, model: type[Model], slug_field: str = "slug", instance: Model = None, max_length=50):
    """
    Creează un slug unic pentru orice model, similar cu django-autoslug.
    """
    slug_base = slugify(text)[:max_length]
    slug = slug_base
    counter = 1

    ModelClass = model
    if instance is not None:
        existing = ModelClass.objects.filter(**{slug_field: slug}).exclude(pk=instance.pk)
    else:
        existing = ModelClass.objects.filter(**{slug_field: slug})

    while existing.exists():
        suffix = f"-{counter}"
        slug = f"{slug_base[:max_length - len(suffix)]}{suffix}"
        counter += 1
        existing = ModelClass.objects.filter(**{slug_field: slug})

    return slug
