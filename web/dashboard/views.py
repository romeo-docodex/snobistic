# dashboard/views.py
import csv
from datetime import date
from decimal import Decimal

from accounts.services.score import RISING_THRESHOLD, TOP_THRESHOLD
from accounts.models import SellerProfile
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Prefetch
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from auctions.models import Auction
from catalog.models import Product
from orders.models import Order, OrderItem
from payments.models import WalletTransaction, Wallet
from logistics.models import Shipment
from invoices.models import Invoice


def is_seller(user):
    """
    Seller = user cu profile.role_seller = True
    sau cu sellerprofile existent.
    Păstrăm și fallback pe user.is_seller pentru compatibilitate.
    """
    if not user.is_authenticated:
        return False

    prof = getattr(user, "profile", None)
    if prof is not None:
        if getattr(prof, "role_seller", False):
            return True

    if hasattr(user, "sellerprofile"):
        return True

    return getattr(user, "is_seller", False)


def is_buyer(user):
    """
    Buyer = user autenticat care poate cumpăra:
    - dacă are Profile: folosim profile.can_buy
    - fallback: orice user autenticat care nu e strict seller-only
    """
    if not user.is_authenticated:
        return False

    prof = getattr(user, "profile", None)
    if prof is not None:
        return prof.can_buy

    # dacă nu avem profil, considerăm buyer dacă nu e seller
    return not is_seller(user)


# ---------------------------------------------------------------------------
# SELLER VIEWS
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_seller)
def seller_dashboard(request):
    user = request.user
    now = timezone.now()

    # ---- Seller profile + profil user (pentru KYC & 2FA) ----
    seller = getattr(user, "sellerprofile", None)
    profile = getattr(user, "profile", None)

    seller_trust_score = seller.seller_trust_score if seller else None
    seller_trust_class = seller.seller_trust_class if seller else None
    lifetime_sales_net = seller.lifetime_sales_net if seller else None
    current_level = seller.seller_level if seller else None

    # Progress bar "level up"
    level_progress = None        # 0–100
    next_level_label = ""        # ex: "Rising Seller"

    if seller:
        volume = lifetime_sales_net or Decimal("0.00")
        target = None

        if current_level == SellerProfile.SELLER_LEVEL_AMATOR:
            target = RISING_THRESHOLD
            next_level_label = "Rising Seller"
        elif current_level == SellerProfile.SELLER_LEVEL_RISING:
            target = TOP_THRESHOLD
            next_level_label = "Top Seller"
        elif current_level == SellerProfile.SELLER_LEVEL_TOP:
            # Top = maxim automat, următorul ar fi VIP (setat manual)
            target = TOP_THRESHOLD
            next_level_label = "Nivel maxim automat"
        elif current_level == SellerProfile.SELLER_LEVEL_VIP:
            target = None
            next_level_label = "Nivel VIP"

        if target and target > 0:
            try:
                raw = (volume / target) * Decimal("100")
            except Exception:
                raw = Decimal("0")
            if raw < 0:
                raw = Decimal("0")
            if raw > 100:
                raw = Decimal("100")
            level_progress = int(raw)
        else:
            # VIP sau fără prag – considerăm 100%
            level_progress = 100

    kyc_status = profile.kyc_status if profile else None
    has_kyc_badge = profile.has_kyc_badge if profile else False
    two_factor_enabled = profile.two_factor_enabled if profile else False

    # ---- Statistici de vânzător ----
    total_products = Product.objects.filter(owner=user).count()

    # ✅ FIX: nu există Auction.is_active -> folosim status + fereastra timp
    active_auctions = (
        Auction.objects.filter(
            creator=user,
            status=Auction.Status.ACTIVE,
            start_time__lte=now,
            end_time__gt=now,
        ).count()
    )

    sold_products = (
        Order.objects.filter(
            items__product__owner=user,
            payment_status="paid",
        )
        .distinct()
        .count()
    )

    # 2) Ensure wallet exists
    wallet_obj, _ = Wallet.objects.get_or_create(user=user)
    wallet_balance = wallet_obj.balance

    # 3) Last 6 months labels (YYYY-MM)
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m = (today.month - i - 1) % 12 + 1
        y = today.year - ((today.month - i - 1) // 12)
        months.append(f"{y}-{m:02d}")

    # 4) Orders per month
    orders_qs = (
        Order.objects.filter(items__product__owner=user, payment_status="paid")
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("pk"))
    )
    orders_data = {o["month"].strftime("%Y-%m"): o["count"] for o in orders_qs}

    # 5) Products created per month
    prods_qs = (
        Product.objects.filter(owner=user)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("pk"))
    )
    prods_data = {p["month"].strftime("%Y-%m"): p["count"] for p in prods_qs}

    return render(
        request,
        "dashboard/seller/dashboard.html",
        {
            "total_products": total_products,
            "active_auctions": active_auctions,
            "sold_products": sold_products,
            "wallet_balance": wallet_balance,
            "chart_months": months,
            "chart_orders": [orders_data.get(m, 0) for m in months],
            "chart_products": [prods_data.get(m, 0) for m in months],

            # ---- Nou: context pentru cardul de profil vânzător ----
            "seller": seller,
            "profile": profile,
            "seller_trust_score": seller_trust_score,
            "seller_trust_class": seller_trust_class,
            "lifetime_sales_net": lifetime_sales_net,
            "level_progress": level_progress,
            "next_level_label": next_level_label,
            "kyc_status": kyc_status,
            "has_kyc_badge": has_kyc_badge,
            "two_factor_enabled": two_factor_enabled,
        },
    )


