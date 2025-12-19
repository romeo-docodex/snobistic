# logistics/services/curiera.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import requests
from django.conf import settings


@dataclass
class CurieraShipmentResult:
    success: bool
    tracking_number: Optional[str] = None
    external_id: Optional[str] = None
    tracking_url: Optional[str] = None
    label_url: Optional[str] = None
    error_message: Optional[str] = None


def create_shipment_for_order(order, seller, *, weight_kg: Decimal,
                              service_name: str,
                              cash_on_delivery: bool,
                              cod_amount: Decimal) -> CurieraShipmentResult:
    """
    Creează o expediere în API-ul Curiera pentru comanda dată.

    Aici VA TREBUI să mapezi structura reală de la Curiera (endpoint, payload, headers).
    Eu pun doar un exemplu generic cu un endpoint imaginar /api/shipments.
    """
    base_url = getattr(settings, "CURIERA_API_BASE_URL", "")
    api_key = getattr(settings, "CURIERA_API_KEY", "")

    if not base_url or not api_key:
        return CurieraShipmentResult(
            success=False,
            error_message="Configurația Curiera lipsește (API base URL sau API KEY).",
        )

    # presupunem că Order are câmpuri shipping_name, shipping_phone, shipping_city, etc.
    payload = {
        "reference": f"SNB-ORDER-{order.id}",
        "sender": {
            "name": getattr(seller, "get_full_name", lambda: seller.email)(),
            "phone": getattr(seller.profile, "phone", ""),
            "city": getattr(seller.profile, "city", ""),
            "address": getattr(seller.profile, "address", ""),
        },
        "recipient": {
            "name": getattr(order, "shipping_name", order.buyer.get_full_name())
            or order.buyer.email,
            "phone": getattr(order, "shipping_phone", ""),
            "city": getattr(order, "shipping_city", ""),
            "address": getattr(order, "shipping_address", ""),
        },
        "parcels": [
            {
                "weight": float(weight_kg),
            }
        ],
        "service": service_name or "Standard",
        "cod": {
            "enabled": cash_on_delivery,
            "amount": float(cod_amount) if cash_on_delivery else 0.0,
            "currency": getattr(settings, "SNOBISTIC_CURRENCY", "RON"),
        },
    }

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/shipments",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        return CurieraShipmentResult(
            success=False,
            error_message=f"Eroare de rețea către Curiera: {exc}",
        )

    if response.status_code >= 400:
        return CurieraShipmentResult(
            success=False,
            error_message=f"Eroare Curiera ({response.status_code}): {response.text}",
        )

    data = response.json()  # structurează după contractul real

    # Exemplu generic – adaptezi key-urile după documentația lor reală
    return CurieraShipmentResult(
        success=True,
        tracking_number=data.get("awb") or data.get("tracking_number"),
        external_id=str(data.get("id") or ""),
        tracking_url=data.get("tracking_url") or "",
        label_url=data.get("label_url") or "",
    )
