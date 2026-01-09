# cart/context_processors.py
from .utils import get_cart


def cart(request):
    cart_obj = get_cart(request)
    count = cart_obj.items.count() if cart_obj else 0
    return {
        "cart": cart_obj,
        "cart_items_count": count,
    }
