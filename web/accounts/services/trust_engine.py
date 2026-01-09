# accounts/services/trust_engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Model

from ..models import (
    SCORE_MAX as MODEL_SCORE_MAX,
    SCORE_MIN as MODEL_SCORE_MIN,
    CustomUser,
    Profile,
    SellerProfile,
    TrustScoreEvent,
)

# =============================================================================
# Settings-driven clamps (fallback to models)
# =============================================================================
SCORE_MIN = int(getattr(settings, "SNOBISTIC_TRUST_SCORE_MIN", MODEL_SCORE_MIN))
SCORE_MAX = int(getattr(settings, "SNOBISTIC_TRUST_SCORE_MAX", MODEL_SCORE_MAX))


def _clamp(value: int, minimum: int = SCORE_MIN, maximum: int = SCORE_MAX) -> int:
    try:
        v = int(value)
    except Exception:
        v = minimum
    return max(minimum, min(maximum, v))


def _has_db_field(obj: Any, field_name: str) -> bool:
    """
    True only if it's a REAL DB field (not a property).
    Safe even before migrations are applied.
    """
    try:
        obj._meta.get_field(field_name)  # type: ignore[attr-defined]
        return True
    except (FieldDoesNotExist, AttributeError):
        return False


def _safe_update_fields(obj: Any, wanted: list[str]) -> list[str]:
    return [f for f in wanted if _has_db_field(obj, f)]


def _save_with_fields(obj: Any, wanted_fields: list[str]) -> None:
    """
    ✅ PAS 4.1.3:
    If update_fields would be empty, call save() without update_fields.
    """
    fields = _safe_update_fields(obj, wanted_fields)
    if fields:
        obj.save(update_fields=fields)
    else:
        obj.save()


def _default_field_value(model_cls: type[Model], field_name: str, fallback: int = 0) -> int:
    """
    For commit=False "dry run real": if target row doesn't exist, we can still
    compute using model field default without creating anything.
    """
    try:
        f = model_cls._meta.get_field(field_name)
        default = f.default
        if callable(default):
            default = default()
        return int(default)
    except Exception:
        return int(fallback)


def _ref_to_ct_and_id(ref: Optional[Model]) -> Tuple[Optional[ContentType], Optional[str]]:
    if not ref or not getattr(ref, "pk", None):
        return None, None
    try:
        return ContentType.objects.get_for_model(ref.__class__), str(ref.pk)
    except Exception:
        return None, None


@dataclass(frozen=True)
class TrustApplyResult:
    created: bool
    event: Optional[TrustScoreEvent]
    score_before: int
    score_after: int


