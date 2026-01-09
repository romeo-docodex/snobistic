# Catalog App — TODO (Snobistic)

> Scop: să avem un `catalog` enterprise, coerent și “single source of truth” (wizard), cu moderare corectă, filtre consistente, SKU robust, integrare authenticator, favorite safe, și performanță ok.

---

## P0 — BLOCKERS (de rezolvat înainte de prod)

### 1) BUG: `size_other_label` folosit în wizard, dar lipsește din model
**Fișiere:** `catalog/views_wizard.py`, `catalog/forms_wizard.py`, `catalog/models.py`  
- [ ] Decide: **ori** adaugi câmpul `size_other_label` în `Product`, **ori** îl elimini complet din wizard (ai deja `size_alpha` + `size`).
- [ ] Curăță toate referințele la `size_other_label` din create/edit preview + save.

### 2) BUG / inconsecvență: `colors` (singular) în wizard vs model (`base_color` FK + `colors` M2M)
**Fișiere:** `catalog/forms_wizard.py`, `catalog/views_wizard.py`, `catalog/models.py`  
- [ ] În wizard, schimbă câmpul din step-ul `size_details` din `colors` -> `base_color` (FK).
- [ ] În view: setează `product.base_color = base_color` și `product.real_color_name = base_color.name`.
- [ ] (Opțional) păstrează compatibilitatea legacy: `product.colors.set([base_color])` dar controlat explicit.

### 3) Moderation workflow: create setează `APPROVED` direct
**Fișier:** `catalog/views_wizard.py`  
- [ ] La creare produs, setează `moderation_status="PENDING"` (sau workflow-ul dorit: `PENDING -> APPROVED -> PUBLISHED`).
- [ ] Definește clar: ce înseamnă “APPROVED” vs “PUBLISHED” pentru vizibilitatea publică.

### 4) `toggle_favorite` trebuie POST-only (CSRF + prefetch/crawler safety)
**Fișiere:** `catalog/views.py`, `catalog/urls.py`, template/JS favorite buttons  
- [ ] Pune `@require_POST` pe `toggle_favorite`.
- [ ] Update în UI: favorite button -> `fetch()` POST + CSRF token.
- [ ] Păstrează răspuns JSON pentru AJAX.

---

## P1 — “Plan gaps” (cerințe din plan neacoperite complet)

### 5) Integrare explicită cu `authenticator` (certificat autenticitate)
**Fișier:** `catalog/models.py` (+ migrations)  
- [ ] Adaugă `OneToOneField` / `ForeignKey` către modelul din `authenticator` (ex: `ProductAuthentication`) cu `related_name="product"`.
- [ ] Înlocuiește `@property has_authentication_badge` bazat pe “ghicit” cu o relație reală.
- [ ] Decide: certificatul poate exista multiplu? (de regulă OneToOne).

### 6) Workflow “propune brand nou” cu aprobare
**Fișiere:** `catalog/models.py`, `catalog/views_wizard.py`  
- [ ] Când user completează `brand_other`:
  - [ ] fie creezi automat `Brand(name=..., is_pending_approval=True, is_visible_public=False)`
  - [ ] fie creezi `BrandSuggestion` (recommended) cu: user, text, product, status, admin_notes, timestamps.
- [ ] În wizard: dacă `brand_other` este completat, forțează `brand=None` (exclusivitate).
- [ ] În UI public: brand dropdown arată doar branduri `is_visible_public=True` & `is_pending_approval=False` (cu includere specială la edit).

### 7) “Tip articol” granular (bluză / tricou / sacou etc.)
**Fișier:** `catalog/models.py` (+ wizard step dacă vrei în UI)  
- [ ] Decide dacă vrei taxonomie granulară separată de `garment_type`:
  - [ ] Model `ArticleType` legat de `Subcategory` (recommended) sau `choices`.
- [ ] Integrează în wizard (pasul category/brand sau size_details).

