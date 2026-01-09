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
    user = request.user

    if _is_seller(user):
        return redirect("dashboard:sold_list")

    orders = (
        Order.objects.filter(buyer=user)
        .order_by("-created_at")
        .prefetch_related("payments", "items")
    )

    return render(
        request,
        "dashboard/buyer/orders_list.html",
        {"orders": orders, "now": timezone.now()},
    )


@login_required
def order_detail_view(request, pk):
    order = get_object_or_404(Order, pk=pk)
    user = request.user

    is_seller = _is_seller(user) and order.items.filter(product__owner=user).exists()

    if not (order.buyer == user or is_seller or user.is_staff):
        raise Http404

    last_return = None
    can_request_return = False
    if order.buyer == user:
        last_return = order.return_requests.filter(buyer=user).order_by("-created_at").first()

        # ✅ retur permis după ce e cel puțin "shipped" (incl. in_transit/delivered)
        can_request_return = (
            order.shipping_status in (
                Order.SHIPPING_SHIPPED,
                Order.SHIPPING_IN_TRANSIT,
                Order.SHIPPING_DELIVERED,
            )
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
    orders = (
        Order.objects.filter(items__product__owner=request.user)
        .distinct()
        .prefetch_related("items")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'

    writer = csv.writer(response)
    writer.writerow(["Order ID", "Data", "Buyer", "Total", "Status plată", "Status livrare", "Lifecycle"])

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
                o.get_status_display(),
            ]
        )
    return response


@login_required
def return_list_view(request):
    user = request.user
    if _is_seller(user):
        returns = (
            ReturnRequest.objects.filter(order__items__product__owner=user)
            .select_related("order", "buyer")
            .distinct()
        )
        is_seller = True
    else:
        returns = ReturnRequest.objects.filter(buyer=user).select_related("order", "buyer")
        is_seller = False

    return render(
        request,
        "orders/return_list.html",
        {"returns": returns, "is_seller": is_seller},
    )


@login_required
def order_return_request_view(request, pk):
    order = get_object_or_404(Order, pk=pk, buyer=request.user)

    # ✅ acum permitem și in_transit / delivered
    if order.shipping_status not in (
        Order.SHIPPING_SHIPPED,
        Order.SHIPPING_IN_TRANSIT,
        Order.SHIPPING_DELIVERED,
    ):
        raise Http404

    if order.return_requests.filter(
        buyer=request.user,
        status=ReturnRequest.STATUS_PENDING,
    ).exists():
        messages.warning(request, "Ai deja o cerere de retur în curs pentru această comandă.")
        return redirect("orders:order_detail", pk=order.pk)

    if request.method == "POST":
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            rr = form.save(commit=False)
            rr.order = order
            rr.buyer = request.user
            rr.save()

            order.mark_escrow_disputed()

            messages.success(request, "Cererea de retur a fost trimisă. Te vom contacta în curând.")
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = ReturnRequestForm()

    return render(
        request,
        "orders/return_request.html",
        {"order": order, "form": form},
    )


@login_required
def invoice_view(request, order_id, kind):
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

    if invoice_type in (Invoice.Type.PRODUCT, Invoice.Type.SHIPPING):
        if order.payment_status != Order.PAYMENT_PAID:
            messages.error(request, "Factura poate fi generată doar după ce comanda este plătită.")
            return redirect("orders:order_detail", pk=order.pk)

    if invoice_type == Invoice.Type.COMMISSION:
        if order.escrow_status != Order.ESCROW_RELEASED:
            messages.error(request, "Factura de comision poate fi emisă doar după eliberarea escrow-ului.")
            return redirect("orders:order_detail", pk=order.pk)

        if not (is_seller or user.is_staff):
            messages.error(request, "Doar vânzătorul sau staff-ul Snobistic pot accesa această factură.")
            return redirect("orders:order_detail", pk=order.pk)

    if invoice_type == Invoice.Type.RETURN:
        has_approved_return = order.return_requests.filter(status=ReturnRequest.STATUS_APPROVED).exists()
        if not has_approved_return:
            messages.error(request, "Factura de retur poate fi emisă doar pentru comenzi cu retur aprobat.")
            return redirect("orders:order_detail", pk=order.pk)

    seller = order.items.first().product.owner if order.items.exists() else None

    base_amount = D("0.00")
    if invoice_type == Invoice.Type.PRODUCT:
        base_amount = order.subtotal
    elif invoice_type == Invoice.Type.SHIPPING:
        base_amount = order.shipping_cost
    elif invoice_type == Invoice.Type.COMMISSION:
        base_amount = order.seller_commission_amount
    elif invoice_type == Invoice.Type.RETURN:
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
        {"invoice": invoice, "order": order, "kind": kind},
    )
