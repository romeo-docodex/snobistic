"""
Logica de merge între coșul de guest și coșul de user este
gestionată central în accounts.signals.on_user_logged_in,
care apelează cart.utils.merge_session_cart_to_user.

Fișierul de signals al aplicației cart este lăsat intenționat
minimal pentru a evita dublarea logicii de merge.
"""
