Îți pun totul la un loc, curățat de duplicate și redus la funcționalitățile de bază, inclusiv cu modificările noi de la client (fără New/Outlet/Pre-loved în meniu, condiții pe produs, brand „Altele”, comisioane, retur, scoruri etc.).

---

# SNOBISTIC – FUNCȚIONALITĂȚI DE BAZĂ (VERSIUNE UNIFICATĂ)

## 1. Tipuri de utilizatori & roluri

* **Vizitator** – poate naviga, căuta, vedea produse și licitații.
* **Cumpărător (Buyer)** – poate adăuga în coș, cumpăra, deschide retururi, folosi wallet-ul.
* **Vânzător (Seller)**

  * Private Seller (PF)
  * Professional Seller (PJ / firmă)
* **Shop Manager** – validează anunțuri, gestionează produse și suport vânzători.
* **Admin** – acces complet la setări, rapoarte, comisioane, utilizatori.

> Notă: un user poate fi și buyer, și seller (cont mixt), dar există o setare care permite sau nu cumpărarea când este vânzător.

---

## 2. Autentificare & conturi

### 2.1. Login & înregistrare

* Login cu **email + parolă**.
* **2FA**: prin email / SMS / aplicație.
* **Social login**: Google, Facebook, Apple ID.
* Recuperare / resetare parolă.

### 2.2. Creare cont

Pentru toți utilizatorii:

* Nume, Prenume, Email, Telefon, Data nașterii.
* Adresă de livrare (opțional adresă de facturare diferită).
* Alegere: **Persoană fizică / juridică**.

Pentru **vânzători**:

* Date firmă (CUI, registru, TVA, sediu) pentru PJ.
* IBAN pentru plăți.
* Setări vânzător:

  * Accept / Nu accept **plata la ramburs**.
  * Limită sumă ramburs (maxim).
  * Posibilă livrare locală (ulterior).

### 2.3. Profil, KYC & dimensiuni

* Profil utilizator cu:

  * Avatar, date de contact, adrese.
  * Roluri: buyer / seller.
  * Status KYC: neînceput, în analiză, aprobat, respins.
* Pentru cumpărători:

  * „Dimensiunile mele” salvate (umeri, bust, talie, șold etc.) pentru filtrare produs.

---

## 3. Structură pagini & navigare

### 3.1. Meniu principal (versiunea actualizată)

* **Home**
* **Magazin**
* **Licitații**
* **Favorite**
* **Coș**
* **Cont**
* **Autentificare Produse**

> „New / Outlet / Pre-loved” nu mai sunt secțiuni separate; condiția produsului devine atribut/filtru pe produs.

### 3.2. Pagina Magazin

* Listare produse în **grid**.
* Sidebar / filtre:

  * Subcategorii: Accesorii, Blugi, Bluze, Cămăși, Cardigane, Costume de baie, Fuste, Geci, Genți, Încălțăminte, Paltoane, Pantaloni, Pulovere, Rochii, Sacouri, Salopete, Tricouri / Topuri, Veste.
  * Condiție produs:

    * **NOU CU ETICHETĂ**
    * **NOU FĂRĂ ETICHETĂ**
    * **STARE FOARTE BUNĂ**
    * **STARE BUNĂ**
  * Mărimi (S, M, L, EU, FR, IT etc.).
  * Filtru dimensiuni: slider toleranță (0–10 cm) față de dimensiunile salvate în profil.
* **Searchbar** care caută în:

  * titlu produs,
  * categorii / subcategorii,
  * brand,
  * atribute produs.

---

## 4. Catalog de produse

### 4.1. Atribute produs

Un produs are cel puțin:

* Titlu.
* Categorie, Subcategorie, tip articol (bluza, tricou etc.).
* **Brand**:

  * Alegere din listă de branduri existente.
  * Opțiune **„Altele”** + câmp text pentru brand nou (apoi validat și adăugat de echipă).
* **Condiția** produsului:

  * Nou cu etichetă, Nou fără etichetă, Stare foarte bună, Stare bună.
* Mărime:

  * One Size, XXS–3XL, EU 35–46.5, FR 28–58, GB 2–30, IT 32–66 etc.
  * Opțiune „Altele” + text pentru mărime dacă nu există în listă.
