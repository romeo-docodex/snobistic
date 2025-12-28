## Core — audit (vs. app-plan.md)

### ✅ CE AVEM

* **Homepage (`home`)**:

  * Query pe `Product` cu filtre corecte: `is_active=True`, `is_archived=False`, `moderation_status="APPROVED"`.
  * `select_related("category", "brand")` + `order_by("-created_at")`.
  * Livrează context pentru secțiuni: `popular_products`, `todays_picks`, `latest_products`, `homepage_categories` (+ alias-uri `featured_products`, `today_picks`).

* **Pagini statice** + routing:

  * `about`, `terms`, `privacy`, `faq`, `returns_policy`, `cookies_policy` există ca view-uri + URL-uri curate.

* **Contact end-to-end**:

  * `ContactForm` (ModelForm) + view `contact` cu validare.
  * Salvează mesajul în DB (`ContactMessage`) + metadate: IP, user_agent, user logat.
  * Trimite email către suport via `send_mail`.
  * Honeypot (anti-spam) în view + feedback cu `messages`.

* **Admin pentru ContactMessage**:

  * list_display, filtre, search, readonly fields, actions.

* **SEO tehnic minim**:

  * `robots.txt` servit din view (fără trailing slash).
  * `sitemap.xml` generat dinamic (paginile core) (fără trailing slash).

---

### ❌ CE LIPSEȘTE (față de plan + “enterprise-ready”)

* **SEO “de bază” real (meta title/meta description dinamice)**:

  * În `core` nu există un model / config pentru SEO (ex: `SiteSetting`, `PageSEO` etc.)
  * Nu există context processor care să injecteze meta automat pentru paginile core.
  * “în colaborare cu `catalog`” nu e acoperit aici (nimic pentru meta pe produs/categorie în core).

* **Sitemap complet pentru platformă**:

  * `sitemap.xml` include doar paginile statice core.
  * Lipsesc: **produse**, **categorii**, **licitații**, pagini dinamice (wishlist, cart, etc.) — chiar dacă ele apar în “meniul principal” din plan.

* **Pagini de erori (necesare în producție)**:

  * 400/403/404/500 custom (handlers + template-uri) — nu există în `core` (din ce ai lipit).

* **Flow de email mai “pro” pentru contact**:

  * Confirmare către user (“am primit mesajul”).
  * Email HTML (EmailMultiAlternatives) + template dedicat.
  * `Reply-To` setat pe email-ul userului (acum nu e).

* **Anti-abuz mai solid**:

  * Rate limit / throttling pe IP/email (ex: `django-ratelimit`).
  * CAPTCHA/Turnstile/ReCAPTCHA (dacă vrei).
  * Cooldown / blocklist.

* **Header/footer + meniul principal**:

  * În codul `core` lipit nu există nimic explicit (de obicei e în `base.html` / template partials).
  * Deci, **în această verificare**, nu pot confirma implementarea (doar că planul spune că `core` le “gestionează”).

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (bugs + calitate)

#### P0 — BUG / risc crash

* **`ContactForm` este invalid ca ModelForm în forma actuală**:

  * `Meta.fields` include `consent` și `honeypot`, dar **modelul `ContactMessage` nu are aceste câmpuri**.
  * În Django, asta dă eroare tipică: *Unknown field(s) ... specified for ContactMessage*.

  Fix recomandat (varianta “corect legal + audit”): adaugi câmpurile de consimțământ în model, honeypot rămâne doar în form.

  ```python
  # core/models.py
  from django.utils import timezone

  class ContactMessage(models.Model):
      ...
      consent = models.BooleanField(default=False)
      consent_at = models.DateTimeField(null=True, blank=True)
      privacy_policy_version = models.CharField(max_length=32, blank=True, default="")
  ```

  și în form:

  * `honeypot` rămâne field extra (ok),
  * `consent` mapat în model,
  * în `contact()` setezi `consent_at=timezone.now()` când e bifat.

* **Admin action `mark_as_processed` setează `processed_at=None`**:

  * Practic marchezi ca procesat dar pierzi timestamp-ul.

  Fix:

  ```python
  from django.utils import timezone

  def mark_as_processed(self, request, queryset):
      updated = queryset.update(
          is_processed=True,
          processed_at=timezone.now(),
          processed_by=request.user,
      )
  ```

#### P1 — corectitudine / SEO / robustete

* **`robots_txt()` hardcode-uiește `https://{host}`**:

  * Poate fi greșit în dev/staging sau în spate la reverse proxy.
  * Folosește:

    * `request.build_absolute_uri("/sitemap.xml")`
    * sau un `SITE_URL` în settings.

* **`sitemap_xml()` pune `lastmod=today` pentru toate paginile**:

  * Minim ok, dar nu reflectă realitatea.
  * Pentru home poți deriva `lastmod` din ultimul `Product.created_at` (sau `updated_at` dacă ai).

* **Hardcode `moderation_status="APPROVED"`**:

  * Fragil dacă schimbi choices.
  * Mai bine constant/enum importat din `catalog`.

#### P2 — scalare / mentenanță

* **Email sending direct în request**:

  * Pe trafic, blochează request-ul.
  * Minim: logging + try/except complet.
  * Ideal: Celery/RQ.

* **Home categories**:

  * `Category.objects.all()` — dacă ai concept de “active/has_products”, ar trebui filtrat.
  * Altfel, riști să listezi categorii “goale”.

* **“popular_products” nu e popular** (e “latest 8”):

  * Nu e bug, dar e naming/logic mismatch.
  * Popular = based on views, favorites count, sales, etc.

---

## Concluzie (core)

`core` e deja solid pe: **home + pagini statice + contact + robots/sitemap basic + admin**.
Problema mare e că, pentru nivel “enterprise”, îți lipsesc **SEO settings + sitemap complet + error pages + anti-abuz**, iar în forma actuală ai 2 P0 clare: **ContactForm invalid** + **processed_at=None**.

Dacă vrei, următorul pas logic (fără să ne atingem de alte app-uri încă) e să facem un mini “core hardening sprint” în ordinea:

1. reparăm `ContactForm` + consimțământ salvat,
2. reparăm admin actions,
3. înlocuim sitemap custom cu `django.contrib.sitemaps` (și includem Products/Categories),
4. adăugăm modelul de SEO settings + context processor.













































## Accounts

### ✅ CE AVEM (implementat)

#### 1) Conturi + autentificare

* Register cu **activare email** (uidb64 + token) + resend cu throttle.
* Login email/parola + “remember me”.
* Logout.
* Reset parola (flow complet) + Change password (cu audit event).

#### 2) 2FA (bine peste minim)

* TOTP (pyotp): setup + verify.
* Email 2FA (cod in cache, TTL 10 min, throttle send).
* SMS 2FA (backend hook + throttle + daily quota).
* Backup codes (JSON list) + regenerare.
* Trusted devices (cookie + token hash) cu bypass la login.

#### 3) Profil user + preferinte + masuratori

* Profile separat cu: phone, DOB, avatar, newsletter/marketing/sms.
* Dimensiuni personale (height/weight + masuratori) + status “complet” calculat in UI.

#### 4) Adrese

* CRUD adrese.
* Default shipping + default billing (unic per user) + flag billing.

#### 5) Seller settings + locatii

* SellerProfile: IBAN, seller_type, seller_level, commission_rate, trust_score, setari COD/local pickup.
* SellerLocation: cod 3 litere + default location unic.

#### 6) KYC (minim functional)

* Upload documente KYC + listare + stergere (PENDING/REJECTED).
* Admin: management KYC (prin Django admin).
* La APPROVED: sincronizeaza Profile + aplica bonusuri scor.

#### 7) Referral

* referral_code unic generat automat + referred_by.
* Register accepta referral_code si leaga inviter.

#### 8) Audit la login + merge data din sesiune

* AccountEvent: login success/fail, 2FA success/fail, password change.
* Merge session cart -> user cart (daca exista utilitarul).
* Merge favorites din sesiune in DB.

#### 9) Scoring service (baza OK)

* Functii pentru buyer/seller score + identity bonuses.
* register_seller_sale() cu praguri Rising/Top + comision auto (except VIP).

---

### ❌ CE LIPSESTE (vs app-plan.md)

#### 1) Social login (Google / Facebook / Apple)

* Nu exista flow OAuth (django-allauth / social-auth), callback-uri, linking conturi, “login cu X”.

#### 2) “Buyer / Seller / Ambele” ca roluri reale, cu UX complet

Acum:

* La register alegi doar buyer sau seller (`role` din RegisterForm).
* Exista in Profile `role_buyer`, `role_seller`, `seller_can_buy`, dar nu exista:

  * creare cont “ambele” din start,
  * upgrade/downgrade rol ulterior (buyer -> seller, seller -> buyer+seller),
  * UI/flow pentru `seller_can_buy`,
  * reguli de business enforce peste tot (ex: seller-only nu poate adauga in cart).

#### 3) Roluri avansate: Shop Manager (si UX)

* Nu ai un concept dedicat (grup/permisiuni + restrictii + UI).
* Momentan ramai doar cu `is_staff/is_superuser` si groups “generic”.

#### 4) Integrare reala scor cu Orders / Logistics / Support

* Ai serviciile (`on_buyer_order_paid`, `on_seller_late_shipment` etc.), dar nu exista apeluri din apps:

  * `orders` -> score events buyer/seller,
  * `logistics` -> late shipment / shipped on time,
  * `support` -> dispute/return penalties,
  * deci scorul se misca aproape doar din KYC/2FA.

#### 5) KYC ca flux complet (staff queue + decizie vizibila userului)

* Lipseste UI de review (in afara admin):

  * lista/queue pentru staff/shop manager,
  * actiuni approve/reject + motiv,
  * istoric decizii,
  * status flow complet PENDING -> IN_REVIEW -> APPROVED/REJECTED, cu reguli coerente.

#### 6) Profil “persoana juridica” complet in UX

* Modelul are campuri bogate (reg number, website, phone, contact person etc.)
* Dar in UI:

  * Register foloseste doar `company_vat` ca semnal,
  * ProfilePersonalForm NU include multe campuri din model (company_reg_number, company_website, company_phone, company_contact_person etc.),
  * deci planul “date firma (CUI, TVA, adresa, IBAN etc.)” e doar partial acoperit.

#### 7) UI complet pentru “scor numeric + clase A/B/C/D”

* Exista calcule (properties), dar lipseste:

  * pagina explicativa “de ce scorul meu e X”,
  * istoric evenimente scor (timeline),
  * transparenta reguli / breakdown.

#### 8) Functionalitati “enterprise” implicite la accounts (necerute explicit, dar inevitabile)

* Schimbare email (ai event types in model, dar nu ai flow).
* Verificare telefon (OTP) daca vrei sa te bazezi pe SMS 2FA serios.
* Export/stergeri GDPR mai robuste (ai delete account, dar nu ai “download data”).

---

### 🛠️ CE TREBUIE IMBUNATATIT (bug-uri + hardening + mismatch)

#### A) Bug-uri clare (astea le-as fixa primele)

1. **Ratelimit flag gresit**

* In `LoginView.post()` si `delete_account_request()` folosesti:

  * `getattr(request, "limits", False)`
* In `django-ratelimit` uzual e `request.limited`.
  ✅ Fix: `getattr(request, "limited", False)` (si verifica exact varianta librariei tale).

2. **Bug major: `timezone.timedelta` in TrustedDevice.issue()**

* In `models.TrustedDevice.issue()` ai:

  * `timezone.now() + timezone.timedelta(days=ttl_days)`
* `django.utils.timezone` nu expune `timedelta`.
  ✅ Fix: `from datetime import timedelta` si `timezone.now() + timedelta(days=ttl_days)`.

3. **Mismatch seller fields in `profile()`**

* In `views.profile()` cauti:

  * `seller.get_level_display()` / `seller.level`
  * `seller.commission_percent` / `seller.commission`
  * `seller.trust_score`
* In model sunt:

  * `seller_level`, `seller_commission_rate`, `seller_trust_score`
    ✅ Fix: aliniaza cu modelul actual (altfel afisezi None).

4. **Delete account flow: ordine riscanta**

* In `delete_account_confirm()` faci `user.delete()` apoi `logout(request)`.
  ✅ Fix: `logout()` inainte, apoi stergere (sau stergere + invalidare sesiuni separat).

5. **Cookie trusted device: `secure=True` hardcodat**

