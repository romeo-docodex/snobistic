# authenticator/views.py
from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from catalog.models import Product
from .forms import AuthUploadForm
from .models import AuthRequest
from .services import provider_client
from .services.webhook_security import verify_hmac_signature


def authenticate_product_view(request, slug=None):
    """
    Pagina “Autentificare Produse”.
    - poate fi generică
    - sau pornită dintr-un produs: /authenticator/produs/<slug>/
    """
    product = None
    if slug:
        product = get_object_or_404(Product, slug=slug)
    else:
        pid = request.GET.get("product")
        if pid:
            try:
                product = Product.objects.filter(pk=int(pid)).first()
            except Exception:
                product = None

    if request.method == "POST":
        form = AuthUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            req = form.save_request()

            # dacă vine din product page, forțează legarea (hidden input poate lipsi)
            if product and not req.product_id:
                req.product = product
                req.save(update_fields=["product"])

            # trimite către provider (sync)
            try:
                provider_client.submit_auth_request(req)
                messages.success(request, "Cererea a fost trimisă cu succes! O vei vedea în istoric.")
            except Exception as e:
                req.status = AuthRequest.Status.PENDING
                req.failure_reason = str(e)
                req.save(update_fields=["status", "failure_reason"])
                messages.warning(
                    request,
                    "Cererea a fost înregistrată, dar nu s-a putut trimite către provider. "
                    "Va fi procesată manual / reîncercată.",
                )

            if request.user.is_authenticated:
                return redirect("authenticator:authenticate_history")

            # guest -> status page by token
            return redirect("authenticator:authenticate_status", token=req.public_token)
    else:
        initial = {}
        if product:
            initial["product"] = product.pk
            # prefill from product when possible
            if getattr(product, "display_brand", ""):
                initial["brand_text"] = product.display_brand
            initial["model_text"] = product.title
        form = AuthUploadForm(user=request.user, initial=initial)

    return render(
        request,
        "authenticator/authenticate_product.html",
        {
            "form": form,
            "product": product,
        },
    )


@login_required
def authenticate_history_view(request):
    history = AuthRequest.objects.filter(user=request.user).select_related("product").order_by("-submitted_at")
    return render(request, "authenticator/authenticate_history.html", {"history": history})


def authenticate_status_view(request, token):
    """
    Guest status page. Anyone with token can see the request.
    """
    req = get_object_or_404(AuthRequest, public_token=token)
    return render(request, "authenticator/authenticate_status.html", {"req": req})


def _redirect_to_certificate(req: AuthRequest):
    """
    Prefer file if present; fallback to url.
    """
    if req.certificate_file:
        return redirect(req.certificate_file.url)
    if req.certificate_url:
        return redirect(req.certificate_url)
    messages.error(req_request := None, "Certificatul nu este disponibil încă.")  # no-op guard
    return redirect("authenticator:authenticate_product")


@login_required
def download_certificate_view(request, pk):
    req = get_object_or_404(AuthRequest, pk=pk, user=request.user, status=AuthRequest.Status.SUCCESS)
    if not (req.certificate_file or req.certificate_url):
        messages.error(request, "Certificatul nu este disponibil încă.")
        return redirect("authenticator:authenticate_history")
    return _redirect_to_certificate(req)


def download_certificate_by_token_view(request, token):
    req = get_object_or_404(AuthRequest, public_token=token, status=AuthRequest.Status.SUCCESS)
    if not (req.certificate_file or req.certificate_url):
        messages.error(request, "Certificatul nu este disponibil încă.")
        return redirect("authenticator:authenticate_status", token=token)
    return _redirect_to_certificate(req)


@csrf_exempt
def webhook_view(request, provider: str):
    """
    Endpoint unde provider-ul trimite rezultatul.
    Semnătura se verifică prin header "X-Signature" (HMAC SHA256 hex).
    Payload-ul trebuie să conțină provider_reference + verdict + certificate_url (opțional).

    URL: /authenticator/webhook/<provider>/
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    secret = getattr(settings, "AUTH_PROVIDER_WEBHOOK_SECRET", "")
    signature = request.headers.get("X-Signature", "")

    body = request.body or b""
    if secret:
        if not verify_hmac_signature(secret=secret, body=body, signature=signature):
            return HttpResponseForbidden("Invalid signature")

    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    provider_reference = str(data.get("provider_reference") or data.get("reference") or data.get("id") or "").strip()
    if not provider_reference:
        return HttpResponseBadRequest("Missing provider_reference")

    req = AuthRequest.objects.filter(provider_reference=provider_reference).select_related("product").first()
    if not req:
        return HttpResponseBadRequest("Unknown provider_reference")

    verdict_raw = str(data.get("verdict") or "").strip().lower()
    verdict_map = {
        "authentic": AuthRequest.Verdict.AUTHENTIC,
        "real": AuthRequest.Verdict.AUTHENTIC,
        "verified": AuthRequest.Verdict.AUTHENTIC,
        "fake": AuthRequest.Verdict.FAKE,
        "not_authentic": AuthRequest.Verdict.FAKE,
        "counterfeit": AuthRequest.Verdict.FAKE,
        "inconclusive": AuthRequest.Verdict.INCONCLUSIVE,
        "unknown": AuthRequest.Verdict.INCONCLUSIVE,
        "pending": AuthRequest.Verdict.PENDING,
    }
    verdict = verdict_map.get(verdict_raw, AuthRequest.Verdict.INCONCLUSIVE)

    certificate_url = str(data.get("certificate_url") or data.get("certificate") or "").strip()
    failure_reason = str(data.get("failure_reason") or "").strip()

    req.finalize(
        verdict=verdict,
        certificate_url=certificate_url,
        payload=data,
        failure_reason=failure_reason,
    )
    req.save()

    # sync to product badge if linked
    provider_client.apply_result_to_product(req)

    return HttpResponse("OK")
