# invoices/views.py
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from .models import Invoice

try:
    # Ai nevoie de: pip install weasyprint
    from weasyprint import HTML
except ImportError:
    HTML = None


def _user_can_access_invoice(user, invoice: Invoice) -> bool:
    """
    Buyer poate vedea factura lui.
    Seller poate vedea factura unde este trecut ca seller.
    Staff vede tot.
    """
    if not user.is_authenticated:
        return False

    if user.is_staff:
        return True

    if invoice.buyer_id == user.id:
        return True

    if invoice.seller_id and invoice.seller_id == user.id:
        return True

    return False


@login_required
def invoice_detail_view(request, pk):
    """
    Pagina HTML de detaliu factură (folosește invoice_detail.html).
    Acces:
      - buyer (invoice.buyer)
      - seller (invoice.seller, dacă există)
      - staff
    """
    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "buyer", "seller"),
        pk=pk,
    )
    user = request.user

    if not _user_can_access_invoice(user, invoice):
        messages.error(request, "Nu ai acces la această factură.")
        return redirect("dashboard:orders_list")

    order = invoice.order

    # pentru template folosim "kind" ca alias la tip
    kind = invoice.invoice_type

    return render(
        request,
        "invoices/invoice_detail.html",
        {
            "invoice": invoice,
            "order": order,
            "kind": kind,
        },
    )


@login_required
def invoice_pdf_view(request, pk):
    """
    Generează PDF pentru o factură existentă.
    Acces:
      - buyer (invoice.buyer)
      - seller (invoice.seller, dacă există)
      - staff
    """
    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "buyer", "seller"),
        pk=pk,
    )
    user = request.user

    if not _user_can_access_invoice(user, invoice):
        messages.error(request, "Nu ai acces la această factură.")
        return redirect("dashboard:orders_list")

    order = invoice.order

    # Dacă nu avem WeasyPrint instalat, nu are sens să încercăm PDF
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
            "order": order,
            "platform_name": "Snobistic",
            "company_vat": getattr(settings, "SNOBISTIC_COMPANY_VAT", "RO00000000"),
        },
        request=request,
    )

    # Generăm PDF
    response = HttpResponse(content_type="application/pdf")
    filename = f"Factura-{invoice.invoice_number or invoice.pk}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    HTML(
        string=html_string,
        base_url=request.build_absolute_uri("/"),
    ).write_pdf(response)

    return response