* In `set_trusted_cookie()` ai `secure=True`. In local/dev pe HTTP nu se seteaza cookie-ul.
  ✅ Fix: `secure = settings.SESSION_COOKIE_SECURE` sau `secure = not settings.DEBUG`.

6. **`TrustedDevice.token_hash` max_length prea mic**

* `make_password()` poate depasi 128 (mai ales cu argon2 / setari custom).
  ✅ Fix: 256 sau 512.

7. **Admin: `add_form = RegisterForm` nepotrivit**

* `RegisterForm` cere `phone`, `date_of_birth`, `agree_terms`, etc. Dar in `add_fieldsets` nu le dai.
  ✅ Fix: `AdminUserCreationForm` minimal (email + nume + parole + flags), separat de register-ul public.

---

#### B) Consistenta / reguli de business

8. **Inconsistenta intre `CustomUser.is_seller` si rolurile din Profile**

* Semnalul sincronizeaza `Profile.role_seller` din `CustomUser.is_seller`, dar:

  * nu ai un flow clar de “role_buyer off” (seller-only),
  * nu ai UI sa comuti roluri.
    ✅ Fix: defineste clar “source of truth” (recomand Profile roles ca business truth, user flags doar pentru permisiuni admin).

9. **Adrese: unicitate default doar la nivel aplicatie**

* Enforce-ul de “un singur default shipping/billing” e facut in `save()` dupa save.
  ✅ Fix: adauga **UniqueConstraint conditionale** (ca la SellerLocation) pentru default shipping/billing.

10. **KYC status mapping (Profile vs KycDocument)**

* Profile are NOT_STARTED/IN_REVIEW/APPROVED/REJECTED, documentele au PENDING/IN_REVIEW/APPROVED/REJECTED.
* Acum profile trece automat doar la APPROVED, restul ramane “manual”.
  ✅ Fix: reguli automate coerente (ex: daca exista PENDING/IN_REVIEW => Profile.IN_REVIEW; daca toate respinse => REJECTED; daca nu exista nimic => NOT_STARTED).

---

#### C) Security hardening (pentru productie)

11. **2FA brute-force**

* Codurile email/SMS in cache sunt ok, dar nu ai:

  * limita de incercari per user per interval,
  * lockout temporar,
  * invalidare cod dupa N incercari esuate.
    ✅ Fix: counter in cache + cooldown.

12. **`client_ip()` si X-Forwarded-For**

* Iei primul IP din XFF fara sa verifici ca esti in spatele unui proxy de incredere.
  ✅ Fix: foloseste setari Django pentru proxy (`SECURE_PROXY_SSL_HEADER`) si/sau valideaza XFF doar cand e cazul.

13. **`safe_next()`**

* OK ca folosesti `url_has_allowed_host_and_scheme`, dar in activation link adaugi `?next=` fara url-encoding.
  ✅ Fix: urlencode pentru `next` (si optional `require_https` cand e cazul).

14. **Session key pentru merge cart**

* In login pui `pre_login_session_key = request.session.session_key`, dar uneori `session_key` poate fi None pana nu e salvata sesiunea.
  ✅ Fix: asigura sesiunea (`request.session.save()` sau atingi sesiunea astfel incat sa existe cheie) inainte sa stochezi key-ul.

---

### Recomandare de prioritizare (ca sa nu rupi ritmul)

1. Fix bug-urile “A” (ratelimit flag, timezone.timedelta, mismatch seller fields, delete order, cookie secure, token_hash length, admin add_form).
2. Decide “roluri” (buyer/seller/both) + UI flows (upgrade/toggle) + enforcement in cart/catalog/orders.
3. Leaga scorul la orders/logistics/support (evenimente reale).
4. KYC review UI (queue) + status mapping automat + motive respingere vizibile userului.
5. Social login.














































## Catalog

### ✅ CE AVEM (aliniat pe plan)

**1) Magazin produse (listare + detaliu + cautare)**

* `ProductListView` cu filtrare extinsa (q, category, pret, marimi multiple scheme, brand, material inclusiv compozitii, culoare base+M2M, conditie, gen, fit, sustenabilitate, dim_min/dim_max) + sortare + paginare.
* `ProductDetailView` cu:

  * related products (subcategorie → fallback categorie),
  * recently viewed (session),
  * hook pentru licitatie (`product.auction`),
  * calc impact (CO2/trees) via `Subcategory.get_effective_impact_values()`.

**2) Categorii + subcategorii (ierarhie + logica utila)**

* `Category` cu `size_group` + `cover_image`.
* `Subcategory` cu:

  * `parent` (sub-subcategorii),
  * `gender` (F/M/U + allows logic),
  * `size_group` override,
  * `measurement_profile`,
  * `is_non_returnable` + auto-detect swimwear/lingerie,
  * impact fields + fallback “Alt tip…”.

**3) Branduri / materiale / culori / sustenabilitate**

* `Brand` cu `group`, `is_fast_fashion`, `is_visible_public`, `is_pending_approval`.
* `Material` cu heuristica `is_sustainable`.
* `Color` (nume + hex).
* `SustainabilityTag` + reguli in `Product.clean()` (NONE exclusiv, “SUSTAINABLE_MATERIALS” conditionat).

**4) Creare/editare produse**

* CRUD clasic: `ProductCreateView / UpdateView / DeleteView` + `ProductForm` (simplificat).
* Wizard multi-step (create + edit) complet:

  * poze (min required pe create),
  * titlu/descriere,
  * gen + categorie + subcategorie + brand (+ brand_other),
  * size_details (marimi + conditie + material + culori + compozitii),
  * pas separat pentru dimensiuni,
  * pret + package size,
  * sustenabilitate,
  * review,
  * scrie `ProductImage` + `ProductMaterial`.

**5) Favorite**

* `Favorite` model (auth) + fallback session (guest).
* `toggle_favorite` cu AJAX response + fallback redirect.
* `FavoritesListView`.

**6) AJAX subcategorii**

* endpoint `ajax_subcategories` cu filtrare pe gender compatibil.

---

### ❌ CE LIPSEȘTE / E INCOMPLET (față de plan)

**1) Filtrare după subcategorie (în plan e cerut explicit)**

* În `ProductListView` NU există query param dedicat pentru `subcategory` (ai doar `category__slug`).
* Pentru UX real de “Magazin” vei vrea `subcategory=<id|slug>` (și eventual `parent` / breadcrumb filtering).

**2) “Tipul articolului” ca filtru/entitate reală**

* Ai `garment_type` (choices + inferare), dar:

  * nu e expus în filtrele din listare,
  * nu e model/taxonomie (dacă planul îl vrea ca “tip articol” gestionabil, nu doar enum).

**3) “Altele” pentru mărimi — BLOCKER**

* Wizard folosește `size_other_label` (create/edit), dar în `Product` modelul postat **nu există** acest field.

  * Asta e crash / pierdere date (în funcție de cât cod ai efectiv în proiect).

**4) “Altele” pentru brand cu flux real de aprobare**

* Ai `brand_other` și în `Brand` ai `is_pending_approval`, dar lipsește fluxul:

  * când user introduce `brand_other`, să se creeze automat `Brand(is_pending_approval=True, is_visible_public=False)` (sau să se trimită în “queue” de aprobare),
  * UI/admin pentru aprobare/respinge + promovare în public.

**5) Filtrarea după dimensiunile personale ale cumpărătorului (accounts)**

* Planul cere “diferența față de dimensiunile personale ale cumpărătorului”.
* Acum ai doar `dim_min/dim_max` generic pe multe câmpuri, nu comparație cu profilul user (ex: “talie mea ± 2 cm”).

**6) Workflow-ul de status produs (PENDING/APPROVED/REJECTED/PUBLISHED/SOLD)**

* În wizard + `ProductCreateView` setezi direct `moderation_status="APPROVED"`.
* Nu există un flow clar:

  * PENDING → (validare) → APPROVED → (publicare) → PUBLISHED
* Plus: “APPROVED” apare în listare publică, ceea ce amestecă “validat intern” cu “public”.

**7) Integrarea reală cu `authenticator`**

* `Product.has_authentication_badge` presupune `product.authentication` (OneToOne), dar în catalog nu există relația concretă + link/certificat + afișare clară.
* Lipsește și filtrarea/afisarea “Autentificat” conform plan.

**8) Admin/operational completeness pentru marketplace**

* Nu se vede:

  * `admin.py` cu acțiuni de moderare (approve/reject/publish, bulk),
  * management commands (import categorii/branduri/materiale),
  * teste,
  * templates complete (nu pot valida acoperirea UI pe toate filtrele/step-urile).

**9) CRUD clasic e mult sub wizard și sub plan**

* `ProductForm` (CRUD) nu acoperă: `condition`, `fit`, `colors`, `compositions`, `package_size`, `sustainability`, mărimi numerice etc.
* Nu impune “min 4 poze” (ai text în help, dar nu validare reală).

**10) Redirect pentru slug history (SEO)**

* Ai `ProductSlugHistory`, dar nu există logică în view/middleware să facă 301 către slug-ul curent dacă user accesează un slug vechi.

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (bugs + securitate + hardening)

#### A) BUG-uri / inconsistennțe (prioritate mare)

1. **`size_other_label` lipsă în Product** (dacă e chiar lipsă în repo)

   * Rezolvă prin: adăugare field + migrare **sau** eliminare completă din wizard/forms.

2. **`availability=out` e logic greșit**

   * Pornești queryset din `is_active=True, is_archived=False`, deci “out” nu va prinde nimic real.
   * Corect: pornești din `Product.objects.all()` și apoi aplici condiția în funcție de parametru.

3. **Acces public la produse nemoderate**

   * `ProductDetailView.get_object()` permite orice produs activ/ne-arhivat indiferent de `moderation_status`.
   * `SearchResultsView` la fel.
   * Recomandare: public vede strict `PUBLISHED` (și eventual `APPROVED` doar dacă asta e decizia), iar owner/staff pot vedea restul.

4. **Create/Update/Delete fără protecție explicită**

   * `ProductCreateView` folosește `self.request.user` ca owner; dacă e anon, e problemă.
   * `Update/Delete` filtrează owner în queryset, dar fără `LoginRequiredMixin` UX-ul e slab și pot apărea edge cases.

5. **`toggle_favorite` ar trebui POST + CSRF**

   * Acum poate fi chemat ca GET, ceea ce e anti-pattern și te expune la acțiuni nedorite (CSRF-like behavior).
   * Pune `@require_POST` + CSRF.

#### B) Performanță / query hygiene

* În `ProductListView` ai multe M2M + `distinct()` → cost mare.

  * Adaugă `select_related("brand","category","subcategory","base_color","material")`
  * `prefetch_related("images")` (+ tags/compositions dacă le afișezi în card)
* `price_agg` se calculează pe “active/ne-arhivate” dar fără filtrul de moderare; ideal aceeași bază ca listarea publică.
* Indexuri: ai câteva bune; dacă filtrezi intens pe `price`, `gender`, `fit`, `is_archived`, `is_active`, merită indexuri compuse țintite.

#### C) Consistență date / timezone

* SKU folosește `datetime.datetime.now()` (naive). În Django, folosește `timezone.now()`.

#### D) Wizard UX / validare

* Gender: wizard pare să meargă pe F/M; în model ai și U → asigură suport complet.
* Subcategorie vs gen: ai validare în `clean()`, dar e bine să blochezi mai devreme în wizard (pasul category_brand).
* Imagini: lipsesc capabilități tipice:

  * ștergere imagini extra la edit,
  * reordonare `position`,
  * generare `alt_text` automat (SEO/UX),
  * validare format/dimensiune.
* Compoziții: validare sumă procente (<=100 și >0), duplicat materiale etc.

#### E) SEO: slug history incomplet

* Ai istoric, dar fără redirect 301 din slug vechi → pierzi SEO și backlinks.

---

## Priorități recomandate (ca să “bifezi planul” rapid)

1. **Fix BLOCKER**: `size_other_label` (model + migrare / sau scoatere).
2. **Regulă publică unică**: decide “public = PUBLISHED” și aliniază `ListView`, `DetailView`, `SearchResultsView`, `toggle_favorite`, `related_products`.
3. **Moderare reală**: PENDING → APPROVED → PUBLISHED + UI/admin actions.
4. **Brand_other approval flow** (creare Brand pending + queue de aprobare).
5. **Filtru subcategorie + garment_type în listare** (plan + UX).
6. **Redirect slug vechi → slug nou** (SEO).
7. **Hardening**: LoginRequired/POST/CSRF + optimizări query.












































