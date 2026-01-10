Mai jos e audit-ul pentru **app `auctions`**, pe cerințele tale (“Ce face”) + ce văd în codul pe care l-ai lipit.

---

## ✅ CE AVEM (bifat / implementat)

### 1) Modelare licitație (core)

* **Auction** legată 1-1 de **Product** (`OneToOneField related_name="auction"`).
* Câmpuri cheie există:

  * **start_price**, **reserve_price** (nullable), **current_price**
  * **start_time**, **end_time**, **duration_days**
  * **status**: PENDING / ACTIVE / ENDED / CANCELED
  * **winner**, **winning_bid**, **payment_due_at**
  * timestamps: created/updated + canceled_at/ended_at
* Reguli de validare:

  * `reserve_price >= start_price` (și `CheckConstraint` în DB + `clean()`)
  * durata > 0, increment > 0, end_time > start_time (în `clean()`)

### 2) Increment minim (ex. +10%)

* `min_increment_percent` + `min_next_bid()` calculează pragul următor (cu quantize + minimum 0.01).

### 3) Bids (oferte)

* Model **Bid**:

  * `auction`, `user`, `amount`, `placed_at`
  * index-uri utile (auction + amount + placed_at, user + placed_at)
* Validare bid:

  * în **BidForm** (UX) + în **Auction.place_bid** (source of truth, atomic)
  * anti self-bid (seller/owner)
  * verificare status/timp + prag minim

### 4) Plasare bid atomică (corect pentru concurență)

* `place_bid()` folosește `transaction.atomic()` + `select_for_update()` pe Auction → ok (nu apar “race conditions” la current_price).

### 5) Final licitație + stabilire câștigător + “comandă”

* `settle_if_needed()` + `_end_and_settle()`:

  * dacă top bid >= reserve → setează winner + winning_bid + current_price + payment_due_at
  * creează `AuctionOrder` (PENDING_PAYMENT) cu `payment_due_at`
* “Fereastra de plată” există: `payment_window_hours`

### 6) Retur licitații (3 zile, doar neconform)

* `AuctionReturnRequest`:

  * `RETURN_WINDOW_DAYS = 3`
  * reason only: `NOT_AS_DESCRIBED`
  * `clean()` validează deadline + reason

### 7) Wizard create/edit pentru licitații

* **Create wizard** creează Product + imagini + Auction (PENDING) și activează dacă start_time <= now.
* **Edit wizard** permite edit doar pentru PENDING (corect).
* Handling imagini: min 4 poze enforced (și pentru edit, pe baza pozelor existente).
* Seller gating: `_user_is_seller()` (profile.role_seller cu fallback is_seller) – bine.

### 8) Views / flow basic

* List cu filtre pe state (active/upcoming/ended/canceled).
* Detail + POST bid.
* Start auction pentru produs existent: creează Auction PENDING și te trimite în wizard_edit.
* Close/cancel pentru owner (creator=request.user).
* Expirare “lightweight” în request: `_expire_due_auctions()` rulează înainte de list/detail/bid.

---

## ❌ CE LIPSEȘTE (ca să fie “enterprise-grade” pe cerințele tale)

### P0 — obligatoriu dacă vrei comportament corect în prod

1. **Scheduler real** pentru:

   * activare automată când `start_time` devine “acum” (pentru licitații viitoare)
   * settlement/expiry periodic (nu doar când cineva deschide o pagină)
   * expirarea plății câștigătorului (`AuctionOrder.is_payment_overdue()` există, dar nu e folosit nicăieri)
   * acțiune după payment overdue: `EXPIRED` + ce se întâmplă cu produsul (relist / offer to 2nd / cancel)
2. **Integrare cu checkout/payments/orders**

   * acum creezi `AuctionOrder` intern, dar nu e conectat clar la fluxul de plată (`payments`) și nici la `orders` (dacă există în proiect).
   * cerința ta zice “creează o comandă pentru câștigător” — momentan e “comandă de licitație”, nu “Order” în sistemul de comenzi.
3. **Return flow complet**

   * ai modelul de request, dar lipsesc:

     * views/urls/templates pentru creare request, aprobare/respingere, “closing”
     * policy enforcement legată de status (ex: retur doar dacă order PAID/DELIVERED etc.)
     * dovezi / atașamente / dispute notes (dacă vrei nivel marketplace)

### P1 — important

4. **Notificări**

   * winner/outbid/auction ending soon/payment due/auction canceled etc. (email + in-app)
5. **Admin / dashboard tooling**

   * nu văd `admin.py` / management views: moderare licitații, forțare settlement, anulare, audit.
6. **Test coverage**

   * unit tests pentru: min increment, concurență bids, settlement, reserve logic, edit restrictions, payment overdue.

---

## 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (riscuri / finețuri)

### 1) Cancel / close nu “repară” starea produsului

* `Auction.cancel()` doar marchează Auction CANCELED, dar **nu sincronizează Product**.

  * Dacă produsul rămâne `sale_type="AUCTION"` după anulare, în catalog poate apărea ca listing de licitație anulată.
* Recomandare:

  * definește policy clar:

    * fie produsul revine la `sale_type="FIXED"` / `is_active=False`
    * fie rămâne AUCTION dar ascuns/archived
  * aplică aceeași sincronizare și în `close_auction_view` dacă licitația se încheie fără winner.

### 2) Expirarea “în request” e OK ca fallback, dar costisitoare

* `_expire_due_auctions()` în fiecare request poate introduce DB load.
* Păstrează-l ca “safety net”, dar în prod trebuie **cron/celery beat**.

### 3) Lipsește policy pentru “bids exist” la cancel

* În `cancel_auction_view` permiți anularea indiferent de bids (în cod nu există blocaj).
* De obicei marketplace-urile:

  * blochează cancel după primul bid, sau
  * permit doar înainte de start, sau
  * permit dar cu penalități/log/audit.

### 4) Constrângeri DB suplimentare (hardening)

Ai validări în `clean()`, dar la nivel DB ar merita:

* `start_price > 0`, `duration_days >= 1`, `min_increment_percent >= 1`, `payment_window_hours >= 1`
* pentru `AuctionOrder.amount` să fie consistent cu `auction.winning_bid.amount` (măcar în cod/signal/save)

### 5) “Anti-sniping” (opțional, dar foarte recomandat)

* Dacă vrei licitații “ca lumea”: la bid în ultimele X minute → extinzi end_time cu Y minute.

### 6) ReturnRequest.clean: timing vs status

* acum verifici “3 zile de la order.created_at”.
* în practică, returul e mai logic raportat la **livrare** (sau măcar la `paid_at`), altfel omul poate pierde returul dacă plătește târziu sau dacă livrarea durează.

---

## Verdict rapid

* **Core licitații + bids + settlement + payment window + retur policy (la nivel model)**: ✅ bine implementat.
* Pentru “prod marketplace” îți lipsesc **automatizările (scheduler)** + **integrarea cu checkout/orders** + **workflow complet pentru retur** + **sync Product la cancel/expire**.

Dacă vrei, următorul pas “practic” (fără întors de 10 ori prin fișiere): îți scriu un **plan P0** cu:

1. management command `auctions_tick` (activate + settle + expire payments),
2. hooks de integrare cu `payments` (mark AuctionOrder PAID),
3. policy clar de “ce se întâmplă cu Product” la CANCELED/EXPIRED/NO_WINNER.
