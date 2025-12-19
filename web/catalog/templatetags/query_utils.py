from django import template
from urllib.parse import urlencode


register = template.Library()

@register.simple_tag
def update_query_params(request, reset_page=True, **kwargs):
    """
    Return encoded URL parameters by updating/removing values.
    Set reset_page=False dacă nu vrei să scoți 'page'.
    Usage:
    {% update_query_params request sort='a-z' %}
    {% update_query_params request sort=None page=None %}
    """
    updated = request.GET.copy()

    # remove 'page' dacă schimbi sortarea sau filtrele
    if reset_page:
        updated.pop('page', None)

    for key, value in kwargs.items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = value

    return '?' + updated.urlencode()

@register.simple_tag
def toggle_query_param(request, param, value):
    query_params = request.GET.copy()
    values = query_params.getlist(param)

    if value in values:
        values.remove(value)
    else:
        values.append(value)

    query_params.setlist(param, values)
    return '?' + urlencode(query_params, doseq=True)