### 8) Filtrare “diferență față de dimensiunile personale ale cumpărătorului”
**Fișier:** `catalog/views.py` (+ dependență pe `accounts` profile measurements)  
- [ ] Definește payload UI: toleranță (cm), câmpuri (bust/waist/hips/length etc.).
- [ ] Ia dimensiuni buyer din `accounts.Profile` (sau model measurements).
- [ ] Filtrează/sortează produsele după compatibilitate (ex: `abs(product.bust_cm - profile.bust_cm) <= tolerance`).
- [ ] (Opțional) scor de compatibilitate + sort “best fit”.

---

## P1 — Coerență vizibilitate publică (APPROVED vs PUBLISHED)

### 9) Centralizează “public queryset”
**Fișiere:** `catalog/models.py` (manager/queryset) + `catalog/views.py`  
- [ ] Creează helper: `ProductQuerySet.public()` care filtrează:
  - `is_active=True`, `is_archived=False`, `moderation_status="PUBLISHED"` (recommended)
- [ ] Folosește `public()` peste tot:
  - `ProductListView`, `ProductDetailView`, `SearchResultsView`,
  - related products, recently viewed, favorites (auth + guest),
  - `toggle_favorite` (să nu favorițezi produse nepublice).

---

## P1 — SKU (conform plan + hardening)

### 10) SKU include “locație” conform planului
**Fișier:** `catalog/models.py`  
- [ ] Include un `location_code` derivat din `pickup_location` (sau FK către `SellerLocation`).
- [ ] Ajustează generatorul SKU: locație + subcategorie + titlu + dată + mărime.

### 11) SKU: timezone + coliziuni
**Fișier:** `catalog/models.py`  
- [ ] Înlocuiește `datetime.now()` cu `timezone.now()`.
- [ ] Implementare retry: dacă SKU există, adaugi suffix random scurt (ex: `-A3K9`) și reîncerci.

---

## P1 — Wizard hardening

### 12) Cleanup fișiere temporare wizard (`product_wizard_tmp`)
**Fișier:** `catalog/views_wizard.py`  
- [ ] După `done()`, șterge fișierele temporare sau rulează cleanup periodic (cron/management command).
- [ ] Verifică permisiuni/ownership pentru MEDIA_ROOT pe VPS.

### 13) Câmpuri “hidden by profile” trebuie să fie `None` (ca să nu păstrezi junk la edit)
**Fișier:** `catalog/forms_wizard.py` (ProductDimensionsForm.clean) / `views_wizard.py`  
- [ ] Dacă measurement_profile nu folosește un câmp, setează explicit `cleaned[field]=None` înainte de salvare.

### 14) Package size: required (dacă vrei shipping logic)
**Fișier:** `catalog/forms_wizard.py`  
- [ ] Decide dacă `package_size` trebuie obligatoriu pentru listare.
- [ ] Dacă da: `required=True` + validare.

---

## P2 — Views (filtre, bug-uri, perf)

### 15) Filtru subcategorie lipsește în `ProductListView`
**Fișier:** `catalog/views.py`  
- [ ] Acceptă param `subcategory` (id sau slug).
- [ ] Aplică filtrare compatibilă cu gender/categorie.

### 16) BUG: `availability=out` nu poate returna rezultate
**Fișier:** `catalog/views.py`  
- [ ] Refactor: nu porni queryset cu `is_active=True,is_archived=False` dacă vrei “out”.
- [ ] Sau scoate complet availability până ai UI real.

### 17) Preț min/max global trebuie calculat pe același queryset ca listarea publică
**Fișier:** `catalog/views.py`  
- [ ] `aggregate(min,max)` să folosească `Product.public()` (nu doar active+ne-arhivate).

### 18) Filtru “dim_min/dim_max” e prea noisy (OR pe toate câmpurile)
**Fișier:** `catalog/views.py`  
- [ ] Constrânge dimensiunile după `measurement_profile` sau param `dim_field` (ex: `bust_cm`).
- [ ] UI: select “ce dimensiune filtrezi” (bust/waist/insole/bag_width etc.).

### 19) N+1 query hardening
**Fișier:** `catalog/views.py`  
- [ ] În queryset list/detail: `select_related(brand, category, subcategory, base_color, owner)` + `prefetch_related(images, compositions__material, sustainability_tags, colors)`.
- [ ] Related products: idem.

