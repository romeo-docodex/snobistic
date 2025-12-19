from django.db.models import Sum
from .utils import get_cart


def cart(request):
    cart_obj = get_cart(request)
    total_qty = 0
    if cart_obj:
        total_qty = cart_obj.items.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
    return {
        'cart': cart_obj,
        'cart_items_count': total_qty,
    }
