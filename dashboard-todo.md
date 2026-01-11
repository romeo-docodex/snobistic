Perfect — ai gândit corect: `dashboard` trebuie să fie **un “presentation layer”** care agregă date din `orders / catalog / auctions / payments / logistics / invoices / accounts`, iar **doar ce e “extra”** (gen rapoarte + setări globale) merită model/view dedicat.

Mai jos îți fac audit-ul pe formatul tău: **Ce avem / Ce lipsește / Ce trebuie îmbunătățit**, strict pe ce ai pus aici.

---

## ✅ 9) Aplicația `dashboard` — audit

### ✅ CE AVEM

#### Buyer

* **Dashboard buyer** (`buyer_dashboard`) cu:

  * count comenzi (`orders_count`)
  * count favorite (atenție: vezi la “îmbunătățit”)
  * indicator “dimensiuni salvate”
* **Listă comenzi buyer** (`orders_list`) cu tabel complet + CTA “Plătește”
* **Chat rapid** (`chat_quick`) cu ultimele 5 conversații

#### Seller

* **Dashboard seller** (`seller_dashboard`) cu:

  * statistici: total produse, licitații active, comenzi plătite cu produse ale sellerului, wallet balance
  * grafice pe ultimele 6 luni: comenzi & produse
  * carduri KYC / trust score / level progress (bine gândit)
* **Produsele mele** (`products_list`) + export CSV
* **Licitațiile mele** (`auctions_list`) + export CSV + acțiuni (edit/cancel/close)
* **Articole vândute** (`sold_list`) (prefetch corect pe order items doar ale sellerului)
* **Wallet** (`wallet`) cu filtrare perioadă + export CSV
* **Acțiuni seller legate de livrare/documente**:

  * generate/download AWB (redirect către `logistics`)
  * comision invoice download (redirect către `invoices`)
  * placeholder-uri pentru poze colet/retur

#### Structură app

* `models.py` gol (ok dacă dashboard rămâne agregator)
* `admin.py` gol (ok momentan)
* `urls.py` separă buyer/seller corect

---

### ❌ CE LIPSEȘTE (real, raportat la “scope”)

#### 1) Shop manager — lipsește complet

În spec ai:

* listă produse în validare
* aprobare / respingere
* istoric validări

În cod/urls/templates: **nimic** pentru shop manager.

> Recomandare: asta poate sta fie în `dashboard` (sub /cont/manager/...), fie într-un app dedicat (`moderation` / `staff_dashboard`). Dar **în prezent lipsește**.

#### 2) Admin (rapoarte + setări globale) — lipsește complet

În spec ai:

* rapoarte: comisioane, vânzări, retururi, scoruri
* setări globale: comision, buyer protection fee, retur, AWB SLA, limite licitații, parametri scoring

În cod: **zero** views/urls/templates pentru admin.

> Aici ai două variante sănătoase:

* **A)** “Admin” rămâne Django Admin + modele singleton de config în app-urile relevante (`payments`, `orders`, `auctions`, `accounts/services/score` etc.)
* **B)** faci “Admin dashboard” custom în `dashboard` (dar atunci trebuie **modele de config** + permisiuni staff)

Momentan: **lipsește**.

#### 3) Buyer: “Facturi & documente” în cont — lipsește ca secțiune

În spec ai “acces la facturi și documente disponibile”.
În dashboard buyer nu ai:

* listă facturi buyer
* link/shortcut către `invoices` / downloads

Poate exista în `invoices` app, dar **nu e expus în dashboard**.

#### 4) Seller: “Istoric articole + repost” — lipsește

Ai:

* produse listate
* licitații
* vândute
  Dar nu ai:
* “istoric articole” (ex: produse expirate/șterse/închise)
* “repost” flow (call-to-action + endpoint)

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (ca să fie production-grade și coerent cu “dashboard = doar prezentare”)

#### 1) **Inconsistență seller gating în template-uri**

În `buyer/orders_list.html` ai:

```django
{% if request.user.is_seller %}
```

Dar în `views.py` tu ai `is_seller()` cu **source-of-truth** pe `profile.role_seller`, apoi fallback.

