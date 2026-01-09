Perfect — ai dat deja **tot nucleul din `orders`** (models/views/urls/forms/signals/apps/admin + trust_hooks). Pot să fac auditul acum.

## ✅ Ce avem (din codul tău actual)

* **Order + OrderItem** cu:

  * buyer, address (livrare), shipping_method
  * statusuri: payment (pending/paid), shipping (pending/shipped/cancelled), escrow (pending/held/released/disputed)
  * totals: subtotal, buyer_protection_fee_amount, shipping_cost, seller_commission_amount, total
* **Create order din cart** (`Order.create_from_cart`) compatibil cu **qty=1 policy** (creează `OrderItem.quantity=1` și subtotal = sum(price))
* **Escrow payout** pe selleri (`_payout_sellers_from_escrow`) + release logic condiționat de shipped + fără retur pending
* **ReturnRequest** la nivel de comandă (reason + status pending/approved/rejected)
* **Views**:

  * list buyer (seller redirect către dashboard)
  * detail cu gating buyer/seller/staff
  * export CSV seller
  * retur list buyer/seller
  * create return request (buyer) + mark escrow disputed
  * invoice view cu gating în funcție de tip și starea comenzii
* **Signals**: la crearea ReturnRequest → marchează escrow disputed
* **Admin**: list/order actions + release escrow action

## ❌ CE LIPSEȘTE (față de „scope”-ul tău descris)

### 1) Status machine complet pentru comandă

Tu ai acum doar:

* payment: pending/paid
* shipping: pending/shipped/cancelled
* escrow: pending/held/released/disputed

În “scope” ai menționat: creată, plătită, în curs expediere, livrată, finalizată, anulată + eșuată la plată etc.
**Lipsesc**:

* payment: failed/cancelled/refunded/chargeback (măcar failed/refunded)
* shipping: delivered/returned/in_transit
* order lifecycle: completed/cancelled_by_buyer/cancelled_by_seller (sau un `status` separat)

### 2) Retururi “serioase”

Scope-ul tău cere:

* retur pe comandă **sau produs**
* motiv + **poze**
* status: deschis/aprobat/respins/rambursat
* reguli termene PF/PJ + marketplace vs licitații

Acum ai doar:

* retur pe comandă (nu pe item)
* fără poze
* fără “refunded”
* fără termen / eligibilitate / PF vs PJ / auction rules

### 3) Snapshot/immutability pentru date de comandă

În `OrderItem` referința e către `Product` live + `price`.
Lipsesc snapshot-uri utile ca să nu-ți “muți istoria” dacă produsul se schimbă:

* titlu produs, sku, seller_id, imagine, variantă/size, etc. (minim titlu + sku + seller_id)

### 4) Discount/cupon în Order

În checkout tu aplici cupon în cart și calculezi totals, dar în `Order` nu stochezi:

* coupon_code / coupon_id
* discount_amount / discount_percent
* subtotal_before_discount
  => factura / audit / dispute nu vor avea “ce s-a aplicat”.

### 5) Billing address separată

Scope: “adresa de livrare și adresa de facturare”
În model ai doar `address` (livrare).

---

## 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (P0/P1/P2)

### P0 — BUG CRITIC: trust_hooks sunt apelate greșit

În `orders/services/trust_hooks.py` funcțiile sunt definite așa:

* `on_order_paid(order_id: int)`
* `on_escrow_released(order_id: int)`

Dar în `Order.mark_as_paid()` și `Order.release_escrow()` tu le apelezi cu **self**:

```py
on_order_paid(self)
on_escrow_released(self)
```

Asta va crăpa (sau va produce efecte greșite).

✅ Fix corect:

* `on_order_paid(self.id)`
* `on_escrow_released(self.id)`

### P0 — DUBLARE logică: escrow disputed la retur

Ai **două** mecanisme care fac același lucru:

* în `order_return_request_view()` → `order.mark_escrow_disputed()`
* în `signals.py` la post_save ReturnRequest created → `instance.order.mark_escrow_disputed()`

Recomand să păstrezi **doar signal-ul** (mai robust, centralizat) și să scoți din view ca să nu faci update de 2 ori.

### P0 — Invoice pentru multi-seller e incorect

`invoice_view()` alege seller-ul așa:

```py
seller = order.items.first().product.owner
```

Dacă un order are produse de la **mai mulți selleri**, asta generează facturi greșite.

Ai două opțiuni:

1. **Restricție** (quick fix): dacă există >1 seller distinct → invoice seller-only blocat (doar staff).
2. **Corect enterprise**: facturi **per seller** (invoice_type + seller_id) + sume calculate per seller (subtotal/commission etc).

În același loc, și `seller_commission_amount` e “la nivel de comandă”, dar payout-ul îl calculezi per seller. E ok ca idee, dar trebuie reconciliat corect.

### P1 — Securitate / scoping mai curat în `order_detail_view`

Acum faci:

* iei comanda by pk
* după aia verifici permisiuni

E ok, dar “enterprise hardening” ar fi:

* să construiești queryset-ul accesibil direct (buyer OR seller-items OR staff) și să faci `get_object_or_404` pe el (mai puțin risc de leak/IDOR).

### P1 — `OrderAddressForm` pare nefolosit

Există în `orders/forms.py`, dar flow-ul real de checkout e în `cart` cu `CheckoutForm`.
Ori îl elimini, ori îl integrezi.

### P1 — ReturnRequest: reguli minime lipsă

Chiar și înainte să faci PF/PJ complet, îți trebuie:

* să ceri retur doar dacă `payment_status == PAID` (nu doar shipped)
* să limitezi la un return pending per order per buyer (ai deja)
* să pui `processed_at` când status devine approved/rejected (momentan nu există logică)

### P2 — Constrângeri DB / consistență

* `OrderItem` nu are constraint `unique(order, product)`; dacă ajungi să creezi de 2 ori aceeași linie, faci duplicate (mai ales dacă în viitor ai retry-uri).
* Indexuri utile: `Order(buyer, created_at)`, `Order(payment_status)`, `Order(escrow_status)`, `ReturnRequest(order, status)`.

---

## Fix-uri imediate pe care ți le-aș face “dintr-o trecere” (fără să îți schimb business logic)

1. **Repar trust_hooks calls** în `Order.mark_as_paid` și `Order.release_escrow` (P0)
2. **Elimin dublarea** escrow disputed (P0)
3. **Pun gard** pentru multi-seller invoices (P0 quick safety)
4. **Hardening** pe `order_detail_view` queryset scoping (P1)
5. (opțional) **unique constraint** pe `OrderItem(order, product)` (P2)

---

Dacă vrei, în următorul mesaj îți dau direct **fișierele modificate complet** (minim: `orders/models.py`, `orders/views.py`, `orders/signals.py`) cu fix-urile P0+P1 de mai sus, ca să le poți copia/paste și rula migrarea unde e cazul.
