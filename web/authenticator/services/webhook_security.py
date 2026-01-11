# authenticator/services/webhook_security.py
from __future__ import annotations

import hmac
import hashlib


def verify_hmac_signature(*, secret: str, body: bytes, signature: str) -> bool:
    """
    signature: hex digest (de ex "sha256=...") sau doar hex
    """
    if not secret:
        return False

    signature = (signature or "").strip()
    if signature.startswith("sha256="):
        signature = signature.split("=", 1)[1].strip()

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
