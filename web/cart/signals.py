from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import CartItem

@receiver(user_logged_in)
def merge_cart_on_login(sender, user, request, **kwargs):
    session_key = request.session.session_key
    if not session_key:
        return
    anon_items = CartItem.objects.filter(session_key=session_key)
    for anon in anon_items:
        obj, created = CartItem.objects.get_or_create(
            user=user,
            product=anon.product,
            defaults={'quantity': anon.quantity}
        )
        if not created:
            obj.quantity += anon.quantity
            obj.save()
    anon_items.delete()
