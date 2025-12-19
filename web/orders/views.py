# orders/views.py
import csv
from decimal import Decimal as D

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Order, ReturnRequest, _pct
from .forms import ReturnRequestForm

from invoices.models import Invoice


def _is_seller(user):
    prof = getattr(user, "profile", None)
    return bool(prof and prof.role_seller)


@login_required
def order_list_view(request):
    """
    /orders/ – fallback pentru BUYER.
    - dacă user-ul este seller → trimitem spre dashboard-ul de seller (articole vândute)
    - dacă este buyer → folosim același template ca în dashboard: dashboard/buyer/orders_list.html
    """
    user = request.user

    # Seller: nu mai listăm comenzile aici, îl trimitem în dashboard-ul lui
    if _is_seller(user):
        return redirect("dashboard:sold_list")

    # Buyer: listă comenzi (același pattern ca în dashboard.views.orders_list)
    orders = (
        Order.objects.filter(buyer=user)
        .order_by("-created_at")
        .prefetch_related("payments", "items")
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
def order_detail_view(request, pk):
    """
    Detalii comandă + info retur (buyer) / doar detalii (seller).
    """
    order = get_object_or_404(Order, pk=pk)
    user = request.user

    # Seller are acces doar dacă are produse în comandă
    is_seller = _is_seller(user) and order.items.filter(product__owner=user).exists()

    if not (order.buyer == user or is_seller or user.is_staff):
        raise Http404

    # Info retur doar pentru buyer
    last_return = None
    can_request_return = False
    if order.buyer == user:
        last_return = order.return_requests.filter(buyer=user).order_by(
            "-created_at"
        ).first()
        can_request_return = (
            order.shipping_status == Order.SHIPPING_SHIPPED
            and not order.return_requests.filter(
                buyer=user,
                status=ReturnRequest.STATUS_PENDING,
            ).exists()
        )

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "is_seller": is_seller,
            "can_request_return": can_request_return,
            "last_return": last_return,
        },
    )


