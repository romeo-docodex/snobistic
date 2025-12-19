Perfect, hai să vedem ce **mai lipsește** raportat la plan 1 + plan 2 + plan 3, ținând cont de codul pe care l-ai pus acum (`catalog/views.py`, `views_wizard.py`, `urls.py`, `models.py`).

Mă concentrez DOAR pe `catalog` și pe ce se vede clar în cod.

---

## 1. Date de configurare (fixtures / script de seed)

Încă lipsesc:

1. **Categorii + subcategorii populate conform planului**

   * Cele 3 categorii root fixe: Îmbrăcăminte / Încălțăminte / Accesorii.
   * Toată lista de subcategorii din plan (Rochii, Blugi, Genți & rucsacuri, Bijuterii etc.).
   * Pentru fiecare subcategorie:

     * `size_group`,
     * `measurement_profile`,
     * `is_non_returnable` pentru Costume de baie / lenjerie,
     * `avg_weight_kg`, `co2_avoided_kg`, `trees_equivalent`.
       ➜ Încă ai nevoie de: **fixtures sau management command** care să bage acest master data în DB.

2. **Materiale populate**

   * Lista completă din plan (bumbac, bumbac organic, lyocell, poliester reciclat, piele ecologică etc.).
   * Setarea corectă a `category_type` și `is_sustainable` pentru fiecare.
     ➜ Lipsesc tot ca **seed/master data**.

3. **Branduri populate**

   * Max Mara Group, Ralph Lauren, COS, Gant, Tommy Hilfiger, Guess, Gas, Pablo, Fast fashion, Altele.
   * `group` setat corect, `is_fast_fashion=True` pentru FAST_FASHION, `is_visible_public=True`.
     ➜ Tot aici: fixtures / script.

4. **Tag-uri de sustenabilitate populate (`SustainabilityTag`)**

   * DEADSTOCK, PRELOVED, VINTAGE, UPCYCLED, SUSTAINABLE_MATERIALS (+ eventual cheia pentru „Nici una” dacă o ții ca tag).
     ➜ În cod există modelul, dar lipsesc instanțele în DB.

---

## 2. Materiale & sustenabilitate pe produs

Din cod:

* `Product.material` (FK) există.
* `ProductMaterial` există (importat), cu `compositions` ca related_name.
* `Product.sustainability_tags` + `sustainability_none` există și sunt folosite în wizard + listare.

Ce lipsește încă:

1. **UI pentru compoziția de materiale (ProductMaterial)**

   * În wizard (Pasul mărime/detalii sau un pas separat) nu se lucrează deloc cu `ProductMaterial` (nu apare în `views_wizard`).
   * Nu există încă un loc unde vânzătorul să poată seta: material + procent (ex: 80% bumbac, 20% poliester).
     ➜ Lipsesc formularul/formset + logică în wizard pentru a crea/update `ProductMaterial` pentru produs.

2. **Logica completă „Materiale sustenabile”**

   * Ai `has_sustainable_materials()` pe `Product` și UI pentru `sustainability_tags`, dar:
   * Nu se vede (din fragmentul de cod) o validare clară de tip:

     > dacă este bifat tag-ul „Materiale sustenabile” dar `has_sustainable_materials()` este False → eroare.
     > ➜ De confirmat / de adăugat în `clean()` sau în formular.

3. **UX clar pentru materiale în wizard**

   * Planul cere ca materialele să fie grupate în UI pe CLOTHING / SHOES / ACCESSORIES.
     ➜ Din cod nu reiese că formularul face această grupare (asta e în `forms_wizard`, dar încă nu avem implementarea sigură).

---

## 3. Măsurători și mărimi – reguli business

Modelele sunt aproape full, însă:

1. **Reguli stricte per `measurement_profile`**
   Planul cere, de ex.:

   * TOP: bust, talie, lungime obligatorii; umeri + mânecă opționale.

   * DRESS: bust, talie, șold, lungime obligatorii etc.
     Din cod se vede doar că:

   * `measurement_profile` este transmis ca kwargs în `ProductSizeDetailsForm`.

   * Dar nu avem (aici) logica **obligatoriu/opțional** per profil.
     ➜ De implementat în `ProductSizeDetailsForm.clean()` (sau logic echivalent):

   * pentru TOP, DRESS, JUMPSUIT, PANTS, SKIRT, SHOES, BAGS, BELTS, JEWELRY, ACCESSORY_GENERIC să fie validați exact câmpurile cerute în plan.

2. **Reguli stricte pentru mărimi în funcție de `size_group`**
   Din plan:

   * CLOTHING → `size_alpha` obligatoriu, FR/IT/GB opționale, dar recomandate.
   * SHOES → `shoe_size_eu` obligatoriu (35–46.5).
   * ACCESSORIES → `size_alpha` = „One Size”.
     În cod:
   * Câmpurile există, sunt folosite în wizard și filtre.
   * Nu se vede clar validarea condițională (Fără cod în formular, presupunem că **încă lipsește**).
     ➜ De pus reguli în formular pe baza `category_obj` / `size_group`.

3. **Filtrul generic de dimensiuni (dim_min / dim_max) nu ia în calcul câmpurile noi specifice**

   * În `ProductListView` se filtrează doar pe: `shoulders_cm`, `bust_cm`, `waist_cm`, `hips_cm`, `length_cm`, `sleeve_cm`, `inseam_cm`, `outseam_cm`.
   * Câmpurile noi (`shoe_insole_length_cm`, `bag_width_cm`, `belt_length_total_cm` etc.) nu intră în acest filtru.
     ➜ Dacă vrei un filtru „interval dimensiuni” care să acopere și pantofi/genți/curele, trebuie extins `dim_fields`.