### 20) SearchResultsView duplică logică și e inconsistent
**Fișier:** `catalog/views.py`  
- [ ] Ori redirecționezi search către ProductListView (`/magazin/?q=...`),
- [ ] Ori îl faci să folosească același `public()` + aceeași logică de filtrare.

---

## P2 — URLs / routing

### 21) Scoate CRUD clasic din public (sau staff-only)
**Fișiere:** `catalog/urls.py`, `catalog/views.py`  
- [ ] Decide “single source of truth”: wizard.
- [ ] Dacă wizard e standard:
  - [ ] rutele `ProductCreateView/Update/Delete` -> staff-only sau eliminate.
  - [ ] păstrezi doar wizard pentru seller.

### 22) (Opțional SEO) Rută pentru subcategorie
**Fișier:** `catalog/urls.py`  
- [ ] `/magazin/categorie/<category_slug>/<subcategory_slug>/` pentru SEO și linkuri curate.

---

## P2 — Validări model-level (consistență totală)

### 23) Brand exclusivitate: `brand` XOR `brand_other`
**Fișier:** `catalog/models.py`  
- [ ] În `Product.clean()`:
  - dacă `brand` setat => `brand_other=""`
  - dacă `brand` null => `brand_other` obligatoriu (dacă vrei strict)

### 24) Sale type: FIXED vs AUCTION consistency
**Fișier:** `catalog/models.py`  
- [ ] `clean()`:
  - FIXED -> auction_* = None
  - AUCTION -> start_price + end_at obligatorii (depinde de flow)

### 25) Material composition constraints
**Fișiere:** `catalog/models.py`  
- [ ] `ProductMaterial.percent` validators 0–100.
- [ ] Validare sumă procent pe produs <= 100 (ideal în wizard + (opțional) model clean / constraint).

### 26) Min images enforce (la publish)
**Fișier:** `catalog/models.py` / admin moderation actions  
- [ ] La trecerea în `PUBLISHED`, impune `has_minimum_images() == True`.

### 27) Mărimi: coerent per size_group / measurement_profile
**Fișier:** `catalog/models.py`  
- [ ] `clean()`:
  - SHOES -> `shoe_size_eu` obligatoriu, restul numeric nul
  - CLOTHING numeric -> FR/IT/GB în funcție de selecție
  - ACCESSORIES -> One Size / size_alpha

---

## P3 — Admin, UX, QA

### 28) Admin moderation dashboard
**Fișiere:** `catalog/admin.py`, templates dashboard (admin/staff)  
- [ ] Pagina/listă moderare produse: approve/reject/publish/unpublish.
- [ ] Log: moderated_by / moderated_at / rejection_reason.

### 29) UX: edit imagini (delete/reorder/select main)
**Fișiere:** wizard templates + views  
- [ ] În edit wizard: permite ștergere imagini extra.
- [ ] Reordonare `position` + setare “cover/main”.

### 30) Teste (unit + integration)
**Fișiere:** `catalog/tests/`  
- [ ] Wizard: create flow cu fiecare measurement_profile (TOP/DRESS/PANTS/SHOES/BAGS/BELTS).
- [ ] Favorite: POST-only + guest session.
- [ ] Public visibility: list/detail/search consistent.
- [ ] SKU uniqueness + format.
- [ ] Brand suggestion flow.

### 31) Observabilitate / logging
- [ ] Log important: create product, edit product, propose brand, publish/unpublish.
- [ ] Sentry/monitoring hook (dacă folosești).

---

## Done criteria (când considerăm catalog “final”)
- Wizard = singura cale publică de create/edit pentru sellers.
- Moderation: PENDING -> APPROVED -> PUBLISHED (sau modelul tău final), consistent în toate views.
- Authenticator link real + badge logic stabilă.
- Brand suggestion/pending approval implementat.
- Favorite POST-only, sigur.
- Filtre + perf ok (select_related/prefetch), subcategory filter, dims filter “smart”.
- SKU robust (timezone + location + retry).
















