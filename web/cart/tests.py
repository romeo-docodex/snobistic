from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from .models import Cart, CartItem

@receiver(user_logged_in)
def merge_carts(sender, request, user, **kwargs):
    """
    When a user logs in, merge any session cart into the user's cart.
    """
    s_key = request.session.session_key
    if not s_key:
        return

    guest_cart = Cart.objects.filter(session_key=s_key, user__isnull=True).first()
    if not guest_cart:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)
    for item in guest_cart.items.select_related('product'):
        dst, created = CartItem.objects.get_or_create(
            cart=user_cart,
            product=item.product,
            defaults={'quantity': item.quantity}
        )
        if not created:
            dst.quantity += item.quantity
            dst.save()

    guest_cart.delete()