@login_required
@user_passes_test(is_seller)
def products_list(request):
    qs = Product.objects.filter(owner=request.user)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="produse_magazin.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Titlu",
                "SKU",
                "Subcategorie",
                "Status",
                "Creat la",
                "Validat la",
                "Preț",
                "URL imagine",
            ]
        )
        for p in qs:
            subcat = p.category.name
            status = "Validat" if p.is_active else "În Validare"
            created = p.created_at.strftime("%Y-%m-%d %H:%M")
            validated = p.updated_at.strftime("%Y-%m-%d %H:%M") if p.is_active else ""
            img_url = (
                request.build_absolute_uri(p.main_image.url) if p.main_image else ""
            )
            writer.writerow(
                [p.title, p.sku, subcat, status, created, validated, p.price, img_url]
            )
        return response

    return render(
        request,
        "dashboard/seller/products_list.html",
        {"products": qs},
    )


@login_required
@user_passes_test(is_seller)
def auctions_list(request):
    user = request.user
    now = timezone.now()

    qs = (
        Auction.objects.filter(creator=user)
        .select_related("product")
        .order_by("-created_at")
    )

    # CSV export
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="licitatii_postate.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Titlu",
                "SKU",
                "Status produs (validare)",
                "Status licitație",
                "Creat la",
                "Start licitație",
                "Sfârșit licitație",
                "Timp rămas",
                "Preț curent",
                "Preț pornire",
                "Preț rezervă (minim)",
                "URL imagine",
            ]
        )

        for a in qs:
            title = a.product.title
            sku = a.product.sku

            product_status = "Validat" if getattr(a.product, "is_active", False) else "În validare"
            auction_status = a.get_status_display()

            created = a.created_at.strftime("%Y-%m-%d %H:%M")
            start_dt = a.start_time.strftime("%Y-%m-%d %H:%M") if a.start_time else ""
            end_dt = a.end_time.strftime("%Y-%m-%d %H:%M") if a.end_time else ""

            remaining = ""
            if a.end_time:
                remaining = str(max(a.end_time - now, timezone.timedelta())).split(".")[0]

            current = a.current_price or ""
            start_amt = a.start_price or ""
            reserve = a.reserve_price if a.reserve_price is not None else a.start_price

            img_url = (
                request.build_absolute_uri(a.product.main_image.url)
                if a.product.main_image
                else ""
            )

            writer.writerow(
                [
                    title,
                    sku,
                    product_status,
                    auction_status,
                    created,
                    start_dt,
                    end_dt,
                    remaining,
                    current,
                    start_amt,
                    reserve,
                    img_url,
                ]
            )
        return response

    return render(
        request,
        "dashboard/seller/auctions_list.html",
        {
            "auctions": qs,
            "now": now,  # ✅ folosit în template la timeuntil / comparații
        },
    )


