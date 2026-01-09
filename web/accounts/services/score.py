# accounts/services/score.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction

from ..models import (
    SCORE_MAX as MODEL_SCORE_MAX,
    SCORE_MIN as MODEL_SCORE_MIN,
    SELLER_COMMISSION_BY_TIER as MODEL_SELLER_COMMISSION_BY_TIER,
    SELLER_TIER_THRESHOLDS_NET_RON as MODEL_SELLER_THRESHOLDS_NET_RON,
    TRUST_A_MIN as MODEL_TRUST_A_MIN,
    TRUST_B_MIN as MODEL_TRUST_B_MIN,
    TRUST_C_MIN as MODEL_TRUST_C_MIN,
    Profile,
    SellerProfile,
    TrustScoreEvent,
)
from .trust_engine import buyer_trust_event, seller_trust_event

# =============================================================================
# Buyer/Seller score clamps (settings-driven; fallback to models)
# =============================================================================
BUYER_SCORE_MIN = int(getattr(settings, "SNOBISTIC_TRUST_SCORE_MIN", MODEL_SCORE_MIN))
BUYER_SCORE_MAX = int(getattr(settings, "SNOBISTIC_TRUST_SCORE_MAX", MODEL_SCORE_MAX))
SELLER_SCORE_MIN = int(getattr(settings, "SNOBISTIC_TRUST_SCORE_MIN", MODEL_SCORE_MIN))
SELLER_SCORE_MAX = int(getattr(settings, "SNOBISTIC_TRUST_SCORE_MAX", MODEL_SCORE_MAX))

# Trust class thresholds (settings-driven; fallback to models single truth)
TRUST_A_MIN = int(getattr(settings, "SNOBISTIC_TRUST_A_MIN", MODEL_TRUST_A_MIN))
TRUST_B_MIN = int(getattr(settings, "SNOBISTIC_TRUST_B_MIN", MODEL_TRUST_B_MIN))
TRUST_C_MIN = int(getattr(settings, "SNOBISTIC_TRUST_C_MIN", MODEL_TRUST_C_MIN))


def _clamp(value, minimum: int, maximum: int) -> int:
    try:
        value = int(value)
    except Exception:
        value = minimum
    return max(minimum, min(maximum, value))


def _has_db_field(obj, field_name: str) -> bool:
    """
    True only if it's a REAL DB field (not a property).
    Safe to call even before migrations are applied.
    """
    try:
        obj._meta.get_field(field_name)  # type: ignore[attr-defined]
        return True
    except (FieldDoesNotExist, AttributeError):
        return False


def _safe_update_fields(obj, wanted: list[str]) -> list[str]:
    return [f for f in wanted if _has_db_field(obj, f)]


def _save_with_fields(obj, wanted_fields: list[str]) -> None:
    """
    ✅ PAS 4.1.3: if update_fields ends up empty, call save() without update_fields.
    """
    fields = _safe_update_fields(obj, wanted_fields)
    if fields:
        obj.save(update_fields=fields)
    else:
        obj.save()


# =============================================================================
# Weights (helpers only)
# =============================================================================
@dataclass(frozen=True)
class BuyerEventWeights:
    order_paid: int = 2
    order_completed: int = 1
    good_history_bonus: int = 1

    cancel_buyer_fault: int = -5
    return_buyer_fault: int = -3
    dispute_lost: int = -8
    chargeback: int = -15

    kyc_approved_bonus: int = 5
    twofa_enabled_bonus: int = 3


DEFAULT_BUYER_WEIGHTS = BuyerEventWeights()


@dataclass(frozen=True)
class SellerEventWeights:
    order_paid: int = 1
    order_shipped_on_time: int = 2
    order_completed_ok: int = 1

    late_shipment: int = -3
    cancel_seller_fault: int = -5
    return_seller_fault: int = -6
    dispute_lost: int = -10
    severe_incident: int = -20

    kyc_approved_bonus: int = 5
    twofa_enabled_bonus: int = 3


DEFAULT_SELLER_WEIGHTS = SellerEventWeights()


