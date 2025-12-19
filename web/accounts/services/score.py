# accounts/services/score.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from ..models import Profile, SellerProfile


# ====== Constante scor & praguri (0–100) ======

BUYER_SCORE_MIN = 0
BUYER_SCORE_MAX = 100
SELLER_SCORE_MIN = 0
SELLER_SCORE_MAX = 100

# Praguri de clasă A/B/C/D (trebuie să fie coerente cu proprietățile din modele)
TRUST_A_MIN = 85
TRUST_B_MIN = 70
TRUST_C_MIN = 50


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


# =====================================================================
# 1. SCOR CUMPĂRĂTOR (BUYER)
# =====================================================================

@dataclass
class BuyerEventWeights:
    # Bonusuri pozitive
    order_paid: int = 2              # comandă plătită și dusă la bun sfârșit
    order_completed: int = 1         # livrată și fără incidente
    good_history_bonus: int = 1      # bonus uneori, la milestones

    # Penalizări
    cancel_buyer_fault: int = -5     # anulare din vina cumpărătorului
    return_buyer_fault: int = -3     # retur abuziv / „nu îmi mai place” repetat
    dispute_lost: int = -8           # dispută pierdută
    chargeback: int = -15            # chargeback bancar grav

    # Identitate / securitate
    kyc_approved_bonus: int = 5      # KYC aprobat
    twofa_enabled_bonus: int = 3     # 2FA activ


DEFAULT_BUYER_WEIGHTS = BuyerEventWeights()


def adjust_buyer_score(profile: Profile, delta: int, *, commit: bool = True) -> int:
    """
    Aplică un delta pe scorul cumpărătorului și îl limitează în intervalul 0–100.
    """
    current = profile.buyer_trust_score or 0
    new_val = _clamp(current + delta, BUYER_SCORE_MIN, BUYER_SCORE_MAX)
    profile.buyer_trust_score = new_val
    if commit:
        profile.save(update_fields=["buyer_trust_score"])
    return new_val


def apply_buyer_identity_bonuses(
    profile: Profile,
    *,
    weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS,
    commit: bool = True,
) -> int:
    """
    Aplică bonusuri pentru identitate solidă: KYC + 2FA.
    Se poate apela când:
      - KYC trece în APPROVED
      - userul activează 2FA
    """
    delta = 0
    if profile.kyc_status == "APPROVED":
        delta += weights.kyc_approved_bonus
    if profile.two_factor_enabled:
        delta += weights.twofa_enabled_bonus

    return adjust_buyer_score(profile, delta, commit=commit)


# Evenimente principale (apelezi din orders/payments/support când implementăm):

def on_buyer_order_paid(profile: Profile, *, weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS, commit: bool = True) -> int:
    """
    Apelat când o comandă este plătită (fără să știm încă de retur).
    """
    return adjust_buyer_score(profile, weights.order_paid, commit=commit)


def on_buyer_order_completed_ok(profile: Profile, *, weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS, commit: bool = True) -> int:
    """
    Apelat când comanda este livrată și a trecut termenul de retur fără probleme.
    """
    return adjust_buyer_score(profile, weights.order_completed, commit=commit)


def on_buyer_cancel_buyer_fault(profile: Profile, *, weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS, commit: bool = True) -> int:
    """
    Apelat când comanda este anulată din vina cumpărătorului (nu ridică colet, se răzgândește târziu etc.).
    """
    return adjust_buyer_score(profile, weights.cancel_buyer_fault, commit=commit)


def on_buyer_return_buyer_fault(profile: Profile, *, weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS, commit: bool = True) -> int:
    """
    Apelat când returul este considerat „abuziv” sau repetitiv și confirmat ca buyer fault.
    """
    return adjust_buyer_score(profile, weights.return_buyer_fault, commit=commit)


def on_buyer_dispute_lost(profile: Profile, *, weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS, commit: bool = True) -> int:
    """
    Apelat când o dispută este soluționată împotriva cumpărătorului.
    """
    return adjust_buyer_score(profile, weights.dispute_lost, commit=commit)


def on_buyer_chargeback(profile: Profile, *, weights: BuyerEventWeights = DEFAULT_BUYER_WEIGHTS, commit: bool = True) -> int:
    """
    Apelat la chargeback bancar – incident sever.
    """
    return adjust_buyer_score(profile, weights.chargeback, commit=commit)


def buyer_trust_class_from_score(score: int) -> str:
    """
    Mic utilitar care mapează scor -> clasă A/B/C/D.
    E coerent cu profile.buyer_trust_class, dar îl putem folosi și în alte contexte.
    """
    if score >= TRUST_A_MIN:
        return "A"
    if score >= TRUST_B_MIN:
        return "B"
    if score >= TRUST_C_MIN:
        return "C"
    return "D"


# =====================================================================
# 2. SCOR VÂNZĂTOR (SELLER) + NIVEL & COMISION
# =====================================================================

