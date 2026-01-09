Perfect — dacă **quantity nu există** (mereu 1, produse unice), atunci auditul se simplifică și devine mai “marketplace-fashion corect”.

Mai jos ai planul **actualizat** în formatul fix.

---

## ✅ CE AVEM

### 1) Scope & flow general

* Coș **DB-based** pentru user (`Cart.user` OneToOne) + coș pentru vizitatori pe `session_key`.
* Add în coș cu **gating seller**: seller nu poate cumpăra decât dacă are buyer + `seller_can_buy`.
* Pagina de coș `cart_view` + mini-cart/offcanvas via `cart_offcanvas_partial`.
* Checkout cu:

  * verificare coș gol,
  * verificare adresă,
  * estimare transport (service extern),
  * opțiuni: wallet / card / ramburs,
  * pre-check wallet înainte de a crea comanda,
  * `Order.create_from_cart(...)`.

### 2) Modele

* `Cart` cu `coupon`, `session_key` + `UniqueConstraint` pentru `session_key` când nu e null.
* `CartItem` cu `unique_together(cart, product)` (corect pentru produse unice).
* `Coupon` simplu (cod + procent + activ).

### 3) Utils

* `get_cart` vs `get_or_create_cart` (bun, clar).
* Suport guest DB-cart prin `session_key`.
* `merge_session_cart_to_user(...)` (DB guest + legacy dict).

### 4) Admin + context

* Admin OK (inline items).
* Context processor cu `cart_items_count` (badge în header).

---

## ❌ CE LIPSEȘTE (actualizat cu qty=1)

### P0 — funcționalități promise dar neimplementate complet

* **Eliminare produs “curată” (endpoint dedicat)**:

  * acum ștergerea e “înghesuită” în `cart_view` prin `action` / `remove_XX`
  * offcanvas-ul modern are nevoie de **`cart_remove(item_id)` POST** + răspuns JSON (count/total/html).
* **Sumarul coșului complet la nivel de app**:

  * buyer protection fee există doar “ad-hoc” în checkout
  * estimarea transport lipsește din `cart_view` (e doar în checkout)
  * nu există un “calculator standard” (subtotal/fee/shipping/total) reutilizat în cart + offcanvas + checkout.

### P0 — Support pentru “produse câștigate la licitații”

În `cart` nu există încă:

* concept de “auction win item” / “reserved item”
* reguli de expirare / lock / exclusivitate
* import/transfer din `auctions` către coș/comandă
  ➡️ Dacă asta rămâne scope, trebuie un tip de item (vezi la “Trebuie îmbunătățit”).

### P1 — produs / robustețe

* **Cupoane**: fără expiry, usage limit, min order, max discount, validatori discount 0–100, unicitate case-insensitive garantată.
* **Prevent buy your own product**: `cart_add` nu blochează explicit produsele proprii.
* **Teste** lipsă (add/remove, gating seller, coupon, wallet insufficient, COD eligibility, merge carts).
* **Confirmarea hook-ului de merge la login** (ai funcția, dar auditul trebuie să bifeze că e apelată sigur).

---

## 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (prioritizat pentru qty=1)

### P0 — core bug/edge-cases

* **`checkout_view` folosește `get_object_or_404(Cart, user=request.user)`**
  → user autentic fără cart = 404 (UX prost).
  ✅ Fix: `cart = get_or_create_cart(request)` (și te asiguri că e al userului).
* **`cart_view` creează cart la GET** (prin `get_or_create_cart`)
  → poate umple DB cu coșuri goale (bots/crawlers).
  ✅ Fix: pe GET folosești `get_cart(request)`; creezi cart doar la POST / add.
* **`cart_add`**:

  * pune `@require_POST`
  * dacă item există deja: **nu crești quantity** (pentru că nu există), doar returnezi ok + mesaj (“Produsul este deja în coș.”).
* **Disponibilitate/rezervare produs** (marketplace):

  * când un produs ajunge în coș, în practică trebuie o regulă:

    * ori “soft” (mai mulți pot avea în coș, dar primul la plată câștigă),
    * ori “hard reserve” (se blochează temporar).
      ✅ Dacă vrei corect pentru unice, recomand: **hard reserve cu expirare** (vezi P1).

### P0 — consistență calcule (sumar coș)

* Mută într-un loc comun (ideal `Cart` sau `cart/services.py`) calculele:

  * subtotal (după cupon),
  * buyer protection fee (percent din settings),
  * shipping estimate (lazy),
  * total estimat.
* Folosești același “calculator” în:

  * `cart_view`,
  * `cart_offcanvas_partial`,
  * `checkout_view`.

### P1 — model cleanup: eliminare `quantity`

* **Scoți `quantity` din `CartItem`** + migrare.
* Ajustezi:

  * `Cart.get_subtotal()` să fie `sum(product.price)` fără multiplicare
  * `context_processor` să folosească `cart.items.count()` (nu Sum(quantity))
  * `cart_add` să nu mai scrie quantity
  * orice template care arată qty.

### P1 — endpoints curate pentru UX modern

* Endpoint-uri clare, POST-only:

  * `cart_add(product_id)`
  * `cart_remove(item_id)`
  * `cart_clear()` (opțional)
  * `cart_offcanvas_partial()` (GET)
* Pentru offcanvas: răspuns JSON cu:

  * `count`
  * `cart_total`
  * `html` (partial rerender)

### P1 — hardening cupoane

* `Coupon`: `valid_from`, `valid_to`, `max_uses`, `uses`, `min_order_amount`, validator 0–100, unicitate case-insensitive.
* UI: “Remove coupon”.

### P1 — securitate & comportament

* Evită redirect bazat pe `HTTP_REFERER` (poate fi falsificat) → redirect intern sigur.
* Nu mai înghiți `except Exception: pass` la remove → tratezi excepțiile strict.
* Rate-limit simplu pe add/remove (anti spam).

### P1 — produse unice: rezervare (recomandat)

Aici ai de ales o strategie:

**Variantă A (simplă, soft):**

* produs poate fi în mai multe coșuri
* la `Order.create_from_cart` verifici încă o dată că produsul e disponibil și nu e vândut

**Variantă B (corect marketplace): hard reserve**

* Când e adăugat în coș: setezi “reserved_until” pe produs sau pe un model de rezervare
* Cron/cleanup: expiră rezervările
* La checkout: confirmi rezervarea → finalizezi vânzarea

### P2 — performanță & query hygiene

* `cart.items.select_related("product")` în view (și imagini dacă template cere).
* “related_products” ok.

---

## Rezultat practic (ce se schimbă în planul tău)

* ❌ Dispare complet “update quantity” din scope.
* ✅ În locul lui intră:

  * “add = idempotent”
  * remove curat
  * rezervare produs (soft/hard)
  * totals calculator unificat

Dacă vrei, următorul pas logic e să-ți dau “todo plan” pe fișiere (exact ce atingi) pentru:

1. eliminarea `quantity` + migrare,
2. endpoints curate add/remove,
3. totals calculator comun,
4. update context_processor + templates.
