# wallet/context_processors.py
from __future__ import annotations

from decimal import Decimal

from .services import get_or_create_wallet_for_user_readonly


def wallet_header(request):
    """
    Injectează soldul wallet-ului în contextul tuturor template-urilor (pentru header).
    IMPORTANT: folosește read-only helper (fără select_for_update).
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    try:
        wallet = get_or_create_wallet_for_user_readonly(request.user)
        return {"header_wallet_balance": wallet.balance}
    except Exception:
        return {"header_wallet_balance": Decimal("0.00")}