---

## 4. Wizard „Adaugă produs” – ce mai lipsește

Ai deja:

* pași clari,
* integrat numeric sizes,
* integrat sustenabilitate în `size_details`,
* calcul „Tu primești” în preview.

Ce mai lipsește față de plan:

1. **Pas / secțiune clară pentru sustenabilitate**

   * În prezent, `sustainability_tags` + `sustainability_none` vin prin `size_details`.
   * Planul le tratează ca un bloc logic separat („Sustenabilitate”).
     ➜ Ar fi util un **sub-block clar în UI** sau chiar un pas dedicat, cu mesajele de UX („Nici una” debifează restul etc.).
     (Funcțional ai mare parte deja, dar lipsește stratul de UX clar.)

2. **Regula „Nici una” exclusivă – la nivel de formular**

   * În model (`clean`) începi logica, dar ar fi ideal să existe și:

     * dacă bifezi „Nici una” → debifezi automat celelalte tag-uri în form.
       ➜ Comportament JS / form-level (nu e în codul de view).

3. **Minim 4 poze + eticheta de compoziție**

   * Wizard-ul primește `require_min_photos=True`, dar:

     * nu avem confirmarea că `ProductPhotosForm` verifică **min. 4** (nu doar 1).
     * nu există în codul prezent nicio noțiune de „aceasta este poza cu eticheta de compoziție” (flag în `ProductImage`).
       ➜ De făcut:
   * validare clară pentru minim 4 imagini în `ProductPhotosForm`,
   * decidere strategie pentru eticheta de compoziție (câmp `is_composition_label` sau regulă UI).

4. **Setarea `garment_type`**

   * `Product.garment_type` există, dar nu este setat nicăieri în wizard sau altundeva.
     ➜ De făcut mapping subcategorie → garment_type și setat automat în create/edit.

5. **Integrare cu `ProductMaterial` în wizard** (repet din secțiunea 2)

   * De creat pas / subpas pentru compoziții multiple cu procente.

---

## 5. Listare & filtrare (Magazin)

În `ProductListView` suntem destul de departe, dar mai lipsesc:

1. **Filtru „Potrivire cu dimensiunile mele”**

   * Planul cere un filtru gen „Potrivire mai bună cu dimensiunile mele” care folosește dimensiunile salvate în `accounts`.
   * Momentan ai doar `dim_min` / `dim_max` global, fără legătură cu user-ul.
     ➜ Lipsește complet:
   * citirea dimensiunilor din `accounts` pentru userul logat,
   * compararea cu `bust_cm`, `waist_cm`, `hips_cm` etc. cu toleranță ±X cm,
   * param ex. `fit=my`.

2. **Sortare „Cea mai bună potrivire”**

   * Ai sortare după titlu și preț; default „cele mai noi”.
   * Planul include și ceva de tip „Cea mai bună potrivire” (pe baza dimensiunilor).
     ➜ Lipsește sortarea custom bazată pe diferența de cm față de dimensiunile utilizatorului.

3. **Uniformizare filtre de mărime**

   * Momentan coexistă:

     * `size` (legacy),
     * `size_alpha`, `size_fr`, `size_it`, `size_gb`, `shoe_size_eu`.
       ➜ Mai trebuie:
   * decizie clară: ce folosim în UI (filtrele reale pentru users) și cum ne mai bazăm pe `size` doar ca „group” (FR/EU etc.).
   * update în template-uri ca să nu fie confuz pentru useri.

---

## 6. Integrare cu restul planului 1 (strict partea care atinge `catalog`)

Chiar dacă e cross-app, merită notate acum:

1. **Badge „Autentificat” + certificat**

   * `Product.has_authentication_badge` există.
   * Lipsește încă:

     * modelul și logica din app `authenticator`,
     * afișarea badge-ului și a link-ului la certificat în `product_detail.html`.

2. **Respectarea flag-ului `is_non_returnable` în UI**

   * `Subcategory.is_non_returnable` există.
   * Lipsește:

     * afișarea clară în pagina de produs („Acest produs este nereturnabil.”),
     * propagarea regulii în `orders` / `support` (termene și permisiuni de retur).

3. **Pipeline complet de moderare (PENDING → APPROVED → PUBLISHED → SOLD)**

   * Modelul are `moderation_status`.
   * Listezi produsele cu `moderation_status__in=["APPROVED", "PUBLISHED"]`.
   * Wizard-ul setează `APPROVED` by default.
     ➜ Lipsește:
   * fluxul complet, unde:

     * vânzătorul creează → `PENDING`,
     * shop manager aprobă → `APPROVED/PUBLISHED`,
     * ulterior produsul se marchează `SOLD` după comandă.
   * eventual rafinarea filtrului din `ProductListView` la doar `PUBLISHED` după ce avem dashboard de moderare.

---

## 7. Diverse detalii de verificat / fine-tuning

Nu sunt neapărat „buguri”, dar de pus pe radar:

1. **SKU & slug generate automat**

   * `sku` și utilitare `_clean_code`, `get_seller_code` există.
   * Trebuie verificat (mai jos în model) că avem `save()` sau alt mecanism care setează efectiv SKU/slug după planul de generare (categorie, subcategorie, mărime etc.).

2. **Impact CO₂ și copaci în cardurile de produs**

   * În `ProductDetailView` calculezi și trimiți în context `avg_weight_kg`, `co2_avoided_kg`, `trees_equivalent`.
   * Lipsesc (probabil) afișările în listări / carduri (dacă vrei și acolo, nu doar în detaliu).

---