# =============================================================================
# Trust class helpers
# =============================================================================
def buyer_trust_class_from_score(score: int) -> str:
    score = int(score or 0)
    if score >= TRUST_A_MIN:
        return "A"
    if score >= TRUST_B_MIN:
        return "B"
    if score >= TRUST_C_MIN:
        return "C"
    return "D"


def seller_trust_class_from_score(score: int) -> str:
    return buyer_trust_class_from_score(score)


# =============================================================================
# Score application helpers (NO direct writes; always via trust_engine)
# =============================================================================
def apply_buyer_delta(
    profile: Profile,
    delta: int,
    *,
    reason: str = TrustScoreEvent.REASON_MANUAL_ADJUST,
    source_app: str = "",
    source_event_id: str = "",
    commit: bool = True,
    metadata: Optional[dict] = None,
) -> int:
    res = buyer_trust_event(
        user=profile.user,
        delta=int(delta or 0),
        reason=reason,
        source_app=source_app,
        source_event_id=source_event_id,
        metadata=metadata or {},
        commit=commit,
    )
    return int(res.score_after or 0)


def apply_seller_delta(
    seller: SellerProfile,
    delta: int,
    *,
    reason: str = TrustScoreEvent.REASON_MANUAL_ADJUST,
    source_app: str = "",
    source_event_id: str = "",
    commit: bool = True,
    metadata: Optional[dict] = None,
) -> int:
    res = seller_trust_event(
        user=seller.user,
        delta=int(delta or 0),
        reason=reason,
        source_app=source_app,
        source_event_id=source_event_id,
        metadata=metadata or {},
        commit=commit,
    )
    return int(res.score_after or 0)


# =============================================================================
# Buyer events (wrappers; still accept optional idempotency keys)
# =============================================================================
def on_buyer_order_paid(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_buyer_delta(
        profile,
        weights.order_paid,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "buyer", "event": "order_paid"},
    )


def on_buyer_order_completed_ok(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_buyer_delta(
        profile,
        weights.order_completed,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "buyer", "event": "order_completed_ok"},
    )


def on_buyer_cancel_buyer_fault(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_buyer_delta(
        profile,
        weights.cancel_buyer_fault,
        reason=TrustScoreEvent.REASON_ORDER_CANCELLED,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "buyer", "event": "cancel_buyer_fault"},
    )


def on_buyer_return_buyer_fault(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_buyer_delta(
        profile,
        weights.return_buyer_fault,
        reason=TrustScoreEvent.REASON_RETURN_ABUSE,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "buyer", "event": "return_buyer_fault"},
    )


def on_buyer_dispute_lost(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_buyer_delta(
        profile,
        weights.dispute_lost,
        reason=TrustScoreEvent.REASON_DISPUTE_LOST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "buyer", "event": "dispute_lost"},
    )


def on_buyer_chargeback(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_buyer_delta(
        profile,
        weights.chargeback,
        reason=TrustScoreEvent.REASON_CHARGEBACK,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "buyer", "event": "chargeback"},
    )


# =============================================================================
# Seller events (wrappers; optional idempotency keys)
# =============================================================================
def on_seller_order_paid(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.order_paid,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "order_paid"},
    )


def on_seller_order_shipped_on_time(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.order_shipped_on_time,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "shipped_on_time"},
    )


def on_seller_order_completed_ok(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.order_completed_ok,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "order_completed_ok"},
    )


def on_seller_late_shipment(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.late_shipment,
        reason=TrustScoreEvent.REASON_LATE_SHIPMENT,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "late_shipment"},
    )


def on_seller_cancel_seller_fault(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.cancel_seller_fault,
        reason=TrustScoreEvent.REASON_ORDER_CANCELLED,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "cancel_seller_fault"},
    )


def on_seller_return_seller_fault(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.return_seller_fault,
        reason=TrustScoreEvent.REASON_REFUND_ISSUED,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "return_seller_fault"},
    )


def on_seller_dispute_lost(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.dispute_lost,
        reason=TrustScoreEvent.REASON_DISPUTE_LOST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "dispute_lost"},
    )


def on_seller_severe_incident(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "",
    source_event_id: str = "",
) -> int:
    return apply_seller_delta(
        seller,
        weights.severe_incident,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id=source_event_id,
        commit=commit,
        metadata={"kind": "seller", "event": "severe_incident"},
    )


