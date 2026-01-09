# accounts/tokens.py
from __future__ import annotations

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """
    Activation token hardening:
    - invalid after activation (is_active flip)
    - invalid after password change (password hash changes)
    - invalid after email change (email changes)
    """

    def _make_hash_value(self, user, timestamp):
        # email poate fi None în cazuri edge; normalizează safe
        email = (getattr(user, "email", "") or "").lower()
        password = getattr(user, "password", "") or ""
        is_active = getattr(user, "is_active", False)

        return f"{user.pk}{timestamp}{is_active}{password}{email}"


account_activation_token = AccountActivationTokenGenerator()