* **Dimensiuni**:

  * Umeri, Bust, Talie, Șold, Lungime, Mâneca, Crac interior, Crac exterior (în funcție de tip).
* Materiale:

  * Bumbac, In, Vascoză, Poliester, Mătase, Poliamidă, Catifea, Satin, Lână, Dantelă, Altele.
* Preț vânzare (minim configurabil, ex. 10 RON).
* Stare produs: În validare / Aprobat / Respins / Publicat / Vândut.

### 4.2. Imagini

* Minim **3 imagini** la fiecare produs.

  * 1 imagine obligatorie cu etichetă (unde e cazul).
* Imagine principală selectabilă.
* Imagine principală cu **fundal eliminat automat** (integrare cu un serviciu extern).

### 4.3. SKU produs

* Format:

  * `[3 litere locație marfă] / [3 litere subcategorie] / [3 litere titlu produs] / [data+ora] / [mărime]`.
* Locația marfă:

  * generată din 3 litere (nume utilizator sau locații definite în contul vânzătorului).
* SKU se generează automat la salvarea produsului.

---

## 5. Autentificare Produse (API extern)

* Pagină separată „Autentificare Produse”:

  * utilizatorul poate încărca poze și detalii despre produs.
  * dacă nu are cont, poate introduce doar email.
* Sistemul trimite datele prin **API** către un serviciu de autentificare extern.
* Se primește și se stochează un **certificat digital de autenticitate**.
* În pagina de produs:

  * badge „Autentificat”.
  * link către certificat / descărcare PDF.

---

## 6. Adăugare produs – Wizard

### 6.1. Produse Magazin (listare normală)

Wizard în 4–6 pași (funcțional de bază):

1. **Detalii de bază**

   * Titlu, categorie, subcategorie / tip articol.
   * Alegere brand sau „Altele” + text.
   * Condiție produs.
   * Upload minim 3 imagini + alegere imagine principală.

2. **Mărime & mărimi alternative**

   * Selectare mărime din liste (sisteme multiple).
   * Opțiune „Altele” pentru mărime liberă.

3. **Dimensiuni**

   * Umeri, Bust, Talie, Șold, Lungime, Mâneca, Crac interior, Crac exterior (după tip).

4. **Materiale & detalii**

   * Selectare materiale.
   * Alte atribute (ex. sezon, culoare).

5. **Descriere**

   * Descriere text liberă.

6. **Preț**

   * „Preț vânzare: X RON” – introdus de vânzător.
   * „Tu primești: Y RON” – calculat automat pe baza comisionului pentru nivelul vânzătorului.

După finalizare:

* Produsul intră în **pending** pentru validare la Shop Manager / Admin.
* Orice modificare ulterioară reîntoarce produsul în „În validare”.

### 6.2. Produse Licitații

* Pașii 1–5 identici.
* Pas suplimentar „Setări licitație”:

  * Preț de pornire.
  * Preț minim de vânzare (reserve price).
  * Durată licitație (într-un interval configurabil, ex. 5–10 zile).

---

## 7. Licitații

Funcționalități de bază:

* Creare licitație pentru un produs (tip „AUCTION”).
* Licitațiile au:

  * Preț de pornire, preț curent, preț minim de vânzare.
  * Data și ora de început și de sfârșit.
* Utilizatorii pot:

  * Plasa bid-uri deasupra unui **increment minim** (ex. +10%).
* La final:

  * Se determină câștigătorul (dacă s-a atins condiția minimă).
  * Câștigătorul primește obligația de plată într-un număr de zile configurabil.
* Retur la licitații:

  * În principiu **3 zile**.
  * Acceptat doar dacă **produsul nu corespunde descrierii** / defecte majore, cu dovezi (poze).

---

## 8. Coș & comenzi

### 8.1. Coș de cumpărături

* Doar utilizatori cu drept de **buyer** (sau seller cu opțiunea „poate cumpăra” activă) pot adăuga în coș.
* Coșul conține:

  * Produse din Magazin.
  * Opțional, produse câștigate la licitații care trebuie plătite.
* Sumar coș:

  * Total produse.
  * **Buyer Protection Fee** – % configurabil aplicat la valoarea produselor.
  * Transport estimativ (în funcție de reguli logistice de bază).

### 8.2. Comenzi

