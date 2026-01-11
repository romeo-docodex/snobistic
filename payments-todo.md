Mai jos e auditul pentru app-ul **`payments`**, cu focus explicit: **să scoatem complet orice ține de Wallet** (pentru că vei avea `wallet` app separat).

---

## ✅ CE AVEM (în codul tău acum)

### 1) Stripe Checkout pentru comenzi

* `payment_confirm()` creează `Payment` (provider Stripe), inițiază `stripe.checkout.Session`.
* `stripe_webhook()` marchează `Payment` ca SUCCEEDED / FAILED / CANCELED și cheamă `order.mark_as_paid()` etc.
* Pagini: `payment_success`, `payment_failure`.

### 2) Model `Payment` + `Refund`

* `Payment` are provider/status, Stripe session + payment_intent, `raw_response`, calcule “minor units”.
* `Refund` suportă “refund total/parțial”, cu status și opțional Stripe refund id.

### 3) (❌ Problematic) Wallet în interiorul payments

Ai acum în `payments`:

* `Wallet`, `WalletTransaction`
* top-up + withdraw views (`wallet_topup`, `wallet_withdraw`)
* `charge_order_from_wallet()`
* `refund_payment(... to_wallet=True ...)`
* `signals.py` care creează wallet la user nou
* URL-uri /plati/portofel/...

Asta înseamnă că app-ul “payments” este de fapt **payments + wallet + ledger**, iar tu vrei **wallet separat**.

---

## ❌ CE LIPSEȘTE (raportat la “scope-ul corect” al payments-ului)

### A) Separarea corectă Payments vs Wallet (blocker de arhitectură)

* `payments` trebuie să gestioneze:

  * inițiere plăți (Stripe / COD),
  * confirmare rezultat (webhooks),
  * refund către procesator,
  * dispute/chargeback mapping,
  * (opțional) evidență escrow ca “stare” legată de order/payment.
* `wallet` trebuie să gestioneze:

  * solduri, tranzacții, top-up, withdraw,
  * ledger intern, credit/debit, idempotency pe ledger,
  * payout către vânzător etc.

**În forma actuală, payments încalcă direct cerința ta**: există mult cod wallet în el.

### B) Evidență clară pentru “breakdown” financiar (buyer protection + comision platformă + net seller)

În payments nu ai încă:

* un “fee breakdown” persistent (ex: `buyer_protection_fee`, `platform_fee`, `seller_net`, `shipping`, etc.),
* sursă de adevăr pentru calcul (versionare / snapshot la momentul plății),
* auditabilitate (de ce a fost taxa X?).

### C) Event log pentru webhook-uri (idempotency + audit)

Lipsește o masă tip:

* `PaymentWebhookEvent` / `ProviderEvent`

  * `provider`, `event_id`, `event_type`, `received_at`, `payload`, `processed_ok`, `error`
  * unică pe `event_id` pentru idempotency robust.

Acum idempotency e parțial (verifici status), dar nu ai “receipt” de eveniment.

### D) COD / ramburs “as a first-class flow”

Ai Provider `CASH`, dar nu există:

* model / status pentru “încasat de la curier”,
* confirmare încasare (manual/admin sau webhook curier),
* reconciliere și taxe extra ramburs.

---

## 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (și ce aș schimba concret)

### 1) **P0 — Scoate TOT wallet-ul din payments**

**Țintă:** `payments` să nu conțină *niciun* model/view/form/url/signal/service despre wallet.

**De mutat în `wallet` app (100%)**

* `Wallet`, `WalletTransaction`
* `TopUpForm`, `WithdrawForm`
* `wallet_topup`, `wallet_withdraw`, `wallet_topup_success/cancel`
* `payments/signals.py` (create wallet on user create)
* orice URL `/plati/portofel/...`
* `charge_order_from_wallet()`
* partea “credit to wallet” din refund

**De eliminat din Payment model**

* `Provider.WALLET`
* `wallet = models.ForeignKey("Wallet", ...)`

**De eliminat din Refund model**

* `to_wallet` (e wallet-specific; va fi responsabilitatea `wallet` app)

---

### 2) **P0 — Raw response Stripe: nu salva obiecte Stripe direct**

În `payment_confirm()` faci:

```py
payment.raw_response = session
```

`session` poate să nu fie JSON serializabil. Corect e să salvezi:

* `dict(session)` sau `session.to_dict()` (în funcție de versiune),
* sau doar sub-cheile utile + un “payload” minim.

Recomandare: păstrezi payload complet **doar în webhook event log**, nu în Payment.

---

### 3) **P0 — Webhook: procesare robustă + separare pe handler-e**

Acum ai mult logic într-o singură funcție.

Recomand:

* `payments/providers/stripe/handlers.py` (checkout completed / expired / failed / dispute)
* `payments/webhooks.py` (router)
* `PaymentWebhookEvent` pentru idempotency și audit.

Plus:

* Nu te baza exclusiv pe metadata pentru lucruri sensibile fără cross-check (order_id/payment_id mapping în DB).

---

### 4) **P1 — Payments trebuie să emită “events”, nu să facă ledger**

Cum păstrezi integrarea cu `wallet` fără să ai wallet în payments:

* În `payments` emiți evenimente (Django signals) gen:

  * `payment_succeeded(order_id, payment_id, amount, currency)`
  * `refund_succeeded(order_id, payment_id, amount, currency)`
  * `escrow_releasable(order_id, seller_id, amount_net, currency)`

* `wallet` app ascultă aceste semnale și creează tranzacții în ledger.

Așa `payments` rămâne curat, iar “transferul către wallet” există ca integrare, nu ca dependență.

---

### 5) **P1 — Fee breakdown: snapshot la momentul plății**

Pentru Buyer Protection + comision platformă + “Tu primești”:

* fie adaugi câmpuri în `Payment`:

  * `buyer_protection_fee`, `platform_fee`, `seller_net`, `gross_items_total`, etc.
* fie un model separat `PaymentBreakdown(payment, ...)`.

Important: să fie **înghețat** la momentul inițierii plății, ca să nu se schimbe dacă user-ul își schimbă tier-ul după.

---

### 6) **P1 — Provider enum corect + clar**

În payments, aș păstra:

* `STRIPE` (card)
* `CASH_ON_DELIVERY` (ramburs) – dacă îl gestionezi aici
* (opțional) `BANK_TRANSFER`

Dar **nu** `WALLET`.

---

### 7) **P2 — Success page: confirmare reală**

Acum `payment_success` doar afișează un template și verifică `order.payment_status`.
Ideal:

* ia `session_id` din querystring,
* validează că session-ul aparține payment-ului,
* afișează “paid” doar după ce webhook a confirmat (sau după o verificare Stripe API, dacă vrei fallback).

---

## Verdict rapid (pe cerința ta)

✅ Stripe order payments există și e ok ca direcție.
❌ App-ul `payments` este contaminat masiv cu Wallet. Trebuie separat complet.
🛠️ După separare, payments trebuie întărit cu: event log, idempotency, fee breakdown snapshot, handlers curate.

---

Dacă vrei, următorul pas îl facem “enterprise-grade” fără să ne întindem:

1. îți propun structura nouă de fișiere pentru `payments` (curată, wallet-free)
2. îți spun exact ce se mută în `wallet` app (listă + dependințe)
3. îți dau checklist de migrare (migrations + import paths + admin + urls).
