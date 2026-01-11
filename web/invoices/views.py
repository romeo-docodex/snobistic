# invoices/views.py
from __future__ import annotations

import datetime
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Invoice

try:
    from weasyprint import HTML
except ImportError:
    HTML = None


def _user_can_access_invoice(user, invoice: Invoice) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if invoice.buyer_id == user.id:
        return True
    if invoice.seller_id and invoice.seller_id == user.id:
        return True
    return False


def _user_can_manage_invoice(user, invoice: Invoice) -> bool:
    # MVP: doar staff gestionează emitere/anulare/storno
    return bool(user.is_authenticated and user.is_staff)


def _parse_date(value: str | None) -> Optional[datetime.date]:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.date.fromisoformat(value)
    except Exception:
        return None


def _apply_common_filters(request, qs):
    """
    Filtre standard pentru listări:
      - q: search după invoice_number
      - invoice_type
      - document_type
      - status
      - date_from/date_to (pe issued_at sau created_at dacă issued_at e NULL)
    """
    q = (request.GET.get("q") or "").strip()
    invoice_type = (request.GET.get("type") or "").strip()
    document_type = (request.GET.get("doc") or "").strip()
    status = (request.GET.get("status") or "").strip()
    date_from = _parse_date(request.GET.get("from"))
    date_to = _parse_date(request.GET.get("to"))

    if q:
        qs = qs.filter(invoice_number__icontains=q)

    if invoice_type:
        qs = qs.filter(invoice_type=invoice_type)

    if document_type:
        qs = qs.filter(document_type=document_type)

    if status:
        qs = qs.filter(status=status)

    # range: prefer issued_at; fallback created_at (pentru DRAFT)
    # - from: >= date_from 00:00
    # - to: <= date_to 23:59:59
    if date_from:
        dt_from = datetime.datetime.combine(date_from, datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        qs = qs.filter(Q(issued_at__gte=dt_from) | Q(issued_at__isnull=True, created_at__gte=dt_from))

    if date_to:
        dt_to = datetime.datetime.combine(date_to, datetime.time.max).replace(tzinfo=timezone.get_current_timezone())
        qs = qs.filter(Q(issued_at__lte=dt_to) | Q(issued_at__isnull=True, created_at__lte=dt_to))

    return qs


def _paginate(request, qs, per_page: int = 20):
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)
    return page_obj


@login_required
def invoice_list_my_view(request):
    """
    Buyer: "Facturile mele"
    - staff: vede toate (util pt debug/admin)
    - user normal: doar invoice.buyer = user
    """
    qs = Invoice.objects.select_related("order", "buyer", "seller", "original_invoice")

    if not request.user.is_staff:
        qs = qs.filter(buyer=request.user)

    qs = _apply_common_filters(request, qs).order_by("-issued_at", "-created_at", "-id")

    page_obj = _paginate(request, qs, per_page=20)

    return render(
        request,
        "invoices/invoice_list.html",
        {
            "page_obj": page_obj,
            "invoices": page_obj.object_list,
            "account_section": "invoices",
            # pentru select-uri
            "TYPE_CHOICES": Invoice.Type.choices,
            "DOC_CHOICES": Invoice.Document.choices,
            "STATUS_CHOICES": Invoice.Status.choices,
            # păstrăm query pentru template (valori preselectate)
            "filters": {
                "q": (request.GET.get("q") or "").strip(),
                "type": (request.GET.get("type") or "").strip(),
                "doc": (request.GET.get("doc") or "").strip(),
                "status": (request.GET.get("status") or "").strip(),
                "from": (request.GET.get("from") or "").strip(),
                "to": (request.GET.get("to") or "").strip(),
            },
        },
    )


