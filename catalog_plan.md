Perfect, hai să-l fixăm ca document de referință doar pentru **`catalog`** – la nivel de produs, modele, filtre și wizard.

Îl poți da direct clientului (fără partea tehnică dintre paranteze, dacă vrei) și pentru noi devine checklist clar pentru implementare.

---

## 3. Aplicația `catalog` – plan complet

### 3.1. Rol general

Aplicația `catalog` gestionează tot ce ține de:

* structura de **categorii și subcategorii** (îmbrăcăminte, încălțăminte, accesorii),
* **branduri**,
* **mărimi** (literale și numerice),
* **culori**,
* **dimensiuni în cm** în funcție de tipul produsului,
* **materiale** și **sustenabilitate**,
* **greutate / CO₂ evitat / copaci echivalenți**,
* **produse** (creare, editare, statusuri, imagini),
* **listarea și filtrarea produselor** în Magazin,
* **Favorite** (wishlist).

---

## 3.2. Taxonomie: categorii, subcategorii, profile

### 3.2.1. Categorii principale

Catalogul are **3 categorii principale fixe**:

1. **Îmbrăcăminte**
2. **Încălțăminte**
3. **Accesorii**

Acestea sunt înregistrări fixe (seed) în modelul `Category`.

### 3.2.2. Subcategorii

Fiecare subcategorie aparține unei categorii și are:

* nume afișat (ex: „Rochii”, „Blugi”, „Genți & rucsacuri”),
* slug,
* categoria părinte,
* tip mărime (îmbrăcăminte / încălțăminte / accesorii),
* profil de dimensiuni (ce câmpuri sunt obligatorii),
* greutate medie / CO₂ / copaci echivalenți.

Lista de subcategorii (fixă, seed):

**A. Îmbrăcăminte**

* Rochii
* Salopete
* Fuste
* Pantaloni
* Blugi
* Leggings / colanți
* Tricouri / Topuri
* Bluze
* Cămăși
* Pulovere
* Cardigane
* Hanorace
* Sacouri / Blazere
* Veste
* Geci / Jachete
* Paltoane
* Costume de baie / lenjerie intimă (marcate ca **nereturnabile** – info utilă pentru orders/return rules)

**B. Încălțăminte**

* Pantofi sport / sneakers
* Pantofi cu toc
* Pantofi fără toc / loafers / balerini
* Sandale
* Ghete / botine
* Cizme

**C. Accesorii**

* Genți & rucsacuri
* Curele
* Portofele
* Mănuși
* Căciuli / pălării / bentițe
* Eșarfe / fulare / șaluri
* Bijuterii (TOT ce înseamnă cercei, brățări, coliere, inele, broșe etc. – o singură categorie)
* Ochelari de soare / vedere
* Accesorii de păr
* Alte accesorii

### 3.2.3. Tip mărime & profil de dimensiuni (per subcategorie)

Fiecare `Subcategory` are:

* `size_group`:

  * **CLOTHING** – pentru îmbrăcăminte,
  * **SHOES** – pentru încălțăminte,
  * **ACCESSORIES** – pentru accesorii.

* `measurement_profile` (pentru validarea dimensiunilor):

  * TOP (tricouri, topuri, bluze, cămăși, pulovere, cardigane, sacouri, hanorace, veste, jachete, paltoane, costume de baie/lenjerie),
  * DRESS (rochii),
  * JUMPSUIT (salopete),
  * PANTS (pantaloni, blugi, leggings),
  * SKIRT (fuste),
  * SHOES (toată încălțămintea),
  * BAGS (genți & rucsacuri),
  * BELTS (curele),
  * JEWELRY (bijuterii),
  * ACCESSORY_GENERIC (portofele, mănuși, căciuli, eșarfe, ochelari, accesorii de păr, alte accesorii).

Acest profil dictează **ce dimensiuni sunt obligatorii / opționale** în formularul de produs.

### 3.2.4. Greutate medie și CO₂ evitat (per subcategorie)

Fiecare `Subcategory` are câmpuri:

* `avg_weight_kg` – greutate medie articol (din tabelul clientului),
* `co2_avoided_kg` – CO₂ evitat / articol,
* `trees_equivalent` – copaci echivalenți / articol.

Se pre-populează din tabelele clientului. Exemplu:

* Rochii: 0,35 kg, 8,75 kg CO₂, 0,44 copaci
* Blugi: 0,60 kg, 15,00 kg CO₂, 0,75 copaci
  … etc. pentru toate subcategoriile.

