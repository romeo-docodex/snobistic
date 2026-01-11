# wallet/context_processors.py
from __future__ import annotations

from decimal import Decimal

from .services import get_or_create_wallet_for_user


def wallet_header(request):
    """
    Injectează soldul wallet-ului în contextul tuturor template-urilor (pentru header).
    Returnează doar suma (Decimal), fără currency.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    # opțional: dacă vrei DOAR pentru seller (ca în meniul tău)
    # if not getattr(request.user, "is_seller", False):
    #     return {}

    try:
        wallet = get_or_create_wallet_for_user(request.user)
        return {"header_wallet_balance": wallet.balance}
    except Exception:
        return {"header_wallet_balance": Decimal("0.00")}