# =============================================================================
# Identity bonuses sync (via trust_engine; no direct score writes)
# =============================================================================
@transaction.atomic
def sync_buyer_identity_bonuses(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
    source_app: str = "accounts",
) -> int:
    """
    Idempotent via:
      - flags on Profile: buyer_bonus_kyc_applied / buyer_bonus_2fa_applied
      - trust_engine idempotency keys per transition (apply/revoke)

    commit=False:
      - computes best-effort "after" without persisting (trust_engine does not create missing rows)
    """
    kyc_now = (getattr(profile, "kyc_status", None) == "APPROVED")
    twofa_now = bool(getattr(profile, "two_factor_enabled", False))

    delta_total = 0

    # --- KYC bonus
    if _has_db_field(profile, "buyer_bonus_kyc_applied"):
        kyc_applied = bool(getattr(profile, "buyer_bonus_kyc_applied", False))
        if kyc_now and not kyc_applied:
            delta_total += weights.kyc_approved_bonus
            if commit:
                res = buyer_trust_event(
                    user=profile.user,
                    delta=weights.kyc_approved_bonus,
                    reason=TrustScoreEvent.REASON_KYC_APPROVED,
                    source_app=source_app,
                    source_event_id=f"buyer_bonus_kyc:on:{profile.user_id}",
                    metadata={"kind": "bonus", "bonus": "kyc", "state": "on"},
                    commit=True,
                )
                # converge flag to truth
                profile.buyer_bonus_kyc_applied = True
                _save_with_fields(profile, ["buyer_bonus_kyc_applied"])
                return int(res.score_after or 0)

        elif (not kyc_now) and kyc_applied:
            delta_total -= weights.kyc_approved_bonus
            if commit:
                res = buyer_trust_event(
                    user=profile.user,
                    delta=-weights.kyc_approved_bonus,
                    reason=TrustScoreEvent.REASON_KYC_REJECTED,
                    source_app=source_app,
                    source_event_id=f"buyer_bonus_kyc:off:{profile.user_id}",
                    metadata={"kind": "bonus", "bonus": "kyc", "state": "off"},
                    commit=True,
                )
                profile.buyer_bonus_kyc_applied = False
                _save_with_fields(profile, ["buyer_bonus_kyc_applied"])
                return int(res.score_after or 0)

    # --- 2FA bonus
    if _has_db_field(profile, "buyer_bonus_2fa_applied"):
        twofa_applied = bool(getattr(profile, "buyer_bonus_2fa_applied", False))
        if twofa_now and not twofa_applied:
            delta_total += weights.twofa_enabled_bonus
            if commit:
                res = buyer_trust_event(
                    user=profile.user,
                    delta=weights.twofa_enabled_bonus,
                    reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
                    source_app=source_app,
                    source_event_id=f"buyer_bonus_2fa:on:{profile.user_id}",
                    metadata={"kind": "bonus", "bonus": "2fa", "state": "on"},
                    commit=True,
                )
                profile.buyer_bonus_2fa_applied = True
                _save_with_fields(profile, ["buyer_bonus_2fa_applied"])
                return int(res.score_after or 0)

        elif (not twofa_now) and twofa_applied:
            delta_total -= weights.twofa_enabled_bonus
            if commit:
                res = buyer_trust_event(
                    user=profile.user,
                    delta=-weights.twofa_enabled_bonus,
                    reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
                    source_app=source_app,
                    source_event_id=f"buyer_bonus_2fa:off:{profile.user_id}",
                    metadata={"kind": "bonus", "bonus": "2fa", "state": "off"},
                    commit=True,
                )
                profile.buyer_bonus_2fa_applied = False
                _save_with_fields(profile, ["buyer_bonus_2fa_applied"])
                return int(res.score_after or 0)

    # If nothing changed, still return current/after (dry-run safe)
    res = buyer_trust_event(
        user=profile.user,
        delta=delta_total,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id="",  # dry-run path doesn't create anything anyway
        metadata={"kind": "sync", "what": "buyer_identity_bonuses"},
        commit=commit,
    )
    return int(res.score_after or 0)