* La checkout se generează:

  * **Comandă** cu buyer, seller, adrese, produse, prețuri, comisioane.
* Documente automate:

  * „Detalii comandă – cumpărător”.
  * „Detalii comandă – vânzător” (include date facturare cumpărător).
* Banii se încasează și intră în **escrow** (vezi secțiunea Plăți & Escrow).

---

## 9. Plăți, Escrow & Comisioane

### 9.1. Metode de plată

* **Card online** (procesator extern – Stripe / altul).
* **Wallet** (sold intern, când există).
* **Plata la ramburs**:

  * disponibilă doar pentru vânzători care acceptă ramburs.
  * restricționată pentru cumpărători cu scor mic.
  * costuri transport ramburs diferite (comunicate).

### 9.2. Escrow

* Suma plătită de cumpărător este reținută în **escrow**.
* Escrow se eliberează către vânzător:

  * la confirmarea de primire de la cumpărător
    **sau**
  * la expirarea perioadei de retur fără reclamație.

### 9.3. Comisioane

* **Comision vânzător** pe nivel:

  * Amator Seller – 9%
  * Rising Seller – 8%
  * Top Seller – 7%
  * VIP (abonament plătit) – 6%
* Comision cumpărător:

  * **Buyer Protection Fee** (ex. 5%, configurabil).
* La plasarea comenzii:

  * sistemul calculează: preț produs + buyer protection + transport.
  * „Tu primești” (net pentru vânzător) = preț produs – comision platformă (în funcție de nivel).

---

## 10. Retururi

### 10.1. Termene de retur

* **Vânzare normală Magazin**:

  * PF (vânzători persoane fizice): 3 zile (configurabil).
  * PJ (vânzători firme): 14 zile (configurabil).
* **Licitații**:

  * 3 zile – doar dacă produsul nu corespunde descrierii.

### 10.2. Proces retur

* Cumpărătorul inițiază retur din cont:

  * selectează motiv din listă + „Alt motiv”.
  * răspunde la întrebarea „De ce returnezi?” (folosită și pentru scor de seriozitate).
  * atașează poze unde e cazul.
* Cumpărătorul plătește transportul de retur:

  * se emite factură separată pentru transport retur (ex. 25 RON).
* După ce vânzătorul primește coletul și îl acceptă:

  * cumpărătorul primește în wallet:

    * valoarea produsului.
    * transport standard inițial.
  * suplimente (Express / Ramburs etc.) nu se restituie.

---

## 11. Wallet & Retrageri

* Fiecare utilizator are **Wallet** în RON.
* Operațiuni de bază:

  * Încasare din vânzări (după ce escrow se eliberează).
  * Bonusuri din referral.
  * Restituiri (retururi, diferențe).
  * Retragere bani în cont bancar.
* **Withdrawal**:

  * minim 1 RON (configurabil).
  * cererile de retragere au status: pending / complet.

---

## 12. Facturare & documente

Funcțional, fără a intra în detalii de API:

* La plasarea comenzii:

  * **Detalii comandă – cumpărător** (Snobistic).
  * **Detalii comandă – vânzător** (cu datele de facturare ale cumpărătorului).
  * Factura Snobistic pentru:

    * Buyer Protection.
    * Transport standard + suplimente (Express / Ramburs).
* Pentru vânzători PJ/PFA/II:

  * emit **factura de produs** către cumpărător (manual sau prin API la sistem de facturare).
* Pentru vânzători PF:

  * se generează **contract de vânzare-cumpărare** tipizat.
* Pentru retur:

  * Snobistic emite factură de transport retur și, după caz, factură storno pentru componentele care se rambursează.

---

## 13. Logistică & AWB

Funcționalități de bază:

* Vânzătorul are **3 zile** (configurabil) să genereze AWB după plasarea comenzii:

  * direct din platformă (integrare API) sau
  * prin upload manual al AWB-ului.
* La generarea AWB:

  * se cere încărcarea a 2 poze:

    * conținut colet.
    * colet ambalat.
* Panou:

  * **Colete Netrimise** – comenzi neexpediate, unde se adaugă AWB + poze.
  * **Colete Trimise** – comenzi expediate, cu AWB și tracking.
* Dacă termenul pentru AWB este depășit:

  * comanda poate fi anulată.
  * scade scorul de seriozitate al vânzătorului.