# =============================================================================
# Core engine
# =============================================================================
@transaction.atomic
def apply_trust_event(
    *,
    user: CustomUser,
    subject: str,
    delta: int,
    reason: str,
    ref: Optional[Model] = None,
    source_app: str = "",
    source_event_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> TrustApplyResult:
    """
    ✅ PAS 4.1 requirements

    1) Idempotency safe (release blocker):
       - lock target row with select_for_update()
       - attempt to create TrustScoreEvent (get_or_create on unique)
       - ONLY if created: apply delta and persist score
       - if exists already: return existing (no side-effects)

    2) commit=False = dry run real:
       - DO NOT create missing Profile/SellerProfile
       - return "cannot compute" or compute using defaults without persisting

    3) _safe_update_fields:
       - if empty -> save() without update_fields
    """
    if not user or not getattr(user, "pk", None):
        return TrustApplyResult(created=False, event=None, score_before=0, score_after=0)

    subject = (subject or "").upper().strip()
    if subject not in (TrustScoreEvent.SUBJECT_BUYER, TrustScoreEvent.SUBJECT_SELLER):
        raise ValueError("Invalid subject for trust event.")

    reason = (reason or "").upper().strip()
    delta = int(delta or 0)

    src_app = (source_app or "").strip()
    src_id = (source_event_id or "").strip()
    meta = metadata if isinstance(metadata, dict) else {}

    # -------------------------------------------------------------------------
    # commit=False: DRY RUN (no row creation, no event creation)
    # -------------------------------------------------------------------------
    if not commit:
        if subject == TrustScoreEvent.SUBJECT_BUYER:
            prof = Profile.objects.filter(user=user).only("buyer_trust_score").first()
            before = int(prof.buyer_trust_score) if prof else _default_field_value(Profile, "buyer_trust_score", 0)
            after = _clamp(before + delta)
            return TrustApplyResult(created=False, event=None, score_before=before, score_after=after)

        seller = SellerProfile.objects.filter(user=user).only("seller_trust_score").first()
        before = (
            int(seller.seller_trust_score) if seller else _default_field_value(SellerProfile, "seller_trust_score", 0)
        )
        after = _clamp(before + delta)
        return TrustApplyResult(created=False, event=None, score_before=before, score_after=after)

    # -------------------------------------------------------------------------
    # commit=True: REAL APPLY (idempotent + atomic)
    # -------------------------------------------------------------------------
    # 1) Lock target row (select_for_update)
    if subject == TrustScoreEvent.SUBJECT_BUYER:
        target, _ = Profile.objects.select_for_update().get_or_create(user=user)
        score_field = "buyer_trust_score"
    else:
        target, _ = SellerProfile.objects.select_for_update().get_or_create(user=user)
        score_field = "seller_trust_score"

    before = int(getattr(target, score_field, 0) or 0)
    after = _clamp(before + delta)

    ct, oid = _ref_to_ct_and_id(ref)

    # 2) Try create event FIRST; only if created -> update score
    if src_app and src_id:
        event, created = TrustScoreEvent.objects.get_or_create(
            source_app=src_app,
            source_event_id=src_id,
            defaults={
                "user": user,
                "subject": subject,
                "delta": delta,
                "score_before": _clamp(before),
                "score_after": after,
                "reason": reason,
                "ref_content_type": ct,
                "ref_object_id": oid,
                "metadata": meta,
            },
        )
        if not created:
            return TrustApplyResult(
                created=False,
                event=event,
                score_before=int(event.score_before or 0),
                score_after=int(event.score_after or 0),
            )
    else:
        # No idempotency key => always create a new event
        event = TrustScoreEvent.objects.create(
            user=user,
            subject=subject,
            delta=delta,
            score_before=_clamp(before),
            score_after=after,
            reason=reason,
            ref_content_type=ct,
            ref_object_id=oid,
            source_app=src_app,
            source_event_id=src_id,
            metadata=meta,
        )
        created = True

    # 3) Apply delta ONLY if event was created
    if created:
        setattr(target, score_field, after)
        _save_with_fields(target, [score_field])

    return TrustApplyResult(created=True, event=event, score_before=before, score_after=after)


# =============================================================================
# Convenience wrappers
# =============================================================================
def buyer_trust_event(
    *,
    user: CustomUser,
    delta: int,
    reason: str,
    ref: Optional[Model] = None,
    source_app: str = "",
    source_event_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> TrustApplyResult:
    return apply_trust_event(
        user=user,
        subject=TrustScoreEvent.SUBJECT_BUYER,
        delta=delta,
        reason=reason,
        ref=ref,
        source_app=source_app,
        source_event_id=source_event_id,
        metadata=metadata,
        commit=commit,
    )


def seller_trust_event(
    *,
    user: CustomUser,
    delta: int,
    reason: str,
    ref: Optional[Model] = None,
    source_app: str = "",
    source_event_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> TrustApplyResult:
    return apply_trust_event(
        user=user,
        subject=TrustScoreEvent.SUBJECT_SELLER,
        delta=delta,
        reason=reason,
        ref=ref,
        source_app=source_app,
        source_event_id=source_event_id,
        metadata=metadata,
        commit=commit,
    )