@transaction.atomic
def sync_seller_identity_bonuses(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
    source_app: str = "accounts",
) -> int:
    """
    Similar to buyer, but flags live on SellerProfile:
      - seller_bonus_kyc_applied / seller_bonus_2fa_applied
    KYC/2FA truth comes from Profile.
    """
    prof = getattr(seller.user, "profile", None)
    if prof is None:
        if not commit:
            # dry run: cannot create Profile
            res = seller_trust_event(
                user=seller.user,
                delta=0,
                reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
                commit=False,
            )
            return int(res.score_after or 0)
        # commit=True: Profile should exist normally via signals, but keep robust
        prof = Profile.objects.select_for_update().get(user=seller.user)

    kyc_now = (getattr(prof, "kyc_status", None) == "APPROVED")
    twofa_now = bool(getattr(prof, "two_factor_enabled", False))

    delta_total = 0

    if _has_db_field(seller, "seller_bonus_kyc_applied"):
        kyc_applied = bool(getattr(seller, "seller_bonus_kyc_applied", False))
        if kyc_now and not kyc_applied:
            delta_total += weights.kyc_approved_bonus
            if commit:
                res = seller_trust_event(
                    user=seller.user,
                    delta=weights.kyc_approved_bonus,
                    reason=TrustScoreEvent.REASON_KYC_APPROVED,
                    source_app=source_app,
                    source_event_id=f"seller_bonus_kyc:on:{seller.user_id}",
                    metadata={"kind": "bonus", "bonus": "kyc", "state": "on"},
                    commit=True,
                )
                seller.seller_bonus_kyc_applied = True
                _save_with_fields(seller, ["seller_bonus_kyc_applied"])
                return int(res.score_after or 0)

        elif (not kyc_now) and kyc_applied:
            delta_total -= weights.kyc_approved_bonus
            if commit:
                res = seller_trust_event(
                    user=seller.user,
                    delta=-weights.kyc_approved_bonus,
                    reason=TrustScoreEvent.REASON_KYC_REJECTED,
                    source_app=source_app,
                    source_event_id=f"seller_bonus_kyc:off:{seller.user_id}",
                    metadata={"kind": "bonus", "bonus": "kyc", "state": "off"},
                    commit=True,
                )
                seller.seller_bonus_kyc_applied = False
                _save_with_fields(seller, ["seller_bonus_kyc_applied"])
                return int(res.score_after or 0)

    if _has_db_field(seller, "seller_bonus_2fa_applied"):
        twofa_applied = bool(getattr(seller, "seller_bonus_2fa_applied", False))
        if twofa_now and not twofa_applied:
            delta_total += weights.twofa_enabled_bonus
            if commit:
                res = seller_trust_event(
                    user=seller.user,
                    delta=weights.twofa_enabled_bonus,
                    reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
                    source_app=source_app,
                    source_event_id=f"seller_bonus_2fa:on:{seller.user_id}",
                    metadata={"kind": "bonus", "bonus": "2fa", "state": "on"},
                    commit=True,
                )
                seller.seller_bonus_2fa_applied = True
                _save_with_fields(seller, ["seller_bonus_2fa_applied"])
                return int(res.score_after or 0)

        elif (not twofa_now) and twofa_applied:
            delta_total -= weights.twofa_enabled_bonus
            if commit:
                res = seller_trust_event(
                    user=seller.user,
                    delta=-weights.twofa_enabled_bonus,
                    reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
                    source_app=source_app,
                    source_event_id=f"seller_bonus_2fa:off:{seller.user_id}",
                    metadata={"kind": "bonus", "bonus": "2fa", "state": "off"},
                    commit=True,
                )
                seller.seller_bonus_2fa_applied = False
                _save_with_fields(seller, ["seller_bonus_2fa_applied"])
                return int(res.score_after or 0)

    res = seller_trust_event(
        user=seller.user,
        delta=delta_total,
        reason=TrustScoreEvent.REASON_MANUAL_ADJUST,
        source_app=source_app,
        source_event_id="",
        metadata={"kind": "sync", "what": "seller_identity_bonuses"},
        commit=commit,
    )
    return int(res.score_after or 0)


