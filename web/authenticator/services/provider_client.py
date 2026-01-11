# authenticator/services/provider_client.py
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from django.conf import settings

from authenticator.models import AuthRequest


class ProviderError(Exception):
    pass


def is_configured() -> bool:
    return bool(getattr(settings, "AUTH_PROVIDER_BASE_URL", "") and getattr(settings, "AUTH_PROVIDER_API_KEY", ""))


def submit_auth_request(req: AuthRequest) -> str:
    """
    Trimite cererea către provider.
    Returnează provider_reference.

    - dacă nu e configurat provider-ul, facem fallback: simulăm "sent" (ca să ruleze flow-ul),
      iar tu poți procesa manual din Admin sau prin webhook test.
    """
    if not is_configured():
        # fallback safe: "pretend sent" so the rest of the system works end-to-end
        provider_reference = f"LOCAL-{uuid.uuid4().hex[:16]}"
        req.mark_sent(provider="local_stub", provider_reference=provider_reference, payload={"stub": True})
        req.save(update_fields=["status", "provider", "provider_reference", "sent_at", "provider_payload"])
        return provider_reference

    base_url = settings.AUTH_PROVIDER_BASE_URL.rstrip("/")
    api_key = settings.AUTH_PROVIDER_API_KEY
    endpoint = f"{base_url}/auth/requests"

    # Build payload. Adjust to real provider contract.
    payload: Dict[str, Any] = {
        "brand": req.brand_text,
        "model": req.model_text,
        "serial_number": req.serial_number,
        "notes": req.notes,
        "contact_email": req.contact_email,
        "callback_url": getattr(settings, "AUTH_PROVIDER_WEBHOOK_CALLBACK_URL", ""),  # optional
        "metadata": {
            "snobistic_auth_request_id": req.pk,
            "product_id": req.product_id,
        },
    }

    # For image upload: depends on provider (multipart, presigned URLs, etc.)
    # Here we send just metadata and assume images are handled separately, OR provider accepts URLs.
    # If provider requires images in this call, adapt to multipart with requests.

    try:
        import requests  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ProviderError("Lipsește pachetul 'requests' pentru integrarea provider-ului.") from e

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        r = requests.post(endpoint, json=payload, headers=headers, timeout=25)
        r.raise_for_status()
        data = r.json() if r.content else {}
    except Exception as e:
        raise ProviderError(f"Eroare la trimiterea către provider: {e}") from e

    provider_reference = str(data.get("id") or data.get("reference") or "").strip()
    if not provider_reference:
        raise ProviderError("Provider-ul nu a returnat un provider_reference valid.")

    req.mark_sent(provider="external_provider", provider_reference=provider_reference, payload=data)
    req.save(update_fields=["status", "provider", "provider_reference", "sent_at", "provider_payload"])
    return provider_reference


def apply_result_to_product(req: AuthRequest) -> None:
    """
    Dacă cererea este legată de un produs, sincronizează ProductAuthentication.
    """
    if not req.product_id:
        return

    from authenticator.models import ProductAuthentication  # local import to avoid cycles

    obj, _created = ProductAuthentication.objects.get_or_create(product_id=req.product_id)
    obj.apply_from_request(req)
    obj.save()