✅ Fix corect: nu lăsa template-urile să decidă pe `user.is_seller`.
Ai 2 opțiuni curate:

* **A)** pui o proprietate pe User (sau pe Profile) gen `user.is_seller_effective`
* **B)** context processor / template tag care expune `is_seller(request.user)` și o folosești peste tot

Altfel o să ai UI care arată link-uri greșit pentru useri.

#### 2) **`buyer_dashboard`: favorites_count probabil greșit**

Tu calculezi:

```py
favorites_count = profile.favorites.count()
```

Dar tu ai zis explicit că favoritele sunt “ca la favorites” (și la tine favorites sunt foarte posibil în `catalog` (sesiune) sau alt mecanism, nu neapărat M2M pe profile).

✅ Recomandare: extrage într-un “favorites service” și folosește același source-of-truth ca pagina de favorites:

* ex: `catalog.services.favorites.get_count(request)`
  Ca să nu ai “dashboard arată 0, dar eu am 12 favorite”.

#### 3) **Bug de dată: calculul lunilor pe ultimele 6 luni e greșit în ianuarie**

Blocul:

```py
for i in range(5, -1, -1):
    m = (today.month - i - 1) % 12 + 1
    y = today.year - ((today.month - i - 1) // 12)
```

În Python, împărțirea `// 12` pe negativ “cade” (floor) și poate să-ți dea anul viitor în loc de anul trecut când e ianuarie.

✅ Fix robust: folosește `relativedelta` sau o funcție clară de month-shift.

#### 4) Lipsesc complet: pagination + filters + search (buyer & seller lists)

Acum toate listele sunt “dump all”:

* produse seller
* licitații seller
* sold orders
* wallet transactions
* buyer orders

✅ Minim recomandat:

* pagination (Django Paginator)
* filtre simple via querystring:

  * products: `status=active|pending`, `q=...`
  * auctions: `status=ACTIVE|PENDING|ENDED`
  * sold: `shipping_status=...`, `escrow_status=...`
  * wallet: deja ai period, dar mai poți `type=...`

#### 5) “Dashboard = doar agregator” → curăță imports/dependințe unde nu trebuie

Ex: `dashboard/views.py` importă multe modele direct. Asta e ok, dar când crește:

* mută calculele în “selectors/services” în app-urile lor (ex: `orders.selectors.seller_orders_stats(user)`).
  Dashboard doar cheamă servicii și randază template-ul.

#### 6) Placeholder-urile (upload poze colet / retur) trebuie fie scoase, fie “feature-flag”

Acum ai endpoint-uri care dau `messages.info("în curând")`. E ok temporar, dar în producție:

* ori le ascunzi din UI până sunt gata
* ori le pui sub “Coming soon” clar, fără URL public indexat

#### 7) Naming / typo: “seller/waller.html”

Ai menționat `seller/waller.html`, dar template-ul e `seller/wallet.html`. Asigură-te că în repo e consistent (altfel o să ai bug-uri de path).

---

## Concluzie: ce e “cu adevărat lipsă” acum

Dacă rămânem strict la ce ai listat în spec și la ce ai implementat:

1. **Shop manager dashboard** — 100% lipsă
2. **Admin dashboard (rapoarte + setări globale)** — 100% lipsă
3. **Buyer: facturi/documente în cont** — lipsește ca secțiune/shortcut
4. **Seller: istoric + repost flow** — lipsește
5. **Robustețe listări (pagination/filters)** — lipsește peste tot
6. **Coerență role gating + favorites source-of-truth** — trebuie aliniate

---

Dacă vrei, următorul pas “enterprise” (și cel mai eficient) e să facem un **mini-plan de implementare** pe 3 module:

1. `dashboard.staff` (shop manager)
2. `dashboard.admin` (rapoarte + settings, sau decidem să fie în Django Admin)
3. “hardening” (pagination + gating + services)

Spune-mi doar ce alegi pentru **Admin settings**: le vrei ca pagini custom în dashboard, sau le lăsăm în Django Admin prin modele singleton în app-urile lor? (Eu aș merge pe Django Admin la început, dashboard doar link-uri + rapoarte read-only.)