# =============================================================================
# Seller level/commission progression (settings-driven, fallback to models)
# =============================================================================
def _get_seller_thresholds() -> Dict[str, Decimal]:
    default = {
        "AMATOR": Decimal(MODEL_SELLER_THRESHOLDS_NET_RON.get("AMATOR", Decimal("0"))),
        "RISING": Decimal(MODEL_SELLER_THRESHOLDS_NET_RON.get("RISING", Decimal("3000"))),
        "TOP": Decimal(MODEL_SELLER_THRESHOLDS_NET_RON.get("TOP", Decimal("15000"))),
        "VIP": Decimal(MODEL_SELLER_THRESHOLDS_NET_RON.get("VIP", Decimal("50000"))),
    }
    raw = getattr(settings, "SNOBISTIC_SELLER_THRESHOLDS", None)
    if not isinstance(raw, dict):
        return default

    out: Dict[str, Decimal] = {}
    for k, v in raw.items():
        try:
            out[str(k).upper()] = Decimal(v)
        except Exception:
            pass

    return {**default, **out}


def _get_commission_rates() -> Dict[str, Decimal]:
    default = {
        "AMATOR": Decimal(MODEL_SELLER_COMMISSION_BY_TIER.get("AMATOR", Decimal("9.00"))),
        "RISING": Decimal(MODEL_SELLER_COMMISSION_BY_TIER.get("RISING", Decimal("8.00"))),
        "TOP": Decimal(MODEL_SELLER_COMMISSION_BY_TIER.get("TOP", Decimal("7.00"))),
        "VIP": Decimal(MODEL_SELLER_COMMISSION_BY_TIER.get("VIP", Decimal("6.00"))),
    }
    raw = getattr(settings, "SNOBISTIC_COMMISSION_RATES", None)
    if not isinstance(raw, dict):
        return default

    out: Dict[str, Decimal] = {}
    for k, v in raw.items():
        try:
            out[str(k).upper()] = Decimal(v)
        except Exception:
            pass

    return {**default, **out}


def _tier_for_sales(volume: Decimal, thresholds: Dict[str, Decimal]) -> str:
    volume = Decimal(volume or "0")
    if volume >= thresholds["VIP"]:
        return "VIP"
    if volume >= thresholds["TOP"]:
        return "TOP"
    if volume >= thresholds["RISING"]:
        return "RISING"
    return "AMATOR"


@transaction.atomic
def register_seller_sale(
    seller: SellerProfile,
    net_amount: Decimal,
    *,
    commit: bool = True,
) -> SellerProfile:
    """
    Atomic: locks SellerProfile row, updates lifetime_sales_net, recomputes tier+commission.
    Not a trust-score write; safe to persist directly.
    """
    if net_amount is None:
        return seller
    try:
        net_amount = Decimal(net_amount)
    except Exception:
        return seller
    if net_amount <= 0:
        return seller

    locked = SellerProfile.objects.select_for_update().get(pk=seller.pk)
    locked.lifetime_sales_net = (locked.lifetime_sales_net or Decimal("0")) + net_amount

    thresholds = _get_seller_thresholds()
    commissions = _get_commission_rates()

    tier = _tier_for_sales(locked.lifetime_sales_net, thresholds)
    locked.seller_level = tier
    locked.seller_commission_rate = commissions.get(tier, Decimal("9.00"))

    if commit:
        _save_with_fields(locked, ["lifetime_sales_net", "seller_level", "seller_commission_rate"])

    seller.lifetime_sales_net = locked.lifetime_sales_net
    seller.seller_level = locked.seller_level
    seller.seller_commission_rate = locked.seller_commission_rate
    return seller


# =============================================================================
# Public constants for other apps (e.g., dashboard/views.py imports)
# =============================================================================
SELLER_THRESHOLDS: Dict[str, Decimal] = _get_seller_thresholds()
SELLER_COMMISSIONS: Dict[str, Decimal] = _get_commission_rates()

AMATOR_THRESHOLD: Decimal = SELLER_THRESHOLDS["AMATOR"]
RISING_THRESHOLD: Decimal = SELLER_THRESHOLDS["RISING"]
TOP_THRESHOLD: Decimal = SELLER_THRESHOLDS["TOP"]
VIP_THRESHOLD: Decimal = SELLER_THRESHOLDS["VIP"]