În pagina de produs poți afișa:

> „Prin achiziția acestui articol ai evitat ~X kg CO₂ (echivalent cu Y copaci pe an).”

---

## 3.3. Branduri

### 3.3.1. Structură branduri

`Brand` este entitatea care conține:

* `name` – ex: „Max Mara Group”, „Ralph Lauren”, „Fast fashion” etc.
* `group` – enumerare internă:

  * MAX_MARA_GROUP
  * RALPH_LAUREN
  * COS
  * GANT
  * TOMMY_HILFIGER
  * GUESS
  * GAS
  * PABLO
  * FAST_FASHION
  * OTHER
* `is_fast_fashion` (bool) – pentru brandurile de tip „fast fashion”.

Lista fixă cerută de client:

* Max Mara Group
* Ralph Lauren
* COS
* Gant
* Tommy Hilfiger
* Guess
* Gas
* Pablo
* Fast fashion (grup care include Zara, H&M, Mango, Bershka, Pull&Bear, Stradivarius, Primark etc.)
* „Altele” (în UI la adăugare produs, plus câmp text)

### 3.3.2. Reguli de UX/filtrare

* La **adăugare produs**:

  * userul alege un brand din listă,
  * sau alege „Fast fashion” (cu sub-explicare opțională: Zara, H&M etc),
  * sau alege „Altele” + completează brand în câmp text (`brand_other` pe Product – doar la add/edit, nu în filtre).

* La **filtre**:

  * se afișează doar brandurile/grupurile din listă (inclusiv „Fast fashion”),
  * „Altele” NU apare ca filtru (intern voi veți decide unde mappați brandurile noi).

---

## 3.4. Mărimi

### 3.4.1. Mărimi pentru îmbrăcăminte

Reguli:

* **Obligatoriu**:

  * o **mărime literală**: `XXS, XS, S, M, L, XL, 2XL, 3XL`
* **Opțional**:

  * mărimi numerice:

    * `FR`: 28–58 (din 2 în 2: 28, 30, 32, …, 58),
    * `IT`: 32–66,
    * `GB`: 2–30.

Dacă userul a ales doar mărimi numerice (FR/IT/GB) și a lăsat goală mărimea literală, UI arată un infobox:

> „Te rog să estimezi mărimea literară (XXS–3XL) pentru a-i fi mai ușor cumpărătorului.”

### 3.4.2. Mărimi pentru încălțăminte

* numeric **EU**: 35–46.5 în pași de 0.5:

  * 35, 35.5, 36, 36.5, …, 46.5.

### 3.4.3. Mărimi pentru accesorii

* `One Size`.

### 3.4.4. Structură pe `Product`

Pe `Product` există câmpuri dedicate:

* `size_alpha` – mărime principală:

  * pentru îmbrăcăminte: **obligatoriu** (XXS–3XL),
  * pentru accesorii: „One Size”,
* `size_fr` – numeric FR (opțional),
* `size_it` – numeric IT (opțional),
* `size_gb` – numeric GB (opțional),
* `shoe_size_eu` – numeric EU (opțional, folosit doar la încălțăminte).

Validările țin cont de `Subcategory.size_group`:

* CLOTHING → `size_alpha` obligatoriu; FR/IT/GB opționale.
* SHOES → `shoe_size_eu` obligatoriu.
* ACCESSORIES → `size_alpha = One Size`.

---

## 3.5. Culori

### 3.5.1. Color master data

`Color` (paletă fixă):

* `name` – ex: Alb, Negru, Roșu, Verde, Albastru, Galben, Maro, Bej, Mov, Roz, Portocaliu, Gri, Argintiu, Auriu etc.
* `slug`
* `hex_code` – pentru afișare (swatch-uri).

### 3.5.2. Culorile pe produs

Pe `Product`:

* `base_color` – FK către `Color` – **obligatoriu**,
* `real_color_name` – text liber (default = `base_color.name`, dar userul îl poate schimba; ex: Burgundy, Dusty Pink, Sage, Midnight Blue etc.).

Reguli:

* În **filtre**:

  * se folosește doar `base_color`.
* În **search**:

  * dacă userul caută „Burgundy”, se caută și în `real_color_name`.

---

## 3.6. Dimensiuni (măsurători)

### 3.6.1. Câmpuri de dimensiuni pe `Product`

Setul de câmpuri (în cm):

Top / Rochii / Pantaloni etc. (haine):