## Cart

### ✅ CE AVEM (aliniat la plan)

#### 1) Coș pentru user sau vizitator

* **Cart DB** cu `user (OneToOne)` + `session_key` pentru guest.
* **UniqueConstraint** pe `session_key` (când nu e null) → 1 cart / sesiune.
* `get_cart()` (fără create) + `get_or_create_cart()` (cu create) – corect pentru flow-ul web.
* **Merge logic guest→user la login**: `merge_session_cart_to_user()` (DB cart + fallback “legacy session dict”).

#### 2) Adăugare / eliminare produse

* `cart_add()` (POST only) + `CartItem unique_together(cart, product)` → fără duplicate.
* `cart_view()` suport remove (prin `action=remove` sau `remove_<id>`).
* Răspuns **JSON** la add pentru AJAX (count/total etc).

#### 3) Offcanvas mini-cart în header

* Endpoint dedicat `cart_offcanvas_partial()` care returnează HTML via `render_to_string`.
* `context_processors.cart` expune `cart` + `cart_items_count` (badge în navbar).

#### 4) Cupon

* Model `Coupon(code, discount %, is_active)` + aplicare în `cart_view()` + persistare în `Cart.coupon`.
* `Cart.get_total_price()` aplică discount procentual (bun ca început).

#### 5) Checkout entrypoint (în cart app)

* `checkout_view()`:

  * `@login_required`
  * blochează dacă nu există items
  * cere adresă înainte de checkout
  * cere acceptare T&C (`agree_terms`)
  * estimare transport via `calculate_shipping_for_cart(cart)`
  * pre-check Wallet (buyer protection + shipping)
  * metode plată: card / wallet / COD
  * restricție COD pe trust class A/B
  * creează Order din cart (`Order.create_from_cart`)
  * flow pentru wallet + COD OK (Payment PENDING pentru COD)

#### 6) Admin

* Admin complet pentru `Cart`, `CartItem`, `Coupon` + inline items.

---

### ❌ CE LIPSEȘTE (față de app-plan.md / cerință de produs)

#### 1) „Permite actualizarea cantității”

Ai `quantity` în model, dar:

* nu ai **endpoint/view** pentru update quantity
* în `cart_add()` dacă item există → `pass` (nici update, nici mesaj clar)

> Dacă la fashion rămâne qty=1: trebuie făcut explicit (blocare + mesaj „deja în coș”) și/sau ascuns complet qty din UI.

#### 2) „Poate include produse câștigate la licitații care trebuie plătite”

În `cart` nu există:

* structură/logică pentru **auction-won items**
* flow de „adaugă automat în coș după final licitație”
* UI separată „de plătit până la…”

Acum pare că licitațiile merg direct spre Order (ok), dar **nu e aliniat cu planul** care zice că pot intra și în cart.

#### 3) „Calculează sumarul coșului: total produse + buyer protection fee + estimare transport”

* În `cart_view()` **nu pui în context**:

  * buyer protection fee
  * shipping estimate
* Doar în `checkout_view()` calculezi (parțial) – deci **pagina de coș** nu poate afișa sumarul complet conform planului.

#### 4) Estimare transport pentru guest

Planul zice coș pentru vizitator; guest n-are adresă, dar tot ar trebui:

* estimare de tip „de la X lei” / tarif default / selectare zonă din UI

Acum: **lipsă**.

#### 5) Cupoane – reguli reale (minim de produs)

Ai doar `discount% + is_active`. Lipsesc (ca funcționalitate de produs):

* `valid_from / valid_to`
* limită utilizări total / per user
* min cart value
* discount fix vs procent
* aplicare pe categorii/branduri
* prevenție „stacking” / combinații

#### 6) Coș multi-seller: reguli clare

Planul `orders` spune „de la ce vânzător cumpără”.
În `cart` nu ai clar:

* restricție „1 seller per cart” **sau**
* split automat în **mai multe comenzi** (una per seller)

Dacă nu impui nimic, `Order.create_from_cart()` devine zona unde trebuie să rezolvi (dar azi nu e explicit din cart).

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (bug-uri, robustețe, edge cases)

#### 1) Bug real: `checkout_view` poate da 404

Ai:

```py
cart = get_object_or_404(Cart, user=request.user)
```

Dacă user tocmai s-a logat și nu are cart creat încă → **404**.

* Fix: folosește `get_or_create_cart(request)` în checkout (și apoi verifici items).

#### 2) `cart_add()` pentru item existent e “silent no-op”

Acum e:

```py
if not created:
    pass
```

Recomandat:

* fie incrementezi qty (dacă permiți)
* fie returnezi JSON/mesaj clar: **„Produs deja în coș”**

#### 3) Validări de produs la add (minim necesare într-un marketplace fashion)

Acum verifici doar `is_active=True`. În practică mai vrei:

* `status=published` / `is_sold=False` (în funcție de catalog)
* blocare adăugare **propriul produs** (seller își pune produsul în coș)
* (opțional) blocare produs „rezervat” într-un checkout activ

#### 4) Concurență / rezervare produs (foarte important la 1 buc)

Fără rezervare/locking:

* 2 useri pot avea același produs în coș și pot plăti aproape simultan

Minim:

* rezervare la început de checkout (atomic) sau la momentul plății (în `Order.create_from_cart` / `payments`).

#### 5) Integritatea modelului `Cart` (regulă de business)

Acum poți avea teoretic:

* cart cu `user=None` și `session_key=None` (dacă cineva creează greșit manual)
  Recomand:
* **CheckConstraint**: cart trebuie să aibă **ori user, ori session_key**.

#### 6) Adresă de livrare „default”

În `cart_view()` iei `request.user.addresses.first()`:

* nu garantează „default shipping”
  Recomand:
* logică de „default address” (câmp dedicat sau ordering clar).

#### 7) UX cupon

* Nu ai „remove/unapply coupon”
* Dacă `coupon` devine inactiv după ce e salvat în cart: totalul îl ignoră (ok), dar UX-ul ar trebui să afișeze warning și/sau să curețe `cart.coupon`.

#### 8) Cod cleanup (mic, dar sănătos)

* `CartAddProductForm` nu e folosit (ori îl scoți, ori îl integrezi).
* În `cart_view()` ai două moduri de remove (`action=remove` și `remove_<id>`) → păstrează unul.

#### 9) Teste (aici e cel mai mare gap de “enterprise quality”)

Minim utile:

* guest cart create + merge la login (DB cart + legacy dict)
* add/remove + “already in cart”
* cupon valid/invalid + expirare
* COD restriction A/B
* wallet insufficient funds
* checkout 404 regression (fixul de la punctul 1)

---














































## Orders

### ✅ CE AVEM (aliniat la plan)

#### 1) Crearea comenzilor la checkout (din cart)

* `Order.create_from_cart(...)`:

  * creeaza `Order` + `OrderItem` (snapshot `price` + `quantity`)
  * calculeaza si salveaza: `subtotal`, `buyer_protection_fee_amount`, `seller_commission_amount`, `shipping_cost`, `total`, `shipping_days_min/max`
  * **goleste cosul** (`cart.items.all().delete()`)

#### 2) Statusuri (acopera o parte din “creata/platita/expediere”)

* `payment_status`: pending/paid
* `shipping_status`: pending/shipped/cancelled
* `escrow_status`: pending/held/released/disputed
* helpers:

  * `mark_as_paid()` → trece `escrow_status=HELD`
  * `release_escrow()` → payout in wallet (cu reguli minime)
  * `mark_escrow_disputed()` → la retur

#### 3) Vizualizare comenzi (buyer + seller)

* `order_list_view`:

  * buyer: lista comenzi (template din dashboard buyer)
  * seller: redirect la `dashboard:sold_list`
* `order_detail_view`:

  * buyer vede comanda
  * seller vede comanda **doar daca are items in ea** (`product__owner=user`)

#### 4) Retururi (minim functional)

* `ReturnRequest` (pending/approved/rejected)
* `order_return_request_view`:

  * doar buyer-ul comenzii
  * doar daca `shipping_status == SHIPPED`
  * blocheaza daca exista deja PENDING
  * marcheaza `escrow` ca DISPUTED
* `return_list_view`:

  * buyer: retururile lui
  * seller: retururi pentru comenzi unde are produse

#### 5) Export CSV seller

* `order_export_view` exporta CSV (distinct) pentru comenzile unde seller-ul apare in items.

#### 6) Facturi (gating corect ca idee)

* `invoice_view(order_id, kind)` cu reguli:

  * PRODUCT/SHIPPING doar dupa `payment_status=PAID`
  * COMMISSION doar dupa `escrow_status=RELEASED`
  * RETURN doar daca exista ReturnRequest APPROVED
* calcule VAT pe baza `SNOBISTIC_VAT_PERCENT`.

---

### ❌ CE LIPSESTE (fata de plan / produs real)

#### 1) Statusurile “delivered / finalized / anulata” (din plan)

Planul cere: **creata, platita, in curs de expediere, livrata, finalizata, anulata**.

* acum nu ai:

  * `DELIVERED` / `COMPLETED` (si nici timestamp-uri gen `delivered_at`, `completed_at`)
  * un “order_status” canonical (il poti deriva, dar in practica ajuta mult separat)

#### 2) Retururi complete (PF/PJ + Magazin vs Licitatii)

Lipsesc complet:

* diferentiere PF/PJ
* “return window” calculat din **livrare** (nu doar shipped)
* reguli pentru `order_type=auction_win` cu termen de **3 zile**
* status “rambursat / in curs de rambursare”

#### 3) Retur pe produs (line-item) + poze/dovezi

Planul zice “la nivel de comanda sau produs” + “poze incarcate”:

* `ReturnRequest` e legat doar de `Order`
* nu exista legatura cu `OrderItem`
* nu exista upload atasamente (imagini/fisiere)

#### 4) Integrare reala cu logistics (AWB + tracking + poze colet)

In `Order` nu exista:

* AWB number / status tracking / poze obligatorii
* mecanism de sincronizare order ↔ shipment (chiar daca `logistics` exista)

#### 5) Adresa de facturare separata

Planul spune livrare + facturare.

* `Order` are doar `address` (shipping)
* ai `OrderAddressForm` cu `billing_address`, dar **nu e folosit** si modelul Order nu are `billing_address`

#### 6) Comenzi din licitatii (end-to-end)

Ai `TYPE_AUCTION_WIN`, dar lipsesc:

* termen de plata (deadline)
* anulare automata daca nu e platita pana la deadline
* restrictii de retur specifice licitatiilor (3 zile)

#### 7) Multi-seller clar (sau restrictionat, sau split)

Planul “de la ce vanzator cumpara” implica ordine “per seller” sau split logic.

* acum o comanda poate contine produse de la mai multi sellers
* asta strica:

  * facturarea (commission / product) per seller
  * rapoarte/export
  * “seller_commission_amount” (calcul global)

---

### 🛠️ CE TREBUIE IMBUNATATIT (bugs + risc business + hardening)

#### 1) BUG critic: cuponul din cart NU ajunge in Order

* in cart: `cart.get_total_price()` aplica discount
* in orders: `create_from_cart()` calculeaza subtotal pe **pret full** si ignora coupon/discount
  Consecinte:
* mismatch intre pre-check (wallet/total) si suma reala din order
* buyer_protection si commission se calculeaza gresit (pe full)
  **Fix recomandat**:
* adauga in Order campuri: `discount_amount`, `coupon_code` (sau FK optional) + calcule pe `subtotal_after_discount`
* sau pasezi explicit `discount_amount` in `create_from_cart(...)`

#### 2) Multi-seller: export + invoice sunt incorecte

* `order_export_view` exporta `o.total` (total comanda) chiar daca seller-ul are doar o parte din items
* `invoice_view` alege `seller = order.items.first().product.owner` → complet gresit in multi-seller
  **Fix recomandat (alege una)**:
* (A) **Restrictie**: 1 seller per cart/order (cel mai simplu)
* (B) **Split**: `create_from_cart` creeaza **cate un Order per seller**
* (C) “SubOrders” / “OrderSellerSummary” (mai complex, dar scalabil)

#### 3) Atomicitate + concurenta

`create_from_cart` ar trebui:

* `transaction.atomic()`
* optional `select_for_update()` pe cart items / produse
* si un mecanism de “reserve product” ca sa nu fie vandut simultan (fashion = 1 buc)

#### 4) Snapshot adresa (integritate istorica)