@login_required
@user_passes_test(_is_seller)
def order_export_view(request):
    """
    Export CSV pentru seller.
    """
    orders = (
        Order.objects.filter(items__product__owner=request.user)
        .distinct()
        .prefetch_related("items")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'

    writer = csv.writer(response)
    writer.writerow(
        ["Order ID", "Data", "Buyer", "Total", "Status plată", "Status livrare"]
    )

    for o in orders:
        buyer_name = getattr(o.buyer, "full_name", "").strip() or o.buyer.email
        writer.writerow(
            [
                o.id,
                o.created_at.strftime("%Y-%m-%d"),
                buyer_name,
                f"{o.total} RON",
                o.payment_status_label,
                o.get_shipping_status_display(),
            ]
        )
    return response


@login_required
def return_list_view(request):
    """
    Buyer: vede propriile cereri de retur.
    Seller: vede cererile de retur pentru comenzile cu produsele lui.
    """
    user = request.user
    if _is_seller(user):
        returns = (
            ReturnRequest.objects.filter(order__items__product__owner=user)
            .select_related("order", "buyer")
            .distinct()
        )
        is_seller = True
    else:
        returns = ReturnRequest.objects.filter(buyer=user).select_related(
            "order", "buyer"
        )
        is_seller = False

    return render(
        request,
        "orders/return_list.html",
        {
            "returns": returns,
            "is_seller": is_seller,
        },
    )


@login_required
def order_return_request_view(request, pk):
    """
    Buyer inițiază cerere de retur pentru o comandă.
    O permitem doar dacă:
      - comanda îi aparține
      - comanda este marcată ca expediată
      - nu există deja o cerere PENDING pentru această comandă și buyer.

    La crearea returului, marcăm și escrow-ul ca DISPUTED,
    ca să nu mai poată fi eliberat automat.
    """
    order = get_object_or_404(Order, pk=pk, buyer=request.user)

    if order.shipping_status != Order.SHIPPING_SHIPPED:
        # Poți înlocui cu redirect + mesaj dacă vrei alt comportament
        raise Http404

    if order.return_requests.filter(
        buyer=request.user,
        status=ReturnRequest.STATUS_PENDING,
    ).exists():
        messages.warning(
            request, "Ai deja o cerere de retur în curs pentru această comandă."
        )
        return redirect("orders:order_detail", pk=order.pk)

    if request.method == "POST":
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            rr = form.save(commit=False)
            rr.order = order
            rr.buyer = request.user
            rr.save()

            # IMPORTANT: escrow intră în dispută când se deschide returul
            order.mark_escrow_disputed()

            messages.success(
                request,
                "Cererea de retur a fost trimisă. Te vom contacta în curând.",
            )
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = ReturnRequestForm()

    return render(
        request,
        "orders/return_request.html",
        {
            "order": order,
            "form": form,
        },
    )


@login_required
def invoice_view(request, order_id, kind):
    """
    Generează (dacă nu există) sau afișează factura pentru:
    - 'product'   → valoare produse (seller ↔ buyer)
    - 'shipping'  → transport (platformă ↔ buyer, în funcție de modelul de business)
    - 'commission'→ comision platformă (platformă ↔ seller)
    - 'return'    → retur (ajustare / storno, legat de ReturnRequest aprobat)

    Reguli legate de escrow:
    - PRODUCT/SHIPPING → doar dacă comanda este PLĂTITĂ (payment_status=PAID)
    - COMMISSION       → doar dacă escrow_status = RELEASED (banii au devenit definitiv ai platformei)
    - RETURN           → doar dacă există cel puțin un ReturnRequest APPROVED
    """
    order = get_object_or_404(Order, pk=order_id)

    user = request.user
    is_buyer = order.buyer_id == user.id
    is_seller = order.items.filter(product__owner=user).exists()

    if not (is_buyer or is_seller or user.is_staff):
        messages.error(request, "Nu ai acces la această factură.")
        return redirect("core:home")

    kind = kind.lower()
    type_map = {
        "product": Invoice.Type.PRODUCT,
        "shipping": Invoice.Type.SHIPPING,
        "commission": Invoice.Type.COMMISSION,
        "return": Invoice.Type.RETURN,
    }
    if kind not in type_map:
        raise Http404("Tip factură necunoscut.")

    invoice_type = type_map[kind]

    # 1) Validări business legate de stare plată / escrow / retur
    # ----------------------------------------------------------

    # PRODUCT + SHIPPING → necesită plată confirmată
    if invoice_type in (Invoice.Type.PRODUCT, Invoice.Type.SHIPPING):
        if order.payment_status != Order.PAYMENT_PAID:
            messages.error(
                request,
                "Factura poate fi generată doar după ce comanda este plătită.",
            )
            return redirect("orders:order_detail", pk=order.pk)

    # COMMISSION → doar după eliberarea escrow-ului
    if invoice_type == Invoice.Type.COMMISSION:
        if order.escrow_status != Order.ESCROW_RELEASED:
            messages.error(
                request,
                "Factura de comision poate fi emisă doar după eliberarea escrow-ului.",
            )
            return redirect("orders:order_detail", pk=order.pk)

        # de comision are sens în principal pentru seller + staff
        if not (is_seller or user.is_staff):
            messages.error(
                request,
                "Doar vânzătorul sau staff-ul Snobistic pot accesa această factură.",
            )
            return redirect("orders:order_detail", pk=order.pk)

    # RETURN → doar dacă există un retur APPROVED
    if invoice_type == Invoice.Type.RETURN:
        has_approved_return = order.return_requests.filter(
            status=ReturnRequest.STATUS_APPROVED
        ).exists()
        if not has_approved_return:
            messages.error(
                request,
                "Factura de retur poate fi emisă doar pentru comenzi cu retur aprobat.",
            )
            return redirect("orders:order_detail", pk=order.pk)

    # 2) Determinare buyer/seller + sume
    # ----------------------------------
    # vânzătorul principal – primul owner din items
    seller = order.items.first().product.owner if order.items.exists() else None

    base_amount = D("0.00")
    if invoice_type == Invoice.Type.PRODUCT:
        base_amount = order.subtotal
    elif invoice_type == Invoice.Type.SHIPPING:
        base_amount = order.shipping_cost
    elif invoice_type == Invoice.Type.COMMISSION:
        base_amount = order.seller_commission_amount
    elif invoice_type == Invoice.Type.RETURN:
        # momentan 0 – ulterior se poate lega de suma efectiv restituită
        base_amount = D("0.00")

    vat_percent = D(getattr(settings, "SNOBISTIC_VAT_PERCENT", "19.00"))
    vat_amount = _pct(base_amount, vat_percent)
    total_amount = base_amount + vat_amount

    invoice, created = Invoice.objects.get_or_create(
        order=order,
        invoice_type=invoice_type,
        defaults={
            "buyer": order.buyer,
            "seller": seller,
            "currency": getattr(settings, "SNOBISTIC_CURRENCY", "RON"),
            "net_amount": base_amount,
            "vat_percent": vat_percent,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
            "status": Invoice.Status.ISSUED,
        },
    )

    return render(
        request,
        "invoices/invoice_detail.html",
        {
            "invoice": invoice,
            "order": order,
            "kind": kind,
        },
    )
