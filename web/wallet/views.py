# wallet/views.py
from __future__ import annotations

from decimal import Decimal
import csv

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import TopUpForm, WithdrawForm
from .models import WalletTransaction, WithdrawalRequest
from .services import credit_wallet, debit_wallet, get_or_create_wallet_for_user

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


@login_required
def wallet_home(request):
    wallet = get_or_create_wallet_for_user(request.user)
    txs = wallet.transactions.all().order_by("-created_at")[:10]
    withdrawals = wallet.withdrawals.all().order_by("-created_at")[:5]

    # ✅ rămânem pe wallet.html
    return render(
        request,
        "wallet/wallet.html",
        {"wallet": wallet, "txs": txs, "withdrawals": withdrawals},
    )


@login_required
def wallet_transactions(request):
    wallet = get_or_create_wallet_for_user(request.user)
    qs = wallet.transactions.all().order_by("-created_at")

    period = request.GET.get("period", "all")
    now = timezone.now()

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(created_at__gte=start)
    elif period == "monthly":
        qs = qs.filter(created_at__year=now.year, created_at__month=now.month)
    elif period == "yearly":
        qs = qs.filter(created_at__year=now.year)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="wallet_{period}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Dată", "Tip", "Direcție", "Metodă", "Sumă", "Sold după", "External ID"])

        for tx in qs:
            writer.writerow(
                [
                    tx.created_at.strftime("%Y-%m-%d %H:%M"),
                    tx.get_tx_type_display() if hasattr(tx, "get_tx_type_display") else tx.tx_type,
                    tx.get_direction_display() if hasattr(tx, "get_direction_display") else tx.direction,
                    tx.method,
                    tx.amount,
                    tx.balance_after,
                    tx.external_id,
                ]
            )
        return response

    # limit rezonabil în UI (poți crește / adăuga pagination mai târziu)
    txs = qs[:200]
    return render(
        request,
        "wallet/wallet_transactions.html",
        {"wallet": wallet, "txs": txs, "period": period},
    )


@login_required
def wallet_topup(request):
    wallet = get_or_create_wallet_for_user(request.user)

    if request.method == "POST":
        form = TopUpForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            method = form.cleaned_data["method"]

            if method != "card":
                messages.error(request, "Momentan poți încărca wallet-ul doar cu cardul (Stripe).")
                return redirect("wallet:topup")

            if not stripe.api_key:
                messages.error(request, "Plata online nu este disponibilă momentan (config Stripe lipsă).")
                return redirect("wallet:home")

            currency_code = getattr(settings, "SNOBISTIC_CURRENCY", "RON").lower()

            try:
                session = stripe.checkout.Session.create(
                    mode="payment",
                    customer_email=request.user.email,
                    line_items=[
                        {
                            "price_data": {
                                "currency": currency_code,
                                "product_data": {"name": "Încărcare Wallet Snobistic"},
                                "unit_amount": int((amount * Decimal("100")).quantize(Decimal("1"))),
                            },
                            "quantity": 1,
                        }
                    ],
                    metadata={
                        "purpose": "wallet_topup",
                        "user_id": str(request.user.id),
                        "amount": str(amount),
                        "currency": currency_code,
                    },
                    automatic_payment_methods={"enabled": True},
                    success_url=(request.build_absolute_uri(reverse("wallet:topup_success")) + "?session_id={CHECKOUT_SESSION_ID}"),
                    cancel_url=request.build_absolute_uri(reverse("wallet:topup_cancel")),
                )
            except Exception as e:
                messages.error(request, f"Eroare la inițierea plății: {e}")
                return redirect("wallet:home")

            return redirect(session.url, code=303)
    else:
        form = TopUpForm()

    return render(request, "wallet/wallet_topup.html", {"form": form, "wallet": wallet})


@login_required
def wallet_topup_success(request):
    messages.success(request, "Plata a fost inițiată. Soldul se actualizează după confirmarea Stripe (webhook).")
    return redirect("wallet:home")


@login_required
def wallet_topup_cancel(request):
    messages.info(request, "Încărcarea wallet-ului a fost anulată.")
    return redirect("wallet:home")


@login_required
def wallet_withdraw(request):
    wallet = get_or_create_wallet_for_user(request.user)

    if request.method == "POST":
        form = WithdrawForm(request.POST, wallet=wallet)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            iban = form.cleaned_data["iban"]

            try:
                with transaction.atomic():
                    debit_wallet(
                        user=request.user,
                        amount=amount,
                        tx_type=WalletTransaction.Type.WITHDRAW,
                        method="bank",
                        external_id=f"withdraw:{request.user.id}:{iban}:{amount}",
                        note=f"Retragere către IBAN {iban}",
                        meta={"iban": iban},
                    )
                    WithdrawalRequest.objects.create(wallet=wallet, amount=amount, iban=iban)
            except Exception as e:
                messages.error(request, str(e))
                return redirect("wallet:withdraw")

            messages.success(request, f"Retragere de {amount} {wallet.currency} inițiată către IBAN {iban}.")
            return redirect("wallet:home")
    else:
        form = WithdrawForm(wallet=wallet)

    return render(request, "wallet/wallet_withdraw.html", {"form": form, "wallet": wallet})


@csrf_exempt
def stripe_webhook_wallet(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    if not endpoint_secret:
        return HttpResponseBadRequest("Stripe webhook secret missing")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {}) or {}

    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {}) or {}
        purpose = metadata.get("purpose")
        if purpose != "wallet_topup":
            return HttpResponse(status=200)

        payment_intent_id = data.get("payment_intent") or ""
        user_id = metadata.get("user_id")
        amount_str = metadata.get("amount")

        if not user_id or not amount_str:
            return HttpResponse(status=200)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return HttpResponse(status=200)

        try:
            amount = Decimal(amount_str)
        except Exception:
            return HttpResponse(status=200)

        credit_wallet(
            user=user,
            amount=amount,
            tx_type=WalletTransaction.Type.TOP_UP,
            method="card",
            external_id=payment_intent_id or data.get("id") or "",
            note="Încărcare wallet (Stripe)",
            meta={"session_id": data.get("id"), "payment_intent": payment_intent_id},
        )

        return HttpResponse(status=200)

    return HttpResponse(status=200)
