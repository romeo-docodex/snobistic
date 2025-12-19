from django import template
from catalog.models import Category, Product, Material

register = template.Library()


@register.simple_tag
def root_categories():
    """Returnează categoriile fără părinte"""
    return Category.objects.filter(parent__isnull=True)


@register.simple_tag
def size_choices():
    """Listează toate size choices din modelul Product"""
    return [choice[0] for choice in Product.SIZE_CHOICES]


@register.simple_tag
def material_choices():
    """
    Listează toate materialele definite în modelul Material.
    Poți itera în template cu:
      {% for m in material_choices %} {{ m.name }} {% endfor %}
    """
    return Material.objects.all()