`Order.address` pointeaza la `Address` (care poate fi editata).
Asta inseamna ca o comanda veche isi “schimba” adresa in timp.
**Fix**:

* `OrderShippingAddressSnapshot` / `OrderAddress` (copie a campurilor) la momentul plasarii comenzii

#### 5) Retur permis pe SHIPPED (prea slab)

In real life returul se bazeaza pe **DELIVERED** + termen legal.
**Fix**:

* `shipping_status` sa includa `DELIVERED`
* `delivered_at`
* return window check: `now <= delivered_at + X zile` (X diferit PF/PJ si auction)

#### 6) Eliberare escrow (conditii incomplete)

Acum: `release_escrow()` permite dupa `SHIPPED` si fara retur pending.
In real: dupa `DELIVERED` + “return window expired” (sau confirmare).
**Fix**:

* flow automat (management command / task) care finalizeaza comanda si elibereaza escrow cand expira returul

#### 7) Payment status: sursa unica de adevar

Ai `Order.payment_status` + `Payment.status` (latest).
Trebuie stabilit clar:

* Order e canonical si Payment e jurnal **sau**
* Payment e canonical si Order se updateaza din webhook (recomandat)

---










































## Auctions

### ✅ CE AVEM

#### 1) Flux complet de creare licitație (wizard 0–5)

* **Step 0**: `AuctionProductCreateForm` creează un `Product` dedicat licitației (owner=request.user, sale_type="AUCTION", quantity=1 etc.)
* **Step 1**: `AuctionStep1Form` cere **minim 3 imagini** și creează `AuctionImage` rows
* **Step 2**: setezi `size` (aliniat cu `Product.SIZE_CHOICES`)
* **Step 3**: `dimensions` în `JSONField`
* **Step 4**: `materials` (M2M normalizat) + `description`
* **Step 5**: setări licitație (`start_price`, `min_price`, `duration_days`) + validare `min_price >= start_price`
* La publish (step5) sincronizezi produsul:

  * `product.sale_type="AUCTION"`, `product.price = start_price`, `product.auction_*` populate

#### 2) Listare + detaliu licitație

* `auction_list_view` cu tab-uri:

  * `active` (start<=now, end>now, is_active=True)
  * `upcoming` (start>now)
  * `ended` (end<=now)
* `auction_detail_view` prefetch pe `images`, `materials`, `bids__user`

#### 3) Plasare bid (minim funcțional)

* `place_bid_view` (login_required + require_POST)
* `BidForm.clean_amount()` validează `amount >= current_price()`

#### 4) Admin bun (peste medie)

* inlines imagini + bids
* annotate pentru max bid + count (evită N+1 în list)
* actions: close now / open / recalc end / extend 1d / extend 7d
* preview imagini + link produs admin/public

#### 5) Închidere manuală licitație (owner)

* `close_auction_view` setează `end_time=now` și `is_active=False`

---

### ❌ CE LIPSEȘTE (față de plan)

#### 1) Finalul licitației: câștigător + reserve + creare comandă

Planul cere:

* selectare **winner** (highest bid) dacă `max_bid >= min_price`
* **creare Order** pentru câștigător
* **termen de plată** + ce se întâmplă dacă nu plătește (cancel, relist, next bidder etc.)

În cod NU există:

* mecanism de “finalize auction”
* câmpuri / logică pentru winner, final_price
* integrare cu `orders` pentru `order_type=auction_win` și `OrderItem` snapshot

#### 2) Deadline de plată + anulare automată dacă nu plătește

* lipsesc: `payment_deadline_at`, `paid_at`, `expired_at`, “relist logic”

#### 3) Reguli de increment minim (+10% / step)

Planul zice “increment minim (ex +10%)”.

* în cod: doar `bid >= current_price`, fără step/min increment

#### 4) Stări “oficiale” pentru licitație (pending/active/ended/cancelled)

* ai doar `is_active` + filtre pe start/end
* lipsește `status` real + tranziții clare (draft → upcoming → active → ended → cancelled)

#### 5) Auto-close / job periodic + anti-sniping

* nu există task periodic care:

  * închide licitațiile expirate
  * determină winner și creează comenzi
* nu există anti-sniping (extindere automată dacă apare bid în ultimele X minute)

#### 6) Validări business la bid (minim necesar)

Lipsesc explicit:

* interdicție **owner** să liciteze pe licitația lui
* verificare că licitația a început (`start_time <= now`) la `place_bid_view`
* limitări buyer-only / scor minim / KYC (dacă vrei să le impui, planul general le sugerează prin “seriozitate/kyc”)

#### 7) Reguli retur pentru licitații (3 zile, doar neconform)

* nu e în `auctions` direct, dar trebuie să fie aplicat prin `orders`:

  * `Order.order_type = auction_win` + return window special + motive limitate
* acum nu există integrarea completă (nici crearea comenzii, deci nici aplicarea regulilor)

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (bugs + risc business + hardening)

#### 1) BUG/logic gap: `place_bid_view` permite bid înainte să înceapă licitația

În `place_bid_view` filtrezi doar:

* `end_time__gt=now` și `is_active=True`
  Nu filtrezi:
* `start_time__lte=now`
  Consecință: user poate licita pe “upcoming” dacă is_active e true și end_time e în viitor.

#### 2) Lipsă feedback UI la bid invalid

* `place_bid_view`: dacă `form.is_valid()` e False, faci redirect fără mesaj.
  Recomandat:
* afișezi erorile în `auction_detail` (messages / re-render cu form errors)

#### 3) “current_price” nu e single source of truth și e scump la runtime

* `Auction.current_price()` face query pe bids (order_by -amount).
  În listare, tu prefetch-uiești `bids` (greu) dar tot nu folosești un `current_price` denormalizat.
  Recomand:
* câmp denormalizat `current_price` + `bids_count` actualizat la fiecare bid (atomic)
  sau
* annotate `Max('bids__amount')` în list view (ca în admin), fără prefetch de bids

#### 4) Concurență / race condition la bids

Două bids simultane pot trece `clean_amount` și se salvează ambele (mai ales dacă sunt egale sau foarte apropiate).
Recomand:

* `transaction.atomic()`
* lock pe Auction (`select_for_update`) + revalidare “min_allowed” chiar înainte de save

#### 5) Regula “>= current” permite bid egal (tie)

* dacă doi useri pun același bid (sau owner), ai situații neclare.
  Recomand:
* minim **strict** `>` și/sau step (+10% / +X RON)

#### 6) Validare JSON pentru `dimensions` lipsește

* `AuctionStep3Form` folosește Textarea pentru JSONField, dar nu parsează/validează JSON.
  Recomand:
* `clean_dimensions()` care face `json.loads` și ridică ValidationError
  sau UI cu câmpuri structurate.

#### 7) Risk major: produsul de licitație poate apărea “cumpărabil” în catalog/cart

* Step0 setează `sale_type="AUCTION"` și `is_active=True` + `price=0.01` placeholder
* Step5 setează `product.price = start_price`
  Dacă `catalog/cart/orders` nu blochează explicit `sale_type="AUCTION"` la “add to cart / checkout”, poți vinde produsul ca “buy now” accidental.
  Recomand:
* produse AUCTION **nu sunt add-to-cart** (doar “Participă la licitație”)
* sau `is_active=False` până la step5 și chiar după step5 să fie exclus din shop normal

#### 8) `Auction.save()` calculează end_time doar dacă e null

* dacă modifici `start_time`/`duration_days` după ce există `end_time`, nu se recalculează.
  Ai admin action de recalc, dar în business trebuie decis clar:
* end_time e derived mereu (recalc automat) **sau**
* end_time e “manual override” (și atunci UI/logic trebuie să fie explicită)

#### 9) Date lipsă pentru “finalization pipeline”

Ca să faci complet planul, ai nevoie de câmpuri (minim):

* `status`
* `winner` (FK user) / `winning_bid`
* `final_price`
* `payment_deadline_at`
* `closed_at` / `finalized_at`
* `order` (FK către Order creat)

---

Dacă vrei următorul pas “implementare”, cea mai sigură ordine (și îți deblochează tot) este:

1. **Blocare purchase normal** pentru `sale_type="AUCTION"` (catalog/cart)
2. **Finalize auctions job**: winner + reserve + create order (`order_type=auction_win`) + payment deadline
3. **Bid rules**: start_time check + owner restriction + min increment + concurrency lock











































## Authenticator

### ✅ CE AVEM

#### 1) Pagina “Autentificare Produse” (upload)

* `authenticate_product_view` acceptă POST cu fișiere.
* Acceptă **user logat** (setează `auth_req.user`) sau **guest** (salvează `email`).
* Setează `submitted_at` + `status=PENDING`.

#### 2) Upload poze multiple (model normalizat)

* `AuthUploadForm` primește `images` multi-file.
* Creează `AuthImage` pentru fiecare poză (`auth_request.images`).

#### 3) Istoric pentru user logat

* `authenticate_history_view` listează `AuthRequest` ale userului (order_by `-submitted_at`).

#### 4) Download certificat (simplu, pentru user logat)

* `download_certificate_view` permite acces doar dacă:

  * request-ul aparține userului
  * status = `SUCCESS`
* redirect către `certificate_file.url`.

---

### ❌ CE LIPSEȘTE (față de plan)

#### 1) Integrarea cu platforma externă (API)

Planul cere:

* “Trimite cererea către platforma externă (prin API)”
* “Primește și salvează rezultatul (verdict + certificat/link)”

În cod acum NU există:

* client HTTP / job / integrare webhook
* câmpuri pentru provider:

  * `provider_name`, `provider_request_id`
  * `result_payload` (JSON), `processed_at`, `failed_reason`
  * `certificate_url` (dacă vine extern)

#### 2) Verdict explicit “autentic / nu” (separat de status)

Planul cere explicit:

* verdict **autentic / nu**
* certificat digital / link extern

Acum ai doar `Status: PENDING/SUCCESS/FAILED` care amestecă:

* lifecycle (pending/processing/done/failed) cu
* rezultat (autentic/inautentic)

Lipsește:

* `verdict = AUTHENTIC / INAUTHENTIC / INCONCLUSIVE`
* un status mai corect (ex: `PENDING/PROCESSING/DONE/FAILED`)

#### 3) Legătura cu un produs din `catalog`

Planul cere:

* “Leagă rezultatul de un produs din catalog când cererea e pentru produs Snobistic”
* “Badge Autentificat în pagina produsului + link certificat”

În cod acum lipsește complet:

* `product = ForeignKey(Product, null=True, blank=True)`
* logică de asociere request ↔ produs
* afișare badge/link în template-urile `catalog`

#### 4) Guest flow complet (fără cont)

Ai doar `email` salvat, dar lipsește:

* istoric pentru guest
* link securizat pentru download certificat (token)
* confirmări pe email (trimite link magic către rezultat)

#### 5) Validări reale pe upload

Lipsește:

* minim imagini (ex: **>= 3**)
* validare mime/type, size limit, max number
* rate limiting / anti-spam (mai ales pentru guest)

#### 6) Admin / backoffice

`admin.py` e gol, dar planul implică procesare & rezultate.
Lipsește:

* `list_display`, `filters`, `search`
* inline pentru `AuthImage`
* actions: “mark success/failed”, “atașează certificat”, “retry send”

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (bug-uri / hardening / enterprise)

#### 1) BUG major: `form.save(commit=False)` rupe upload-ul de imagini

În view faci:

```py
auth_req = form.save(commit=False)
...
auth_req.save()
```

Dar `AuthUploadForm.save()` creează `AuthImage` imediat după `super().save(commit=commit)`.

Când `commit=False`:

* `auth_req` NU are `id` încă
* apoi `AuthImage.objects.create(auth_request=auth_req, ...)` va eșua (sau se comportă inconsistent), pentru că FK cere obiect salvat.

**Fix corect (minim):**

* NU mai folosi `commit=False` cu acest form, **sau**
* rescrii form-ul astfel încât să suporte commit=False (creezi imaginile doar după ce ai `id`).

#### 2) Regula “ori user, ori email” nu e enforce-uită

Acum poți ajunge la:

* guest fără email (dacă validarea nu obligă)
* user cu email completat aiurea
  Recomand:
* validare în form/model: “exact unul din (user, email) trebuie să existe”.

#### 3) Redirect direct la fișier (certificate_file.url) = acces dificil de securizat

Pentru producție, adesea vrei:

* fișier privat + signed URL expirabil
* sau view care servește fișierul controlat (mai ales dacă ai nevoie de audit/log)