@dataclass
class SellerEventWeights:
    # Bonusuri
    order_paid: int = 1              # comandă nouă plătită
    order_shipped_on_time: int = 2   # AWB generat și livrat în termen
    order_completed_ok: int = 1      # finalizată fără retur / dispute

    # Penalizări
    late_shipment: int = -3          # întârziere livrare
    cancel_seller_fault: int = -5    # anulare din vina vânzătorului (no stock, nu livrează etc.)
    return_seller_fault: int = -6    # retur confirmat ca seller fault
    dispute_lost: int = -10          # dispută pierdută (produs fals, stare neconformă)
    severe_incident: int = -20       # incidente grave (fraudă evidentă etc.)

    # Identitate / conformitate
    kyc_approved_bonus: int = 5
    twofa_enabled_bonus: int = 3


DEFAULT_SELLER_WEIGHTS = SellerEventWeights()

# Praguri pentru nivel (bazate pe lifetime_sales_net – RON)
RISING_THRESHOLD = Decimal("10000")
TOP_THRESHOLD = Decimal("15000")

AMATOR_COMMISSION = Decimal("9.00")
RISING_COMMISSION = Decimal("8.00")
TOP_COMMISSION = Decimal("7.00")
VIP_COMMISSION = Decimal("6.00")  # VIP = abonament plătit (setezi manual nivelul în admin)


def adjust_seller_score(seller: SellerProfile, delta: int, *, commit: bool = True) -> int:
    current = seller.seller_trust_score or 0
    new_val = _clamp(current + delta, SELLER_SCORE_MIN, SELLER_SCORE_MAX)
    seller.seller_trust_score = new_val
    if commit:
        seller.save(update_fields=["seller_trust_score"])
    return new_val


def apply_seller_identity_bonuses(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    """
    Bonus pentru vânzătorii cu KYC aprobat și 2FA activ.
    """
    prof = getattr(seller.user, "profile", None)
    if not prof:
        return seller.seller_trust_score

    delta = 0
    if prof.kyc_status == "APPROVED":
        delta += weights.kyc_approved_bonus
    if prof.two_factor_enabled:
        delta += weights.twofa_enabled_bonus

    return adjust_seller_score(seller, delta, commit=commit)


def seller_trust_class_from_score(score: int) -> str:
    if score >= TRUST_A_MIN:
        return "A"
    if score >= TRUST_B_MIN:
        return "B"
    if score >= TRUST_C_MIN:
        return "C"
    return "D"


# ---- Evenimente legate de comenzi ----

def on_seller_order_paid(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.order_paid, commit=commit)


def on_seller_order_shipped_on_time(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.order_shipped_on_time, commit=commit)


def on_seller_order_completed_ok(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.order_completed_ok, commit=commit)


def on_seller_late_shipment(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.late_shipment, commit=commit)


def on_seller_cancel_seller_fault(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.cancel_seller_fault, commit=commit)


def on_seller_return_seller_fault(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.return_seller_fault, commit=commit)


def on_seller_dispute_lost(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.dispute_lost, commit=commit)


def on_seller_severe_incident(
    seller: SellerProfile,
    *,
    weights: SellerEventWeights = DEFAULT_SELLER_WEIGHTS,
    commit: bool = True,
) -> int:
    return adjust_seller_score(seller, weights.severe_incident, commit=commit)


# ---- Volum vânzări & nivel / comision ----

@transaction.atomic
def register_seller_sale(
    seller: SellerProfile,
    net_amount: Decimal,
    *,
    commit: bool = True,
) -> SellerProfile:
    """
    Apelat când o vânzare este finalizată și escrow-ul se eliberează către vânzător.
    Crește `lifetime_sales_net` și actualizează nivelul + comisionul,
    conform pragurilor:
        - < 10.000 RON  => Amator (9%)
        - >= 10.000 RON => Rising (8%)
        - >= 15.000 RON => Top (7%)
        - VIP           => 6% (nivel setat manual, nu îl schimbăm automat)
    """

    if net_amount <= 0:
        return seller

    seller.lifetime_sales_net = (seller.lifetime_sales_net or Decimal("0")) + net_amount

    # Nu umblăm la VIP dinamic – se setează manual ca abonament
    if seller.seller_level != SellerProfile.SELLER_LEVEL_VIP:
        volume = seller.lifetime_sales_net or Decimal("0")
        if volume >= TOP_THRESHOLD:
            seller.seller_level = SellerProfile.SELLER_LEVEL_TOP
            seller.seller_commission_rate = TOP_COMMISSION
        elif volume >= RISING_THRESHOLD:
            seller.seller_level = SellerProfile.SELLER_LEVEL_RISING
            seller.seller_commission_rate = RISING_COMMISSION
        else:
            seller.seller_level = SellerProfile.SELLER_LEVEL_AMATOR
            seller.seller_commission_rate = AMATOR_COMMISSION
    else:
        # VIP – ne asigurăm că are comisionul corect
        seller.seller_commission_rate = VIP_COMMISSION

    if commit:
        seller.save(update_fields=["lifetime_sales_net", "seller_level", "seller_commission_rate"])
    return seller