@login_required
@user_passes_test(is_seller)
def sold_list(request):
    """
    Articole vândute pentru vânzătorul curent.
    - listăm comenzile PLĂTITE în care apar produse ale userului
    - pentru fiecare comandă, prefetch-uim DOAR OrderItem-urile
      unde product.owner = user (nu vedem produsele altor vânzători)
    """
    user = request.user

    sold_orders = (
        Order.objects.filter(
            items__product__owner=user,
            payment_status=Order.PAYMENT_PAID,
        )
        .select_related("buyer")
        .select_related("shipment")
        .prefetch_related(
            "payments",
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related("product").filter(
                    product__owner=user
                ),
            ),
        )
        .distinct()
        .order_by("-created_at")
    )

    return render(
        request,
        "dashboard/seller/sold_list.html",
        {"sold_orders": sold_orders},
    )


@login_required
@user_passes_test(is_seller)
def wallet(request):
    # Ensure wallet exists
    wallet_obj, _ = Wallet.objects.get_or_create(user=request.user)

    # Base queryset
    qs = WalletTransaction.objects.filter(user=request.user).order_by("-date")

    # Period filtering
    period = request.GET.get("period", "all")
    now = timezone.now()
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start)
    elif period == "monthly":
        qs = qs.filter(date__year=now.year, date__month=now.month)
    elif period == "yearly":
        qs = qs.filter(date__year=now.year)
    # else: 'all' → no extra filter

    # CSV export
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="wallet_{period}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(["Dată", "Tip", "Sumă", "Sold după"])
        for tx in qs:
            writer.writerow(
                [
                    tx.date.strftime("%Y-%m-%d %H:%M"),
                    tx.get_transaction_type_display(),
                    tx.amount,
                    tx.balance_after,
                ]
            )
        return response

    return render(
        request,
        "dashboard/seller/wallet.html",
        {
            "balance": wallet_obj.balance,
            "transactions": qs,
            "period": period,
        },
    )


# ---- SELLER ORDER ACTIONS – legate acum de logistics + invoices ------------

@login_required
@user_passes_test(is_seller)
def generate_awb(request, order_id, item_id):
    """
    Generează / editează AWB pentru comanda dată.
    AWB-ul este definit la nivel de comandă (nu per item),
    deci item_id e ignorat – dar îl păstrăm în URL pentru compatibilitate.
    """
    return redirect("logistics:generate_awb", order_id=order_id)


@login_required
@user_passes_test(is_seller)
def download_awb(request, order_id, item_id):
    """
    Descarcă / deschide AWB-ul pentru comanda dată, dacă există Shipment.
    """
    user = request.user

    # ne asigurăm că sellerul are articole în comanda respectivă
    order = get_object_or_404(
        Order.objects.filter(items__product__owner=user).distinct(),
        pk=order_id,
    )

    try:
        shipment = order.shipment
    except Shipment.DoesNotExist:
        messages.error(
            request,
            "Nu există încă un AWB generat pentru această comandă.",
        )
        return redirect("dashboard:sold_list")

    # dacă ai salvat PDF local
    if shipment.label_pdf:
        return redirect(shipment.label_pdf.url)

    # dacă ai URL de label de la Curiera
    if shipment.label_url:
        return redirect(shipment.label_url)

    # ultim fallback – link de tracking (nu e PDF, dar tot ajută)
    if shipment.effective_tracking_url:
        return redirect(shipment.effective_tracking_url)

    messages.error(
        request,
        "AWB-ul nu are încă un fișier sau link de etichetă disponibil.",
    )
    return redirect("dashboard:sold_list")