* `bust_cm` – Bust
* `waist_cm` – Talie
* `hips_cm` – Șold
* `length_cm` – Lungime totală
* `shoulders_cm` – Umeri
* `sleeve_cm` – Lungime mânecă
* `inseam_cm` – Crac interior
* `outseam_cm` – Lungime totală din talie (crac exterior)
* `thigh_cm` – Lățime coapsă (opțional)
* `hem_width_cm` – Lățime la tiv (opțional)

Încălțăminte:

* `shoe_insole_length_cm` – Lungime branț / interior (obligatoriu)
* `shoe_width_cm` – Lățime talpă (opțional)
* `shoe_heel_height_cm` – Înălțime toc (opțional)
* `shoe_total_height_cm` – Înălțime totală (cizme, ghete) (opțional)

Genți:

* `bag_width_cm` – Lățime (obligatoriu)
* `bag_height_cm` – Înălțime (obligatoriu)
* `bag_depth_cm` – Adâncime (opțional)
* `strap_length_cm` – Lungime barete / lanț (opțional)

Curele:

* `belt_length_total_cm` – Lungime totală (obligatoriu)
* `belt_length_usable_cm` – Lungime utilă (de la cataramă la ultima gaură) (obligatoriu)
* `belt_width_cm` – Lățime (obligatoriu)

Bijuterii / accesorii mici:

* `jewelry_chain_length_cm` – Lungime lanț (opțional)
* `jewelry_drop_length_cm` – Lungime / diametru cercel (opțional)
* `jewelry_pendant_size_cm` – Dimensiune pandantiv (opțional)

(denumirile exacte în DB nu contează, important e să acoperim logica.)

### 3.6.2. Reguli de obligatoriu/opțional (în funcție de `measurement_profile`)

Conform documentului clientului:

**3.1. Topuri / bluze / tricouri / cămăși / pulovere / cardigane / sacouri**

* Bust – **OBLIGATORIU**
* Talie – **OBLIGATORIU**
* Lungime totală – **OBLIGATORIU**
* Umeri – OPȚIONAL
* Lungime mânecă – OPȚIONAL

**3.2. Rochii**

* Bust – **OBLIGATORIU**
* Talie – **OBLIGATORIU**
* Șold – **OBLIGATORIU**
* Lungime totală – **OBLIGATORIU**
* Umeri – OPȚIONAL
* Lungime mânecă – OPȚIONAL

**3.3. Salopete**

* Bust – **OBLIGATORIU**
* Talie – **OBLIGATORIU**
* Șold – **OBLIGATORIU**
* Lungime totală – **OBLIGATORIU**
* Crac interior – **OBLIGATORIU**
* Umeri – OPȚIONAL
* Lungime mânecă – OPȚIONAL

**3.4. Pantaloni / blugi / leggings**

* Talie – **OBLIGATORIU**
* Șold – **OBLIGATORIU**
* Crac interior – **OBLIGATORIU**
* Lungime totală (din talie până jos) – **OBLIGATORIU**
* Lățime coapsă – OPȚIONAL
* Lățime la tiv – OPȚIONAL

**3.5. Fuste**

* Talie – **OBLIGATORIU**
* Șold – **OBLIGATORIU**
* Lungime totală – **OBLIGATORIU**

**3.6. Încălțăminte**

* Lungime branț / lungime interior – **OBLIGATORIU**
* Lățime talpă – OPȚIONAL
* Înălțime toc – OPȚIONAL
* Înălțime totală – OPȚIONAL (la cizme/ghete)

**3.7. Genți**

* Lățime – **OBLIGATORIU**
* Înălțime – **OBLIGATORIU**
* Adâncime – OPȚIONAL
* Lungime barete / lanț – OPȚIONAL

**3.8. Curele**

* Lungime totală – **OBLIGATORIU**
* Lungime utilă – **OBLIGATORIU**
* Lățime – **OBLIGATORIU**

**3.9. Bijuterii / accesorii mici**

* Toate câmpurile OPȚIONALE – doar dacă ajută.

Validarea se face în formular (wizard), ținând cont de `Subcategory.measurement_profile`.

---

## 3.7. Materiale

### 3.7.1. Master data Material

`Material` are:

* `name`
* `category_type`:

  * CLOTHING
  * SHOES
  * ACCESSORIES
  * GENERIC (dacă e comun)
* `is_sustainable` (bool) – pentru logica „Materiale sustenabile”.

Liste fixe conform documentului:

**4.1. Fibre naturale (îmbrăcăminte)**
Bumbac, Bumbac organic, Lână, Cașmir, Mohair, Angora, Mătase, In, Alpaca

**4.2. Fibre artificiale (pe bază de celuloză)**
Vascoză, Modal, Lyocell / Tencel, Cupro

**4.3. Fibre sintetice**
Poliester, Poliester reciclat, Poliamidă / Nylon, Poliamidă reciclată, Acril, Elastan, Polipropilenă, Poliuretan (PU)

**4.4. Materiale pentru încălțăminte & accesorii**

Încălțăminte:
Piele naturală, Piele ecologică / PU, Cauciuc, EVA, Textile, Generic

Accesorii:
Piele naturală, Piele ecologică / PU, Cauciuc, EVA, Textile, Generic, Metal, Oțel inoxidabil, Aliaj, Plastic, Lemn, Sticlă, Cristale, Pietre semiprețioase

### 3.7.2. Materiale pe produs

* `Product.materials` – ManyToMany către `Material`.
* Se pot bifa **mai multe materiale**.
* La UI:

  * se afișează materialele separate pe categorii (îmbrăcăminte / încălțăminte / accesorii),
  * în funcție de `Category` / `Subcategory`.

### 3.7.3. Materiale „sustenabile”

Materiale considerate sustenabile:

* Bumbac organic
* In
* Lyocell / Tencel
* Cupro
* Poliester reciclat
* Poliamidă reciclată
* Piele ecologică / PU

Pentru acestea, `Material.is_sustainable = True`.

---

## 3.8. Sustenabilitate

### 3.8.1. Opțiuni

Există 6 opțiuni de sustenabilitate:

1. Deadstock / stoc nevândut
2. Preloved / second hand
3. Vintage
4. Upcycled / recondiționat
5. Materiale sustenabile
6. Nici una

Le stocăm prin:

* M2M `Product.sustainability_tags` (cu opțiunile 1–5),
* bool `Product.sustainability_none` pentru „Nici una”.

### 3.8.2. Logică „Nici una” vs celelalte

În formular:

* dacă userul bifează „Nici una”:

  * se debifează automat toate celelalte 5,
  * celelalte 5 devin disabled.
* dacă userul bifează una dintre cele 5:

  * „Nici una” se debifează automat,
  * „Nici una” devine disabled.

### 3.8.3. „Materiale sustenabile”

* Checkbox-ul „Materiale sustenabile” este **vizibil** doar dacă produsul are cel puțin un material cu `is_sustainable=True`.
* Validare backend:

  * dacă userul bifează „Materiale sustenabile” dar produsul **nu conține** materiale sustenabile → eroare:

> „Produsul nu conține materiale sustenabile conform listei Snobistic.”

---

## 3.9. Produse & imagini

### 3.9.1. Product – câmpuri principale

Pe lângă cele de mai sus, `Product` gestionează:

* `owner` (FK la user),
* `title`,
* `description`,
* `category`, `subcategory`,
* `brand`, `brand_other`,
* `condition`,
* mărimi (size_alpha, size_fr, size_it, size_gb, shoe_size_eu, One Size),
* culori (base_color, real_color_name),
* dimensiuni cm (setul de câmpuri de la 3.6),
* materiale (M2M),
* sustenabilitate (M2M + boolean),
* CO₂ / copaci (derive sau copiem valorile din `Subcategory` la afișare),
* `price`,
* `package_size` + `package_l_cm`, `package_w_cm`, `package_h_cm`,
* `sale_type` (FIXED sau AUCTION – integrat cu `auctions`),
* `is_active`,
* `moderation_status` (PENDING, APPROVED, REJECTED etc.),
* `main_image` (imagine principală).

### 3.9.2. Imagini produs

`ProductImage`:

* FK `product`,
* `image`,
* `position` (pentru ordonare).

Reguli:

* minim **4 fotografii**:

  * front,
  * spate,
  * detalii,
  * **eticheta de compoziție** (obligatorie).
* wizard-ul de poze:

  * validează minim 4,
  * poate avea hint-uri vizuale/text: ghid de pozare.

---

## 3.10. Favorite (Wishlist)

`Favorite` sau similar (poate fi chiar model separat sau coș în DB):

* legătură între `user` și `product`,
* opțional: dată adăugare,
* UI:

  * pagină cu toate produsele favorite,
  * buton togglabil „♡ Salvează în favorite” în pagina de produs,
  * integrat în `dashboard` (cumpărător).

---