---

## 14. Scor de seriozitate & badge-uri

### 14.1. Cumpărători

* Fiecare cumpărător are un **scor de seriozitate (0–100)**.
* Factori generali (nu intrăm în formule):

  * cont complet (email/telefon verificate, 2FA).
  * vechime și număr de comenzi finalizate.
  * rata de finalizare comenzi vs. anulări.
  * procent retururi „normale” vs. abuzive.
  * incidente negative: neridicare ramburs, chargeback etc.
  * rating primit de la vânzători.
* Scorul se traduce în **clase de risc** (A–D) și influențează:

  * accesul la ramburs.
  * limite de valoare coș.
  * priorități de suport.

### 14.2. Vânzători

* Fiecare vânzător are **scor de seriozitate (0–100)** și **nivel** (Amator / Rising / Top / VIP).
* Factori generali:

  * KYC și date firmă validate.
  * număr comenzi, volum de vânzări.
  * procent livrări la timp.
  * procent retururi din vina vânzătorului.
  * anulări de comenzi din lipsă stoc.
  * timp de răspuns la mesaje și dispute.
  * rating de la cumpărători.
* Clasa (A–D) și nivelul determină:

  * comisionul aplicat (9/8/7/6%).
  * vizibilitatea listărilor.
  * termenii de plată (în câte zile se eliberează banii din wallet).

---

## 15. Referral Program

Funcționalități de bază:

* Fiecare user are un **Referral Code**.
* Dacă aduce un user nou (buyer sau seller):

  * primește **1% din sumele cheltuite de acel user** (fără transport și TVA),
    după ce tranzacțiile sunt finale (fără retur).
* Recompensa se acordă în **wallet** sub formă de AIRDROP.
* Programul funcționează pe **un singur nivel** (nu MLM).

---

## 16. Dashboard-uri

### 16.1. Panou vânzător

* **Articole Magazin Postate**:

  * listă produse cu status (în validare / validat / publicat), preț, SKU.
  * acțiuni: editare (înainte de validare), ștergere, export CSV.
* **Articole Licitație Postate**:

  * listă licitații cu datele principale.
* **Articole Vândute**:

  * produse vândute, status plată, status trimis, zile retur rămase.
  * generare / vizualizare AWB, poze colet.
  * acces la facturile de comision.
* **Istoric Articole**:

  * produse vechi, cu opțiune „Repostează”.
* **Wallet**:

  * sold, istoric tranzacții, retrageri.
* **Setări cont**:

  * date personale, brand shop, locații marfă, setări ramburs.

### 16.2. Panou cumpărător

* **Comenzile mele**:

  * listă comenzi Magazin + Licitații.
  * status: Plătit / Neplătit, Trimis / Netrimis.
  * AWB + tracking.
  * buton retur (dacă termenul nu a expirat).
* **Favorite**:

  * listă produse salvate.
* **Dimensiunile mele** și date profil.
* **Facturi & documente**:

  * facturi transport, buyer protection, produse (dacă sunt integrate).

### 16.3. Shop Manager & Admin

* Shop Manager:

  * listă anunțuri în validare.
  * aprobare / respingere.
  * comunicare cu vânzătorul (mesaje interne).
* Admin:

  * dashboard comisioane, vânzări, scoruri, retururi.
  * setări globale:

    * comisioane, buyer protection,
    * termene retur,
    * termene AWB,
    * limite licitație,
    * parametri scor seriozitate.

---

## 17. Suport & comunicare

* **Chat cumpărător–vânzător**:

  * se deschide automat la fiecare comandă.
  * vizibil doar pentru cei doi +, la nevoie, pentru suport (admin).
* **Chat cu suport**:

  * utilizatorii pot deschide conversație cu echipa Snobistic.
  * afișare poziție în lista de așteptare (queue).
* **Sistem de tichete**:

  * pentru retururi, dispute, probleme complexe.
  * status ticket: nou, în lucru, rezolvat, respins.

---

## 18. Legal & SEO (nivel minim)

* Pagini statice:

  * Termeni și condiții, GDPR, Politică cookie, Politică retur.
* SEO de bază:

  * meta title & description dinamice pentru pagini și produse.
  * sitemap XML și robots.txt.

---