#### 4) Lipsesc câmpuri de audit și procesare

Ai doar `submitted_at` + status.
În producție vrei minim:

* `created_at`, `updated_at`
* `processed_at`
* `attempts`, `last_error`
* `provider_response_received_at`

#### 5) Lipsă “processing” state

Ai `PENDING`, `SUCCESS`, `FAILED`. Îți lipsește starea “în procesare” (mai ales dacă trimiți către provider asincron).

---

### Fix-ul minim (ca să nu mai crape upload-ul) – concret

#### Varianta A (cea mai simplă): repari view-ul și form-ul să lucreze “commit=True”

În `authenticate_product_view`:

* setezi `user/email/status/submitted_at` **înainte** de `form.save()`

Dar cum Meta include `email`, și `user` nu e în form, ai 2 opțiuni:

**A1) setezi pe `form.instance` și apoi `form.save()`**

* `form.instance.user = request.user` (dacă e logat)
* altfel lași `email` din form
* apoi `auth_req = form.save()` (commit=True implicit)
* apoi creezi `AuthImage` safe (ai id)

### Varianta B (enterprise): refaci `AuthUploadForm.save(commit=False)` corect

* dacă `commit=False`, returnezi request-ul NESALVAT și NU creezi imaginile
* dacă `commit=True`, salvezi request-ul și creezi imaginile
* iar în view, după `auth_req.save()` mai chemi un `form.save_images(auth_req)`.

---















































## Messaging

### ✅ CE AVEM

#### 1) Inbox conversații (user ↔ user)

* `Conversation` cu `participants` (M2M) → suportă chat între 2+ useri.
* `conversation_list_view`: listează conversațiile userului, ordonate după `-last_updated`.
* `conversation_detail_view`: protejat corect (doar participantul poate vedea conversația) prin `get_object_or_404(..., participants=request.user)`.

#### 2) Trimitere mesaje + atașament (basic)

* `Message` are `text` + `attachment` (`FileField`) → poți trimite text + 1 fișier.
* În `conversation_detail_view`:

  * setezi `msg.conversation`, `msg.sender`
  * salvezi
  * updatezi `conv.last_updated = msg.sent_at`

#### 3) Start conversație (manual, by email)

* `ConversationStartForm` validează existența userului după `recipient_email`.
* `save()` creează conversație nouă + adaugă cei 2 participanți.
* Ai rută separată `incepe/`.

#### 4) Admin existent (minim OK)

* `ConversationAdmin` list_display cu participanți + search.
* `MessageAdmin` list_display + search + list_filter.

---

### ❌ CE LIPSEȘTE (față de plan)

#### 1) Conversație separată pentru fiecare comandă

Plan: “o conversație separată pentru fiecare comandă”.

În cod acum:

* `Conversation` nu are niciun link către `orders.Order`
* nu există constrângere “1 conversație / 1 comandă”
* nu există flux de deschidere automată a chat-ului din pagina comenzii

**Necesare:**

* `Conversation.order = OneToOneField(Order, null=True, blank=True, ...)`
  (sau `FK + UniqueConstraint` pe `order` + `kind`)
* helper `get_or_create(order=...)` folosit din `orders` / `dashboard`

#### 2) Conversații cu suportul (user ↔ echipa Snobistic)

Plan: “conversații cu suportul”.

Acum:

* nu există `kind` / tip conversație
* nu există “contact support” endpoint
* nu există agent asignat / status conversație de suport

**Necesare:**

* `Conversation.kind = DIRECT | ORDER | SUPPORT`
* `Conversation.assigned_to` (admin/shop_manager/support_agent)
* (opțional) `status = OPEN | WAITING_USER | WAITING_AGENT | CLOSED`

#### 3) Mesaje citite / necitite

Plan: “Marchează mesajele citite / necitite”.

Acum:

* nu există `read_at`, `seen_by`, receipts
* nu există `unread_count` pentru inbox

**Necesare (una din variante):**

* `ConversationReadState(conversation, user, last_read_at)`
* și calcul `unread = messages.filter(sent_at__gt=last_read_at).exclude(sender=user).count()`

#### 4) Implicare admin / shop manager (escaladare dispute)

Plan: “poate implica admin / shop manager într-o discuție”.

Acum:

* tehnic poți adăuga participanți în admin (M2M), dar lipsește:

  * flux UI “Escaladează”
  * permisiuni (cine poate escalada)
  * audit (cine a adăugat pe cine, motiv)

#### 5) Queue position în chat-ul de suport

Plan: “poate afișa poziția utilizatorului în lista de așteptare (queue)”.

Acum:

* nu ai concept de queue
* nu e integrat cu `support` (care ar trebui să dețină coada)

**Necesare:**

* integrare cu `support.Ticket` (sau model de queue)
* afișare în template pentru conversațiile `kind=SUPPORT`

#### 6) Atașamente multiple / poze multiple

Planul spune “fișiere/poze”. Tu ai strict **1 attachment per mesaj**.

**Necesare (dacă vrei chat “modern”):**

* model `MessageAttachment` (FK Message) pentru multiple fișiere
* thumbnails pentru imagini + validări

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (calitate, scalare, corectitudine)

#### 1) Conversații duplicate (spam)

Acum `ConversationStartForm.save()` **creează mereu** conversație nouă.
Rezultat: aceeași pereche de useri poate avea 20 conversații “DIRECT”.

**Fix minim:**

* “reuse” dacă există deja o conversație DIRECT între cei doi
* soluție practică:

  * adaugi câmp `direct_key` (hash determinist din user_ids)
  * `UniqueConstraint` pe `direct_key` când `kind=DIRECT`
  * `get_or_create(direct_key=...)`

#### 2) Performanță inbox (N+1 / lipsă prefetch)

`conversation_list_view`:

* nu are `prefetch_related('participants')`
* la render vei genera N+1 când afișezi participanții

**Fix:**

* `Conversation.objects.filter(...).prefetch_related('participants').order_by(...)`

#### 3) Thread fără paginare (explodează în timp)

`conversation_detail_view`:

* `messages_qs = conv.messages.order_by('sent_at')` (toate mesajele)
  Pe conversații lungi devine impracticabil.

**Fix:**

* paginare (ex: ultimele 50) + “Load more”
* `select_related('sender')` pe mesaje

#### 4) Validare atașamente (security)

Acum orice fișier poate fi uploadat:

* fără limită de dimensiune
* fără whitelist MIME
* risc de executabile, arhive, etc.

**Fix minim:**

* validare în form: `size` + `content_type` whitelist
* (ideal) storage privat / antivirus scanning / signed URLs

#### 5) Model hardening: index-uri + Meta.ordering

Recomandări:

* index pe `Conversation.last_updated` (inbox)
* index compus pe `Message(conversation, sent_at)` (thread)
* `Message.Meta.ordering = ('sent_at',)` (și override în view doar când vrei)

#### 6) UX / structură views (start_form inconsistent)

Acum:

* `conversation_list_view` nu include `start_form`
* `start_conversation_view` folosește același template dar în altă rută

**Fix:**

* în `conversation_list_view` afișezi mereu `start_form` (GET)
* iar POST tot acolo (sau păstrezi `incepe/`, dar include form-ul și pe listă)

#### 7) Lipsă “context” pentru ORDER/SUPPORT

Când bagi conversații per comandă și suport, vei avea nevoie de:

* titlu (“Comanda #1234”)
* mesaje de sistem (ex: “AWB adăugat”, “Retur deschis”)
* reguli de blocare după status (ex: chat închis după X zile)

---

#### Verdict scurt

**Messaging-ul actual bifează doar “chat basic user↔user + 1 attachment”**, dar **nu bifează planul** pe punctele critice:

* conversație per comandă
* suport + queue
* read/unread
* escaladare dispute
* anti-duplicate + scalare

---












































## Dashboard

### ✅ CE AVEM

#### Buyer (Cumpărător)

* **Dashboard buyer** (`buyer_dashboard`)

  * număr comenzi (`Order.objects.filter(buyer=user).count()`)
  * număr favorite (încearcă `user.profile.favorites.count()` cu fallback safe)
  * detectare existență dimensiuni (`has_dimensions` pe câmpuri de profil)

* **Lista comenzilor buyer** (`orders_list`)

  * listare comenzi ordonate desc
  * `prefetch_related("payments", "items__product")` (ok)

* **Chat rapid** (`chat_quick`)

  * widget cu ultimele 5 conversații din `messaging` (util)

#### Seller (Vânzător)

* **Dashboard seller** (`seller_dashboard`)

  * KPI: total produse, licitații active, “sold_products” (count comenzi distincte plătite cu item-uri ale sellerului)
  * Wallet: `Wallet.get_or_create()` + `balance`
  * Chart-uri ultimele 6 luni:

    * comenzi per lună (TruncMonth + Count)
    * produse create per lună (TruncMonth + Count)
  * Card profil seller:

    * trust score/class, lifetime sales net, seller level
    * progress bar către next level (RISING/TOP) folosind thresholds din `accounts.services.score`
  * Badge-uri:

    * KYC status/badge
    * 2FA enabled

* **Listări seller**

  * `products_list` + export CSV
  * `auctions_list` + export CSV
  * `sold_list` (comenzi plătite cu produse ale sellerului) cu:

    * `select_related("buyer")`
    * `select_related("shipment")`
    * `prefetch_related("payments")`
    * `Prefetch("items", queryset=OrderItem.filter(product__owner=user))` (corect: vezi doar item-urile tale)

* **Wallet seller** (`wallet`)

  * tranzacții + filtrare pe perioade (daily/monthly/yearly/all)
  * export CSV

* **Acțiuni pe comenzi vândute (parțial)**

  * `generate_awb` → redirect în `logistics:generate_awb`
  * `download_awb` → redirect către pdf/url/tracking (cu verificare ownership prin `items__product__owner=user`)
  * `download_commission_invoice` → redirect către invoices download dacă există

#### Structură & permisiuni

* namespace buyer/seller clar (`/cont/cumparator/...`, `/cont/vanzator/...`)
* `user_passes_test(is_seller/is_buyer)` (există, funcționează)

---

### ❌ CE LIPSEȘTE (față de plan)

#### 1) Buyer: “Favoritele mele” ca pagină/listă

Plan: “afișează Favoritele mele”.

Acum:

* ai doar `favorites_count` în dashboard, fără view/URL pentru listarea efectivă.

**Necesare (în dashboard sau link clar):**

* `buyer_favorites_list` **sau** link către `catalog:favorites` (dacă există deja acolo)

#### 2) Buyer: “Dimensiunile mele” editabile din dashboard

Plan: “și permite modificarea lor”.

Acum:

* ai doar `has_dimensions` boolean, fără form/view de editare.

**Necesare:**

* `buyer_dimensions_update` (ideal reutilizează un form din `accounts`)

#### 3) Buyer: acces la facturi și documente

Plan: “afișează acces la facturi și documente disponibile”.

Acum:

* nu ai listă de facturi pentru buyer (și nici download links) în dashboard.

**Necesare:**

* `buyer_invoices_list` + download (integrare cu `invoices`)

#### 4) Seller: “Istoric Articole” + repostare

Plan: “Istoric Articole și permite repostarea produselor”.

Acum:

* nu există view “istoric” (vândute/expirate/respins) + acțiune “repost/relist”.

**Necesare:**

* `seller_products_history` + acțiuni (repost, duplicate listing, relist auction etc.)

#### 5) Seller: “Articole Magazin” / “Articole Licitație” cu management complet

Planul sugerează separare și management.

Acum:

* doar listă + CSV; nu ai:

  * filtre/segmente (în validare, active, respinse, vândute, etc.)
  * acțiuni clare (edit/relist/cancel)

#### 6) Seller: Setări de cont & setări de vânzător din dashboard

Plan: “afișează setările de cont și de vânzător”.

Acum:

* nu ai views în dashboard pentru:

  * edit seller payout/IBAN + date depozit
  * inițiere KYC / upload documente
  * 2FA enable/disable
    (pot fi în `accounts`, dar planul cere acces clar din “cont”.)

#### 7) Shop Manager dashboard (lipsește complet)

Plan:

* produse în validare
* approve/reject
* istoric validări

Acum:

* nu există rute, views, template-uri, permisiuni pentru shop manager.

#### 8) Admin dashboard (lipsește complet)

Plan:

* rapoarte (comisioane/vânzări/retururi/scoruri)
* setări globale configurabile (comisioane, buyer protection, termene retur/AWB, limite licitații, parametri scor)

Acum:

* nimic din astea în `dashboard`.

#### 9) Seller: acțiuni reale pe colete/retur (nu placeholder)

Ai endpoint-uri, dar sunt **doar** `messages.info("în curând")`:

* `upload_package_photos`
* `mark_sent`
* `view_package_photos`
* `initiate_return_seller`

Asta e lipsă funcționalitate, nu doar “de îmbunătățit”.

#### 10) “Facturi + documente” seller (în cont)

Planul dashboard zice “acces la facturi și documente”.
Acum ai doar **commission invoice download**, dar nu ai:

* listă facturi comision
* listă documente (awb, certificate, etc.) în cont

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT

#### 1) Logică roluri inconsistentă (`is_seller` / `is_buyer`)

Ai 3 surse:

* `profile.role_seller`
* `sellerprofile`
* fallback `user.is_seller`

Riscul: edge cases (user fără profile / user dual role).

**Recomandare:**

* o singură sursă de adevăr: `Profile.can_buy`, `Profile.can_sell`, `Profile.role_admin`, `Profile.role_shop_manager`
* helpers în `accounts.permissions` (și le folosești peste tot)

#### 2) Bug la calculul lunilor (year rollover)

Codul actual:

```py
y = today.year - ((today.month - i - 1) // 12)
```

În Python, `//` cu negative face floor → îți poate strica anul în anumite luni.

**Fix:**

* folosește `dateutil.relativedelta(months=i)` sau calc “total_month_index”

#### 3) KPI “sold_products” e de fapt “număr comenzi”, nu “articole vândute”

Acum:

```py
Order.objects.filter(...).distinct().count()
```

Asta e count comenzi, nu count item-uri.

**Recomandat să ai 2 metrici:**

* `orders_sold_count`
* `items_sold_count = OrderItem.objects.filter(product__owner=user, order__payment_status=paid).count()`

#### 4) `select_related("shipment")` + template safety

În view e ok, dar în template ai grijă la `order.shipment` dacă e OneToOne și nu există (poate ridica `DoesNotExist`).

#### 5) Export CSV: encoding + performanță + escaping

* pentru Excel RO de multe ori vrei `utf-8-sig`
* la volume mare: `.iterator()` + evită `build_absolute_uri` în loop dacă nu e necesar
* separatori / newline handling

#### 6) Wallet: index și timezone

* filtrele daily/monthly/yearly ar trebui să fie coerente cu timezone (ai `timezone.now()` ok, dar recomand index pe `WalletTransaction(user, date)`)

#### 7) `download_commission_invoice` — ownership hardening

E ok că filtrezi `seller=user`, dar ca enterprise:

* verifică și că `order` chiar conține item-uri ale sellerului (în caz de bug de data-integrity)
* tratează cazul în care invoice există dar nu are fișier disponibil (dacă sistemul de invoices e mixt)

#### 8) Dashboard home unificat pentru user “buyer+seller”

Acum ai rute separate.
**Recomandare:**

* `/cont/` care decide automat sau afișează tabs (buyer/seller)

---

### Verdict

`dashboard` e **un schelet bun** (seller stats + listări + wallet + buyer orders + chat widget), dar **nu e plan-compliant** încă pentru:

* favorites list + edit dimensiuni + facturi buyer
* istoric produse + repost seller
* shop manager panel
* admin panel (rapoarte + global settings)
* acțiuni reale pe colete/retur (acum sunt placeholder)

---










































## Payments

### ✅ CE AVEM

#### Plăți online (Stripe) pentru comenzi

* `payment_confirm(order_id)`

  * validează ownership: `Order(id=..., buyer=request.user)` ✅
  * creează `Payment(provider=STRIPE, status=PENDING, amount=order.total, currency=...)` ✅
  * pornește **Stripe Checkout Session** și face redirect 303 ✅
  * salvează `stripe_session_id` ✅
* `payment_success` / `payment_failure`

  * pagini feedback post-checkout (corect: te bazezi pe webhook pentru “paid”) ✅

#### Stripe Webhook (plată comandă + top-up wallet)

* `stripe_webhook`

  * verifică semnătura cu `STRIPE_WEBHOOK_SECRET` ✅
  * pe `checkout.session.completed`:

    * dacă găsește `Payment` după `stripe_session_id`: marchează `Payment=SUCCEEDED`, setează `stripe_payment_intent_id`, salvează `raw_response`, apoi `order.mark_as_paid()` ✅
    * dacă `metadata.purpose == wallet_topup`: creditează wallet + `WalletTransaction(TOP_UP)` ✅
    * idempotency parțial:

      * pentru order payment: dacă `Payment.status == SUCCEEDED` => return ✅
      * pentru top-up: dacă există deja `WalletTransaction` cu `external_id=payment_intent_id` => return ✅

#### Wallet intern (model + tranzacții)

* `Wallet` OneToOne cu user ✅
* `WalletTransaction` tipuri: TOP_UP / WITHDRAW / ORDER_PAYMENT / REFUND / SALE_PAYOUT ✅
* wallet auto-creat la user nou (`signals.py` + `apps.ready()`) ✅

#### Plată din wallet (service)

* `services.charge_order_from_wallet(order, user)`

  * validează sold
  * creează `Payment(provider=WALLET, status=SUCCEEDED)` ✅
  * debitează wallet + `WalletTransaction(ORDER_PAYMENT)` ✅
  * `order.mark_as_paid()` (escrow held) ✅

#### Refund (service)

* `services.refund_payment(payment, amount, ...)`

  * verifică `refundable_amount`
  * blochează escrow (prin `order.mark_escrow_disputed()`) ✅
  * refund în wallet (și opțional Stripe) + `WalletTransaction(REFUND)` ✅
  * creează `Refund` + status final (în varianta sync) ✅

#### Admin

* admin complet pentru `Payment / Wallet / WalletTransaction / Refund` ✅

---

### ❌ CE LIPSEȘTE (față de planul `payments`)

#### 1) Buyer Protection Fee (calcul + stocare + folosire în total)

Plan: “Calculează și gestionează taxa de Buyer Protection”.

Acum:

* nu există câmpuri / calcul / configurare pentru buyer protection fee.
* `Payment.amount = order.total` dar nu ai breakdown.

**Necesare:**

* model/config pentru fee (fixed/percent, praguri, TVA dacă e cazul)
* persistare pe `Order` (ex: `buyer_protection_fee`) și includere clară în total

#### 2) Comision platformă pe nivel seller + “Tu primești”

Plan: “Aplică comisionul de platformă pe baza nivelului seller… și calculează netul”.

Acum:

* zero logică de:

  * rate comision per nivel (Amator/Rising/Top/VIP)
  * calcul net seller / platform_fee
  * persistare

**Necesare:**

* fee engine: `platform_fee`, `seller_net`, eventual `processing_fee`
* legare la `accounts.SellerProfile.seller_level`

#### 3) Escrow complet: held → release → payout către wallet seller

Plan: “reținere bani, eliberare după confirmare/expirare retur, payout către wallet seller”.

Acum:

* ai doar `order.mark_as_paid()` (presupus escrow=HELD).
* lipsește complet:

  * serviciu/job de **release escrow**
  * creare `WalletTransaction(SALE_PAYOUT)` la seller + creditare sold
  * handling retur/dispute după payout (reversals/adjustments)

#### 4) Ramburs (Cash on Delivery) ca flow real

Plan: “ramburs mereu disponibil + încasare curier + decontare seller wallet + limite”.

Acum:

* există `Payment.Provider.CASH`, dar:

  * nu există metodă de checkout pentru ramburs
  * nu există confirmare de încasare/settlement
  * nu există decontare către seller wallet
  * nu există reguli pe trust score / praguri / taxe ramburs

#### 5) Suport pentru alți procesatori (ex: Plati.ro)

Plan: “suport procesatori”.

Acum:

* doar Stripe.

#### 6) Refund-uri complete async (webhook-driven)

Ai `refund_payment()` care poate chema Stripe refund, dar lipsește “plumbing”:

* webhook handling pentru `charge.refunded`, `refund.updated` / stări async
* retry / failure handling (FAILED vs PENDING real)

#### 7) Integrare cu `invoices` pentru facturi de payment-fees

Planul mare zice că invoices emite buyer protection / transport etc.
În payments nu există trigger/integrare pentru emitere facturi.

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT

#### 1) `wallet_withdraw` nu trebuie să scadă soldul direct

Acum:

* scazi `wallet.balance -= amt` instant și creezi tranzacție WITHDRAW.

Corect enterprise:

* `WithdrawalRequest(status=PENDING/APPROVED/REJECTED/PAID_OUT)`
* soldul se blochează/rezervă (sau scade) doar când e aprobat/paid_out

#### 2) Atomicitate + concurență (race conditions)

În webhook / wallet charge / withdraw:

* lipsesc `transaction.atomic()` + `select_for_update()` pe `Wallet` / `Payment` / `Order`.

**Riscuri:**

* dublu credit la top-up în anumite edge cases
* dublu debit la wallet charge
* două webhook-uri simultane => stare inconsistentă

#### 3) Constrângeri unice / idempotency mai strictă

Recomandări minime:

* `Payment.stripe_session_id` -> `unique=True` când e setat (sau UniqueConstraint condiționat dacă vrei)
* `WalletTransaction` unique pe `(user, transaction_type, external_id)` când external_id există
* la `Payment` pentru orders: “o singură plată SUCCEEDED per order” (în DB constraint sau logică)

#### 4) `raw_response` salvează StripeObject (potențial incompatibil JSONField)

În `payment_confirm`:

* `payment.raw_response = session` (StripeObject) → poate crăpa serializarea.

Fix:

* salvează `data` ca dict: `session.to_dict()` / `dict(session)` (în funcție de SDK), sau `json.loads(session.to_json())`

#### 5) Payment attempts management (cleanup)

Un order poate genera multiple Payment-uri PENDING/FAILED.
Acum:

* nu anulezi/expirezi încercările vechi
* nu marchezi `FAILED/CANCELED` în DB pe cancel.

Recomandat:

* când pornești o plată nouă: setezi încercările PENDING vechi la CANCELED
* în `payment_failure`: marchezi ultimul payment ca FAILED/CANCELED (cu verificare status)

#### 6) Webhook: acoperire evenimente Stripe mai robuste

Acum tratezi doar `checkout.session.completed`.
Minim util în practică:

* `checkout.session.async_payment_succeeded / failed`
* opțional: `payment_intent.succeeded` pentru robustete
* `charge.refunded` pentru sincronizare refund statuses

#### 7) Duplicare logică roluri (`is_seller`)

Ai `is_seller` duplicat (dashboard + payments).
Recomandare:

* mută în `accounts.permissions` și importă peste tot (single source of truth)

#### 8) Wallet withdraw: lipsă validări și audit

* IBAN: doar string, nu ai validare reală (format/country)
* nu păstrezi beneficiary/account holder
* nu ai audit trail de procesare (cine a aprobat, când, referință bancară)

#### 9) UX: succes Stripe nu validează session (opțional)

Acum `wallet_topup_success` doar afișează mesaj.
Ok ca MVP, dar dacă vrei:

* citești `session_id` din query și validezi că aparține userului (doar ca “nice-to-have”).

---
### Verdict

`payments` e **bun ca MVP** pentru:

* Stripe checkout pentru comenzi
* webhook care marchează plăți + top-up wallet
* wallet intern + charge din wallet
* refund service (parțial)

Dar **nu e plan-compliant** încă pentru:

* buyer protection fee
* comision platformă + “tu primești”
* escrow release + payout către seller wallet
* ramburs (COD) ca flux real
* procesatori alternativi (Plati.ro)
* refund-uri async complete + integrare cu invoices










































## Support

### ✅ CE AVEM

#### Ticketing (MVP funcțional, end-to-end)

* `Ticket` model cu:

  * `owner`, `subject`, `description`
  * `category` (general/order/return/payment)
  * `status` (open/in_progress/closed)
  * `priority` (low/medium/high)
  * timestamps ✅
* `TicketMessage` model:

  * FK la `ticket`, `author`, `text`, `created_at` ✅

#### Legături cu Orders / Returns (în plan)

* `Ticket.order` (FK `orders.Order`) ✅
* `Ticket.return_request` (FK `orders.ReturnRequest`) ✅

#### Views + flow user

* `tickets_list`: listă tichete owner ✅
* `ticket_create`: creare tichet ✅
* `ticket_detail`: thread mesaje + reply ✅
* acces control:

  * owner sau agent (`is_staff` / `support.change_ticket`) ✅

#### Agent update (minimal)

* `ticket_update` cu `@user_passes_test(user_is_agent)` ✅
* `TicketUpdateForm` permite update: status/priority/category + order/return_request ✅

#### Form-uri

* `TicketForm`:

  * permite legarea la `order` (opțional)
  * queryset orders: buyer OR seller (prin `items__product__owner`) + distinct ✅ (presupunând că relațiile sunt corecte în `OrderItem/Product`)
* `TicketMessageForm` pentru reply ✅

#### Admin

* Admin pentru `Ticket` + `TicketMessage`, filtre + search + autocomplete_fields ✅

#### “Queue” endpoint există

* `chat_queue` view + template placeholder (stub) ✅

---

### ❌ CE LIPSEȘTE (față de planul `support`)

#### 1) Coada reală (queue) + poziție reală (plan: “you are #X in queue”)

Acum:

* `chat_queue` calculează position/eta din metode inexistente pe user (`chat_queue_position`, `chat_queue_eta`) => practic fake/stub ❌
  Lipsește complet:
* ordonare deterministă a tichetelor (prioritate + vechime + status)
* poziție per tichet (nu per user generic)
* ETA/SLA bazat pe workload și agenți

#### 2) Integrare cu `messaging` pentru conversația efectivă (dacă alegi varianta)

Planul cere integrare (sau alternativ: ticketing complet cu atașamente + read/unread).
Acum:

* `TicketMessage` e thread intern separat ❌
  Lipsește:
* creare/legare `Conversation` de suport
* read/unread
* atașamente
* posibilitate de “3-way” (buyer + seller + support) în dispute

#### 3) Atașamente (poze/fișiere) pe tichet / mesaj

Planul acoperă retururi, neconformități, AWB etc. => ai nevoie de dovezi.
Acum:

* `TicketMessage` = doar text ❌
  Lipsește:
* `TicketAttachment` (FileField/ImageField) + storage + UI upload

#### 4) Roluri/permisiuni “Support Agent” mai curate

Acum:

* agent = `is_staff OR has_perm("support.change_ticket")`
  Lipsește:
* grup “Support Agent”
* permisiuni separate: view / reply / assign / close / internal_note ❌

#### 5) “Workflow” suport real (statusuri + waiting states)

Acum ai doar: open / in_progress / closed.
Lipsește uzual (și te ajută la queue):

* `waiting_customer`, `waiting_seller`, `escalated`, `resolved`, `duplicate/rejected` ❌

#### 6) Instrumente de dispute (payment/escrow/return) ca acțiuni concrete

Plan: suport interacționează cu retur/escrow.
Acum:

* ai category “payment”, dar nu ai:

  * acțiuni de tip: “mark escrow disputed”, “initiate refund”, “force cancel”, “request photos”, “notify seller” ❌

#### 7) Agent-side UI real (listă tichete globale)

Ai doar:

* `tickets_list` pentru owner.
  Lipsește:
* listă pentru agenți: “Open tickets”, “Assigned to me”, “Unassigned”, filtrare/sortare ❌

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT

#### 1) Acces + query hardening (minor security/cleanliness)

În `ticket_detail`:

* `get_object_or_404(Ticket, id=ticket_id)` apoi verifici acces.
  E ok, dar mai “tight”:
* pentru user: `get_object_or_404(Ticket, id=ticket_id, owner=request.user)`
* pentru agent: separat (sau condition-based), ca să reduci surface/timing differences.

#### 2) N+1 / performanță

* `ticket_detail` face `ticket.messages.order_by("created_at")` fără prefetch.
* `tickets_list` fără `select_related` / `prefetch_related`.
  Recomand:
* `Ticket.objects.filter(...).select_related("order","return_request").prefetch_related("messages")` unde are sens.

#### 3) Coliziune semantică în context (`messages`)

În `ticket_detail` trimiți context key `"messages": ticket.messages...`
Ai și `from django.contrib import messages` (framework).
Nu “crapă”, dar e confuz în template/debug.
Recomand:

* redenumește context key la `thread_messages` sau `ticket_messages`.

#### 4) `TicketForm` order queryset poate fi fragil

`Q(items__product__owner=user)` presupune:

* `Order.items` related_name = `items`
* `OrderItem.product.owner` = seller
  Dacă ai altă schemă (seller pe order item / pe product alt field), queryset-ul nu prinde corect.
  Recomand:
* mută această logică într-un `OrderQueryService.for_user(user)` ca “single source of truth”.

#### 5) Lipsă “last_activity_at” / audit

Nu ai:

* `assigned_to`, `assigned_at`, `closed_by`, `closed_at`, `last_activity_at`
  Fără astea:
* queue/ETA devine imposibil de făcut corect
* audit slab (“cine a rezolvat?”)

#### 6) Lipsă note interne

Support real are nevoie de:

* `TicketMessage.is_internal` (vizibil doar agent)
* altfel agenții nu pot colabora fără să vadă clientul.

#### 7) Notificări

Lipsește complet:

* email / in-app notifications la create/reply/status change.
  MVP recomandat:
* email către owner când agent răspunde
* email către agent când owner răspunde (sau “assigned_to”).

#### 8) Bug de organizare fișiere (din ce ai lipit)

Ai “apps.py” dar conținutul e de `admin.py` (pare copy/paste greșit).
Verifică să existe:

* `support/apps.py` cu `AppConfig(name="support")`
  altfel poți avea probleme de config/migrations în timp.

---

### Verdict

`support` e **MVP solid de ticketing text-based**: creezi tichet, scrii mesaje, ai agent update, ai link la order/return.

Dar **nu e plan-compliant** la părțile grele:

* **queue real + poziție/ETA**
* **atașamente**
* **integrare cu messaging / read-unread / dispute flows**
* **agent-side workflow** (assign, statusuri reale, audit)

---

### P0: “Support v1 plan-compliant” (ce aș face eu în ordine)

1. **Modele**

* `Ticket.assigned_to`, `assigned_at`, `last_activity_at`, `closed_by`, `closed_at`
* `TicketMessage.is_internal`, `read_at` (sau model separat pentru read receipts)
* `TicketAttachment` (FK Ticket sau TicketMessage, FileField/ImageField, uploaded_by)

2. **Agent UI**

* `/suport/agent/tichete/` (unassigned, assigned_to_me, all_open)
* acțiuni: assign/unassign, change status, request more info

3. **Queue real**

* definești o regulă deterministă:

  * open + unassigned, ordonate: priority desc, created_at asc
* poziția unui tichet = count(tickets înaintea lui)
* ETA simplu: `position * avg_handle_time` (config global)

4. **Integrare cu messaging** (dacă mergi pe varianta asta)

* `Ticket` are `conversation = OneToOneField(messaging.Conversation, null=True)`
* la creare ticket => creezi conversație suport (user + support)
* pentru dispute => adaugi seller în conversație (3-way)











































## Invoices

### ✅ CE AVEM

#### Model `Invoice` (MVP ok)

* Tipuri: `product`, `shipping`, `commission`, `return` ✅
* Statusuri: `draft`, `issued`, `cancelled` ✅ (dar vezi observația la “issued_at” mai jos)
* FK la `orders.Order` cu `related_name="invoices"` ✅
* Roluri:

  * `buyer` obligatoriu ✅
  * `seller` opțional (bun pentru comision / facturi către seller) ✅
* Sume:

  * `net_amount`, `vat_percent`, `vat_amount`, `total_amount` ✅
* `currency` ✅
* Timestamps: `issued_at`, `paid_at`, `created_at`, `updated_at` ✅
* Numerotare automată în `save()` (SNB-YYYYMMDD-000001) bazat pe `pk` ✅

#### Views (HTML + PDF)

* `invoice_detail_view` (HTML) ✅
* `invoice_pdf_view` (PDF via WeasyPrint, cu fallback 501 dacă lipsește) ✅
* Control acces:

  * buyer vede factura lui
  * seller vede factura unde e seller
  * staff vede tot ✅

#### Admin

* `InvoiceAdmin` cu list_display + filtre + search ✅

> Notă: **nu ai lipit `invoices/urls.py`** (în paste, secțiunea “urls.py” e de fapt modelul `Invoice`). Deci nu pot valida 100% rutele, dar views sunt ok ca structură.

---

### ❌ CE LIPSEȘTE (față de planul `invoices`)

#### 1) Listare facturi (portal) pentru buyer / seller / admin

Planul cere “permite descărcarea facturilor” din cont/panou.
Acum ai doar:

* detaliu + pdf **dacă știi `pk`** ❌
  Lipsește:
* `invoice_list_view` buyer: toate facturile lui
* `invoice_list_view` seller: facturile unde e seller (mai ales comision)
* filtre: perioadă / tip / status

#### 2) Linii de factură (InvoiceLine / InvoiceItem)

Ai doar totaluri globale.
Lipsește:

* entitate pentru linii: produs/transport/buyer protection/comision/discount/ramburs fee etc. ❌
  Fără linii, PDF-ul e “black box” (nu explică ce e facturat).

#### 3) Generare automată a facturilor la evenimente (checkout/comision/retur)

Planul implică:

* facturi comision către seller
* facturi shipping + buyer protection către buyer
* storno/return invoices la retur
  În cod **nu există** servicii/signals care să emită facturi când:
* comanda devine plătită
* escrow se eliberează / se face refund
* returul e aprobat/rambursat ❌

#### 4) Persistența PDF-ului (stocare/caching/audit)

Plan: “stochează sau generează fișierul PDF”.
Acum:

* PDF se generează on-the-fly, nu se salvează ❌
  Lipsește:
* `pdf_file = FileField(...)` + regenerare/caching + versioning

#### 5) Serii / numerotare configurabilă

Ai `invoice_number`, dar lipsește:

* concept de `series` (ex: SNB, SNB-COM, SNB-RET)
* reset anual / per tip (dacă vrei contabil “curat”)
* mecanism de lock / generator atomic (dacă treci pe contor per zi/per serie, nu doar pk) ❌

#### 6) Integrare externă (opțional, dar planul o menționează)

Pentru “factură de produs emisă automat” (PJ / integrare):

* lipsește `external_provider`, `external_id`, status sync, hooks ❌

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT

#### 1) `issued_at` vs `status` (inconsistență contabilă)

Acum:

* `issued_at = auto_now_add=True` chiar și când status = `draft`.
  Recomand:
* `created_at` pentru creare
* `issued_at` setat **doar** când treci în `ISSUED` (manual sau service).

#### 2) TVA/Total sunt “manuale” (risc de date incoerente)

Ai câmpuri separate, dar nu ai:

* validare/calcul garantat în `clean()` sau `save()`
  Recomand:
* calculezi mereu `vat_amount` și `total_amount` din `net_amount` + `vat_percent` (cu `Decimal` + rounding consistent).

#### 3) `save()` cu double-save (ok ca MVP, dar ai alternative mai curate)

E acceptabil, dar:

* dacă mai târziu vrei contor pe zi/serie, vei avea nevoie de generator atomic (`transaction.atomic()` + tabel de sequence).

#### 4) Redirect la acces denied

Acum:

* redirect la `"dashboard:orders_list"` (poate să nu existe / poate fi nepotrivit pentru seller).
  Recomand:
* `"dashboard:home"` sau `"dashboard:invoices_list"` (după ce-l creezi).

#### 5) PDF reliability în production

* `base_url=request.build_absolute_uri("/")` e ok, dar în prod WeasyPrint poate să nu rezolve static/media cum crezi.
  Recomand:
* setări clare pentru base URL / static absolute
* test pe server (mai ales cu CSS + imagini).

#### 6) FK `order` cu CASCADE (discutabil)

* În practică, facturile ar trebui să rămână (audit).
  Dacă tu nu ștergi niciodată `Order`, e ok; altfel, ia în calcul `PROTECT`.

#### 7) Scenariu multi-seller

Planul sugerează facturi de comision către seller.
Dacă un `Order` poate avea produse de la mai mulți sellers:

* ai nevoie de **invoice per seller** (comision) + eventual invoice buyer pentru fees.
  Modelul suportă `seller`, dar lipsește logica de generare per seller.

---

### Verdict

`invoices` este **MVP bun** pentru: model + acces + HTML + PDF on-demand + admin.

Ca să bifeze **planul complet**, trebuie în primul rând:

* **invoice list view** (buyer/seller)
* **invoice lines**
* **generare automată pe evenimente** (paid / refund / retur / comision)
* **issued_at corect** + calc TVA consistent
* opțional: **PDF storage** + serii/numerotare configurabilă

---















































## Logistics

### ✅ CE AVEM

#### Modele (MVP solid)

* `Courier` cu:

  * `slug` unic, `tracking_url_template`, `is_active` ✅
  * helper `get_tracking_url()` / `effective_tracking_url` (din ce ai descris) ✅
* `ShippingRate`:

  * interval greutate + `base_price` + `currency` ✅
  * estimare livrare `delivery_days_min/max` ✅
* `Shipment`:

  * legat de `Order` (în cod: `order.shipment` => **OneToOne**) ✅
  * `seller`, `courier`, `provider` (Curiera/Manual) ✅
  * tracking fields: `tracking_number`, `external_id`, `tracking_url`, `label_url` ✅
  * opțiuni: `weight_kg`, `service_name`, `cash_on_delivery`, `cod_amount` ✅
  * uploads: `label_pdf`, `package_photo`, `parcel_photo` ✅
  * status flow (pending → label_generated → handed → in_transit → delivered → returned) ✅

#### Flow AWB (seller-only + escrow gate)

* `generate_awb_view`:

  * verifică seller + “are produse în order” ✅
  * **blochează** dacă nu e `PAYMENT_PAID` + `ESCROW_HELD` ✅
  * creează `Courier(curiera)` la nevoie ✅
  * dacă nu există Shipment → call Curiera + persist Shipment ✅
  * dacă există Shipment → update local (poze etc.) fără regenerare ✅
  * set `shipment.status = LABEL_GENERATED` ✅

#### Servicii

* `services/curiera.py`:

  * structură ok (dataclass result, timeout, error handling) ✅
* `services/shipping.py`:

  * calc shipping cost pe greutate + rate selection ✅

#### Admin

* Admin pentru Courier/ShippingRate/Shipment cu list/filter/search ✅

#### URL-uri (minim)

* `awb/<order_id>/` pentru seller generate AWB ✅

---

### ❌ CE LIPSEȘTE (față de planul `logistics`)

#### 1) Tracking pentru buyer (UI + URL)

Planul cere: “buyer vede tracking-ul coletelor”.
În cod:

* nu ai view/URL de tip `track/<tracking_number>/` sau “Tracking” în `orders:order_detail` pentru buyer ❌

#### 2) Sincronizare status (polling/webhook) cu provider

Ai enum-uri bune în Shipment, dar:

* nu există job/management command care să actualizeze `Shipment.status` din Curiera ❌
* nu există “status history” (audit) ❌

#### 3) Dashboard seller: “Colete Netrimise” / “Colete Trimise”

Planul cere liste.
În cod:

* nu există views/URL-uri pentru aceste două liste ❌

#### 4) Regula de 3 zile AWB + penalizare/scor/anulare

Planul cere:

* deadline + acțiune (scădere scor / anulare).
  În cod:
* nu ai `awb_due_at` / cron / management command / emit event către `accounts` ❌

#### 5) Provider MANUAL “pe bune”

Modelul suportă `MANUAL`, dar:

* nu ai view/form dedicat pentru “introducere AWB manual” (tracking_number + courier + link) ❌

#### 6) Multi-seller shipping (CRITIC pentru marketplace)

Aici e blocant:

* `Shipment` e OneToOne cu `Order` → **nu poți avea 1 comandă cu 2 vânzători** ❌
  În momentul în care există order cu itemi de la 2 sellers:
* seller A creează `order.shipment`, seller B nu mai poate (logic + DB) → comportament greșit inevitabil.

#### 7) Poze obligatorii (validare reală)

Planul spune “asociază pozele obligatorii…”
În cod:

* câmpuri există, dar nu impui “nu trece în LABEL_GENERATED / SHIPPED fără ambele poze” ❌

#### 8) Tarifare “pe zonă / tip serviciu / ramburs” (mai aproape de plan)

Ai greutate + rate intern, dar lipsește:

* zonare / servicii (standard/express/ramburs) ca reguli coerente ❌
* quote din Curiera (dacă vrei tarif real) ❌

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (calitate, consistență, edge cases)

#### 1) Contradicție majoră cu planul `payments`: COD “mereu disponibil” vs interzis în logistics

În `payments` plan: ramburs mereu disponibil.
În `generate_awb_view`: ramburs blocat + mesaj “nu este permis”.
Asta trebuie decis clar:

* ori Snobistic = escrow-only (și modifici planul + scoți câmpurile COD din form),
* ori implementezi COD complet (payments + logistics + comisioane + limite + decont curier).

#### 2) `order.shipping_status = SHIPPED` când ai doar AWB

AWB generat ≠ predat curierului.
Mai corect:

* la label generated → status de tip `LABEL_GENERATED`
* la predare/pickup → `HANDED/IN_TRANSIT`
* la confirmare → `DELIVERED`

#### 3) Idempotency + concurență la creare shipment

Acum, dacă se dă dublu submit / refresh:

* riști dublare call la provider (mai ales dacă shipment nu există încă în DB).
  Recomand:
* `transaction.atomic()` + lock (sau `select_for_update` pe Order) + create shipment înainte de call (status pending), apoi update cu rezultat.

#### 4) Leakage de date în error mesaj

În `curiera.py`:

* `error_message=f"... {response.text}"` poate conține detalii sensibile și ajunge la user.
  Recomand:
* log server-side, iar către user mesaj generic + cod de eroare.

#### 5) `services/shipping.py` presupune `product.weight_g` non-null

Ai:

```py
weight_g = item.product.weight_g or DEFAULT_ITEM_WEIGHT_G
```

Dacă `Product` nu are `weight_g`, ai AttributeError.
Recomand:

* `getattr(item.product, "weight_g", None) or DEFAULT_ITEM_WEIGHT_G`

#### 6) Shipment la nivel de order dar verificarea e per seller (inconsistență structurală)

Verificarea asta e ok:

```py
order.items.filter(product__owner=user).exists()
```

Dar dacă păstrezi Shipment one-to-one cu order, tot e incompatibil cu marketplace.
Refactor obligatoriu:

* `Shipment(order FK, seller FK)` + `UniqueConstraint(order, seller)`.

#### 7) Validare poze obligatorii

Ai câmpurile, dar trebuie logică:

* dacă treci de pending → label_generated, impui `package_photo` + `parcel_photo`.
  Ideal: validare în form/service, nu doar în template.

#### 8) UX: câmpuri COD în form, dar view le interzice

Asta e confuz și pentru seller.
Dacă rămâi escrow-only:

* scoate `cash_on_delivery` și `cod_amount` din form și template.

#### 9) `Courier.get_or_create` la fiecare request

Nu e grav, dar mai curat:

* seed via migration/fixture sau `post_migrate`, apoi doar `.get(slug="curiera")`.

#### 10) Lipsește “buyer tracking URL” integrat în order detail

Chiar dacă ai `Shipment.effective_tracking_url`, nu ai locul din UI unde să apară.

---

## Prioritate “ce reparăm prima” (ca să nu pierdem timp)

1. **Multi-seller fix**: `Shipment` devine per (order, seller). (Blocant marketplace)
2. **Tracking buyer + UI**: view/URL + afișare în `orders:order_detail`.
3. **Decizie COD vs escrow-only** și aliniere payments/logistics (acum e inconsistent).
4. **Status flow corect**: nu SHIPPED la AWB; introduce “label_generated / handed_to_courier”.
5. **Regula 3 zile**: câmp deadline + management command + emit event către accounts (scor).
6. **Sync status Curiera**: polling job + status history.
7. **Poze obligatorii**: validare hard înainte de trecerea în “shipped”.

---







































## Wallet

### ✅ CE AVEM

* Nimic încă (aplicația `wallet` nu există în proiect) ✅

---

### ❌ CE LIPSEȘTE (față de planul `wallet`)

#### 1) Aplicația în sine

* `wallet/` app (settings, urls, views, templates, admin, tests) ❌

#### 2) Modele (schema minimă)

* `Wallet` (1:1 user) cu:

  * `currency`
  * `available_balance`, `pending_balance`, `locked_balance`
  * timestamps ❌
* `WalletTransaction` / ledger:

  * `tx_type`, `direction`, `amount`, `currency`, `status`
  * legături: `order`, `return_request`, `payment_transaction`, `invoice` (opționale)
  * `idempotency_key` unic
  * timestamps ❌
* `WithdrawalRequest`:

  * `amount`, `iban` (snapshot), `status`, note admin, timestamps ❌

#### 3) Logică atomică (anti-race conditions)

* service layer:

  * `get_or_create_wallet(user)`
  * `credit/debit/move/lock/unlock`
  * tranzacții DB + `select_for_update()` ❌

#### 4) Integrare cu `payments` (escrow → wallet)

* când escrow se eliberează:

  * credit seller în wallet
* când există refund:

  * debit/lock seller sau credit buyer (în funcție de flow)
* idempotency pe evenimente (webhooks/retries) ❌

#### 5) Integrare cu `orders` + `support`

* return/dispute flows:

  * lock/unlock, audit, tranzacții corecte ❌

#### 6) Referral bonus 1% după finalizare fără retur

* calcul, eligibilitate (după expirare retur), credit în wallet inviter
* idempotency (bonus o singură dată) ❌

#### 7) Plată cu wallet la checkout

* opțiune “Plătește din wallet”
* validare sold + debit atomic + rollback la eșec ❌

#### 8) UI în `dashboard`

* Wallet overview (sold + ledger)
* filtre + pagină retrageri (create/list/status) ❌

#### 9) Admin

* admin pentru Wallet / Transactions / Withdrawals
* acțiuni admin (manual adjustment, approve/reject payout) ❌

#### 10) Setări globale

* `MIN_WITHDRAWAL_AMOUNT`, `SNOBISTIC_CURRENCY`, `REFERRAL_BONUS_PERCENT`
* eventual reguli risk (KYC/scor minim) ❌

#### 11) Teste

* concurență, idempotency, solduri, integrare escrow → credit ❌

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (ca design, înainte să scrii cod)

#### 1) Decide “ledger = adevărul” + balanțe cached

* Regula corectă: **ledger entries sunt sursa de adevăr**, iar balanțele din Wallet sunt cache actualizat atomic.

#### 2) Standardizează tipurile de tranzacții (enum) și statusurile

Minim recomandat (și suficient pentru început):

* `SALE_PAYOUT`, `REFERRAL_BONUS`, `REFUND_IN`, `FEE_DEBIT`, `WITHDRAWAL`, `MANUAL_ADJUSTMENT`

#### 3) Idempotency peste tot

* orice credit/debit rezultat din “eveniment” trebuie să aibă `idempotency_key` unic.

#### 4) Integrare cu `accounts` pentru payout info

* IBAN “source of truth” în `accounts` (seller settings).
* în `WithdrawalRequest` salvezi snapshot IBAN la momentul cererii.

#### 5) Definește clar când banii sunt:

* `pending` (ex: referral neeligibil încă)
* `locked` (dispute/retur)
* `available` (cashout/cheltuire)

---

### Blueprint implementare (ordine corectă, fără să te blochezi)

#### Pas 1 — Creezi app + modele + migrații

* `wallet/apps.py`, `wallet/models.py`, `wallet/admin.py`
* `Wallet`, `WalletTransaction`, `WithdrawalRequest`

#### Pas 2 — Service layer atomic

* `wallet/services/wallet.py`:

  * `credit()`, `debit()`, `move_pending_to_available()`, `lock()`, `unlock()`
  * toate în `transaction.atomic()` + `select_for_update()` pe Wallet

#### Pas 3 — Integrare minimă cu escrow release

* un hook (signal/service call) când:

  * `payments` marchează escrow ca released → `WalletTransaction(SALE_PAYOUT, credit)` seller

#### Pas 4 — UI minimal în dashboard

* `/wallet/` (sold + ultimele tranzacții)
* `/wallet/withdraw/` (cerere retragere)
* `/wallet/withdrawals/` (listă)

#### Pas 5 — Referral bonus (job)

* management command / scheduled:

  * “comenzi finalizate + retur expirat + fără retur” → credit inviter cu 1%

---

### Structură recomandată de fișiere (când îl creezi)

* `wallet/models.py`
* `wallet/services/wallet.py`
* `wallet/admin.py`
* `wallet/views.py`
* `wallet/urls.py`
* `wallet/templates/wallet/...`
* `wallet/management/commands/apply_referral_bonuses.py` (mai târziu)
* `wallet/tests/...`

---