## 3.11. Listarea & filtrarea produselor (Magazin)

### 3.11.1. Filtre disponibile

În pagina de **Magazin**:

* Categorii / subcategorii:

  * Îmbrăcăminte / Încălțăminte / Accesorii,
  * subcategoriile aferente.
* Brand:

  * Max Mara Group, Ralph Lauren, COS, Gant, Tommy Hilfiger, Guess, Gas, Pablo, Fast fashion, … (fără „Altele” text).
* Condiție:

  * Nou cu etichetă, Nou fără etichetă, Stare foarte bună, Stare bună.
* Mărimi:

  * dacă filtrul este pe îmbrăcăminte:

    * mărimi literale (XXS–3XL),
    * mărimi numerice FR, IT, GB:

      * ex: „FR 28–58” → când dai click, poți selecta oricare din interval (28,30,32…).
  * dacă filtrul este pe încălțăminte:

    * EU 35–46.5 (lista completă din 0.5 în 0.5).
  * accesorii:

    * One Size.
* Culori:

  * doar `base_color`.
* Materiale:

  * lista fixă, eventual grupată (fibre naturale / artificiale / sintetice etc.).
* Sustenabilitate:

  * Deadstock, Preloved, Vintage, Upcycled, Materiale sustenabile.
* Preț:

  * interval (slider sau 2 input-uri).
* Dimensiuni vs dimensiuni utilizator:

  * filtru „Potrivire mai bună cu dimensiunile mele”, care:

    * compară `bust_cm, waist_cm, hips_cm, length_cm` etc. față de dimensiunile salvate în `accounts`,
    * permite filtre de genul:

      * „±2 cm față de talia mea”,
      * „±3 cm la bust”.

### 3.11.2. Sortare

* default: Relevanță sau cele mai noi,
* alte opțiuni:

  * Preț crescător / descrescător,
  * Cea mai bună potrivire (în funcție de mărime/dimensiuni),
  * Cele mai recente.

---

## 3.12. Wizard „Adaugă produs” (vânzător)

Flow-ul final (logic):

1. **Categorie & subcategorie**

   * alege categoria (Îmbrăcăminte / Încălțăminte / Accesorii),
   * alege subcategoria (Rochii, Blugi, Genți etc.),
   * intern se setează `size_group` + `measurement_profile`.

2. **Brand & stare produs**

   * brand (lista fixă + „Fast fashion” + „Altele + text”),
   * stare produs (Nou cu etichetă, Nou fără etichetă, Stare foarte bună, Stare bună).

3. **Titlu & descriere**

   * titlu produs,
   * descriere (material, croi, defecte, cum se simte, etc.).

4. **Mărimi**

   * dacă îmbrăcăminte:

     * mărime literă (XXS–3XL) – obligatoriu,
     * FR/IT/GB – opțional,
     * dacă userul nu pune literă → mesaj „te rog să estimezi mărimea literară”.
   * dacă încălțăminte:

     * EU 35–46.5.
   * dacă accesorii:

     * One Size.

5. **Culoare**

   * culoare de bază (select din lista fixă),
   * culoare reală (text, pre-populat cu culoarea de bază, userul poate modifica: Burgundy etc.).

6. **Dimensiuni**

   * câmpurile se afișează în funcție de `measurement_profile` (ex: Rochie → bust, talie, șold, lungime, etc.),
   * validare strictă a câmpurilor obligatorii vs opționale.

7. **Materiale**

   * checkboxes cu materialele din listele fixe,
   * filtrate în funcție de categoria/subcategoria produsului.

8. **Sustenabilitate**

   * checkbox-uri pentru Deadstock, Preloved, Vintage, Upcycled, Materiale sustenabile, Nici una,
   * logica de mutual exclusiveness pentru „Nici una”,
   * validare „Materiale sustenabile” ↔ materiale efectiv sustenabile pe produs.

9. **Preț & „Tu primești”**

   * introduci prețul de vânzare,
   * se afișează:

     * comision platformă (în funcție de nivel vânzător),
     * „Tu primești” (net pentru vânzător).

10. **Fotografii & ghid de pozare**

    * upload minim 4 poze (inclusiv eticheta de compoziție),
    * UI afișează ghid text+imagine cu „ce trebuie fotografiat” (față, spate, detalii, etichetă etc.),
    * validare minim 4 imagini.

11. **Review final**

    * recapitulare toate informațiile,
    * check „Confirm că informațiile sunt corecte și produsul poate fi listat.”

---