@login_required
@user_passes_test(is_seller)
def upload_package_photos(request, order_id, item_id):
    messages.info(
        request,
        "Upload-ul de poze pentru colet va fi disponibil în curând.",
    )
    return redirect("dashboard:sold_list")


@login_required
@user_passes_test(is_seller)
def mark_sent(request, order_id, item_id):
    """
    Marchează comanda ca predată curierului + aplică trust scoring.
    """
    return redirect("logistics:hand_to_courier", order_id=order_id)


@login_required
@user_passes_test(is_seller)
def view_package_photos(request, order_id, item_id):
    messages.info(
        request,
        "Vizualizarea pozelor pentru colet va fi disponibilă în curând.",
    )
    return redirect("dashboard:sold_list")


@login_required
@user_passes_test(is_seller)
def initiate_return_seller(request, order_id, item_id):
    messages.info(
        request,
        "Fluxul de retur pentru acest produs va fi disponibil în curând.",
    )
    return redirect("dashboard:sold_list")


@login_required
@user_passes_test(is_seller)
def download_commission_invoice(request, order_id, item_id):
    """
    Descarcă factura de comision pentru seller (dacă există) pentru comanda dată.
    Căutăm ultima factură de tip COMMISSION emisă pentru seller + order.
    """
    user = request.user
    try:
        invoice = (
            Invoice.objects.filter(
                order_id=order_id,
                seller=user,
                invoice_type=Invoice.Type.COMMISSION,
            )
            .order_by("-issued_at")
            .first()
        )
    except Exception:
        invoice = None

    if not invoice:
        messages.info(
            request,
            "Factura de comision nu este încă disponibilă pentru această comandă.",
        )
        return redirect("dashboard:sold_list")

    return redirect("invoices:invoice_download", pk=invoice.pk)


# ---------------------------------------------------------------------------
# BUYER VIEWS
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_buyer)
def buyer_dashboard(request):
    user = request.user

    # 1. Comenzi plasate
    orders_count = Order.objects.filter(buyer=user).count()

    # 2. Favorite – dacă nu există profil sau relația, nu dăm crash
    favorites_count = 0
    has_dimensions = False
    try:
        profile = user.profile
        try:
            favorites_count = profile.favorites.count()
        except Exception:
            favorites_count = 0

        has_dimensions = any(
            [
                getattr(profile, "shoulders", None),
                getattr(profile, "bust", None),
                getattr(profile, "waist", None),
                getattr(profile, "hips", None),
                getattr(profile, "length", None),
                getattr(profile, "sleeve", None),
                getattr(profile, "inseam", None),
                getattr(profile, "outseam", None),
            ]
        )
    except Exception:
        # Fără profil → doar 0 / False
        favorites_count = 0
        has_dimensions = False

    return render(
        request,
        "dashboard/buyer/dashboard.html",
        {
            "orders_count": orders_count,
            "favorites_count": favorites_count,
            "has_dimensions": has_dimensions,
        },
    )


@login_required
@user_passes_test(is_buyer)
def orders_list(request):
    orders = (
        Order.objects.filter(buyer=request.user)
        .order_by("-created_at")
        .prefetch_related("payments", "items__product")
    )
    return render(
        request,
        "dashboard/buyer/orders_list.html",
        {
            "orders": orders,
            "now": timezone.now(),
        },
    )


@login_required
@user_passes_test(is_buyer)
def chat_quick(request):
    from messaging.models import Conversation

    convs = (
        Conversation.objects.filter(participants=request.user)
        .order_by("-last_updated")[:5]
    )
    return render(
        request,
        "dashboard/buyer/chat_quick.html",
        {"conversations": convs},
    )