@login_required
def invoice_list_commission_view(request):
    """
    Seller: "Facturi comision"
    - staff: vede toate (comision)
    - seller: doar invoice_type=commission și seller = user
    """
    qs = Invoice.objects.select_related("order", "buyer", "seller", "original_invoice").filter(
        invoice_type=Invoice.Type.COMMISSION
    )

    if not request.user.is_staff:
        qs = qs.filter(seller=request.user)

    # în această listă tipul e fix "commission", dar lăsăm restul filtrelor
    qs = _apply_common_filters(request, qs).order_by("-issued_at", "-created_at", "-id")

    page_obj = _paginate(request, qs, per_page=20)

    return render(
        request,
        "invoices/invoice_commission_list.html",
        {
            "page_obj": page_obj,
            "invoices": page_obj.object_list,
            "account_section": "seller_invoices_commission",
            "TYPE_CHOICES": Invoice.Type.choices,
            "DOC_CHOICES": Invoice.Document.choices,
            "STATUS_CHOICES": Invoice.Status.choices,
            "filters": {
                "q": (request.GET.get("q") or "").strip(),
                "doc": (request.GET.get("doc") or "").strip(),
                "status": (request.GET.get("status") or "").strip(),
                "from": (request.GET.get("from") or "").strip(),
                "to": (request.GET.get("to") or "").strip(),
            },
        },
    )


@login_required
def invoice_detail_view(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "buyer", "seller", "original_invoice").prefetch_related("lines"),
        pk=pk,
    )

    if not _user_can_access_invoice(request.user, invoice):
        messages.error(request, "Nu ai acces la această factură.")
        return redirect("dashboard:orders_list")

    return render(
        request,
        "invoices/invoice_detail.html",
        {
            "invoice": invoice,
            "order": invoice.order,
            "kind": invoice.invoice_type,
            "lines": invoice.lines.all(),
            "can_manage": _user_can_manage_invoice(request.user, invoice),
        },
    )


@login_required
def invoice_pdf_view(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "buyer", "seller", "original_invoice").prefetch_related("lines"),
        pk=pk,
    )

    if not _user_can_access_invoice(request.user, invoice):
        messages.error(request, "Nu ai acces la această factură.")
        return redirect("dashboard:orders_list")

    if HTML is None:
        return HttpResponse(
            "Generarea de PDF nu este configurată (weasyprint lipsește).",
            content_type="text/plain",
            status=501,
        )

    html_string = render_to_string(
        "invoices/invoice_pdf.html",
        {
            "invoice": invoice,
            "order": invoice.order,
            "lines": invoice.lines.all(),
            "platform_name": "Snobistic",
            "company_vat": getattr(settings, "SNOBISTIC_COMPANY_VAT", "RO00000000"),
        },
        request=request,
    )

    response = HttpResponse(content_type="application/pdf")
    filename = f"Document-{invoice.invoice_number or invoice.pk}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf(response)
    return response


@login_required
@require_POST
def invoice_issue_view(request, pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related("lines"), pk=pk)

    if not _user_can_manage_invoice(request.user, invoice):
        messages.error(request, "Nu ai drepturi pentru emiterea facturii.")
        return redirect("invoices:invoice_detail", pk=pk)

    try:
        invoice.issue(by_user=request.user)
        messages.success(request, f"Factura a fost emisă: {invoice.invoice_number}.")
    except Exception as e:
        messages.error(request, f"Nu am putut emite factura: {e}")

    return redirect("invoices:invoice_detail", pk=pk)


@login_required
@require_POST
def invoice_cancel_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if not _user_can_manage_invoice(request.user, invoice):
        messages.error(request, "Nu ai drepturi pentru anularea facturii.")
        return redirect("invoices:invoice_detail", pk=pk)

    reason = (request.POST.get("reason") or "").strip()

    try:
        invoice.cancel(by_user=request.user, reason=reason)
        messages.success(request, "Factura a fost anulată (marcaj intern).")
    except Exception as e:
        messages.error(request, f"Nu am putut anula factura: {e}")

    return redirect("invoices:invoice_detail", pk=pk)


@login_required
@require_POST
def invoice_credit_note_create_view(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "buyer", "seller").prefetch_related("lines"),
        pk=pk,
    )

    if not _user_can_manage_invoice(request.user, invoice):
        messages.error(request, "Nu ai drepturi pentru storno.")
        return redirect("invoices:invoice_detail", pk=pk)

    reason = (request.POST.get("reason") or "").strip()

    try:
        cn = invoice.create_credit_note(by_user=request.user, reason=reason)
        messages.success(request, f"Storno emis: {cn.invoice_number}.")
        return redirect("invoices:invoice_detail", pk=cn.pk)
    except Exception as e:
        messages.error(request, f"Nu am putut crea storno: {e}")
        return redirect("invoices:invoice_detail", pk=pk)
