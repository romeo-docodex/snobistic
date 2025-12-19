## 1. Aplicația `core`

**Ce face:**

* Gestionează pagina de **Home**.
* Gestionează paginile statice: **Despre**, **Contact**, **FAQ/Help**, eventual Blog (dacă va exista).
* Afișează **meniul principal**: Home, Magazin, Licitații, Favorite, Coș, Cont, Autentificare Produse.
* Gestionează **header** și **footer** pentru tot site-ul.
* Gestionează **formularele de contact** și trimiterea lor pe email.
* Gestionează paginile legale: **Termeni și condiții**, **Politică de confidențialitate (GDPR)**, **Politică de retur**, **Politică cookies**.
* Generează și servește fișierele pentru **SEO tehnic minim**: sitemap și robots.
* Gestionează setările de **SEO de bază**: meta title și meta description dinamice pentru paginile principale și pentru produsele din catalog (în colaborare cu aplicația `catalog`).

---

## 2. Aplicația `accounts`

**Ce face:**

* Gestionează **crearea conturilor** de utilizator (buyer, seller sau ambele).
* Gestionează **autentificarea** cu email și parolă.
* Gestionează **social login** (Google, Facebook, Apple ID) la înregistrare și login.
* Gestionează **recuperarea și resetarea parolei**.
* Gestionează activarea și dezactivarea **autentificării cu doi factori** (2FA).
* Stochează și afișează **profilul utilizatorului**:

  * nume, prenume, email, telefon, data nașterii.
  * tip de persoană: fizică / juridică.
  * pentru persoană juridică: date firmă (CUI, TVA, adresă, IBAN etc.).
* Gestionează **adresele** utilizatorului:

  * adresă de livrare,
  * adresă de facturare,
  * setarea adresei implicite.
* Gestionează **setările de vânzător**:

  * date pentru plăți (IBAN și alte detalii necesare),
  * informații legate de locații de marfă / depozit.
* Gestionează statusul de **KYC**:

  * inițiere, documente încărcate, aprobare / respingere, dată aprobare.
* Stochează **dimensiunile personale** ale cumpărătorului (umeri, bust, talie, șold etc.), folosite la filtrarea produselor.
* Gestionează **scorul de seriozitate** pentru cumpărător și vânzător:

  * scor numeric,
  * încadrarea în clase A/B/C/D.
* Gestionează **nivelul vânzătorului** (Amator / Rising / Top / VIP) și comisionul asociat.
* Gestionează **programul de recomandări (referral)**:

  * cod de recomandare al fiecărui utilizator,
  * legătura dintre „invitat” și „cel care a invitat”.
* Gestionează **rolurile avansate**: Shop Manager și Admin (prin permisiuni/grupuri), pe lângă buyer/seller.
* Gestionează legătura cu **sistemul de scor**: primește evenimente de la comenzi, logistică și suport și actualizează scorul de seriozitate.

---

## 3. Aplicația `catalog`

**Ce face:**

* Gestionează **magazinul de produse**.
* Gestionează **categorii și subcategorii** de produse (blugi, rochii, pantofi etc.).
* Gestionează **tipul articolului** (bluză, tricou, sacou etc.).
* Gestionează **brandurile**:

  * lista de branduri disponibile,
  * posibilitatea ca utilizatorul să aleagă „Altele” și să propună un brand nou,
  * marcarea brandurilor noi care trebuie aprobate.
* Gestionează **mărimile**:

  * mărimi standard (XS–3XL),
  * mărimi numerice (EU, FR, IT, GB),
  * opțiunea „Altele” pentru mărimi care nu există în listă.
* Gestionează **atributele produsului**:

  * condiție: Nou cu etichetă, Nou fără etichetă, Stare foarte bună, Stare bună,
  * dimensiuni (umeri, bust, talie, șold, etc.),
  * materiale (bumbac, in, poliester etc.).
* Gestionează **crearea și editarea produselor** de către vânzători, prin wizard în pași:

  * detalii de bază și poze,
  * mărime,
  * dimensiuni,
  * materiale și detalii,
  * descriere,
  * preț („Preț vânzare” și calcul automat „Tu primești”).
* Gestionează **statusul de validare** al produselor:

  * în așteptare, aprobat, respins, publicat, vândut.
* Gestionează **SKU-ul produselor**:

  * generarea automată a codului intern pe baza locației, subcategoriei, titlului, datei și mărimii.
* Gestionează legătura dintre produs și **certificatul de autenticitate** (primit din aplicația `authenticator`).
* Gestionează **pagina de listare produse** (Magazin) cu:

  * filtrare după subcategorie, brand, condiție, mărime, materiale,
  * filtrare după diferența de dimensiuni față de dimensiunile personale ale cumpărătorului,
  * căutare după titlu, brand, categorie și atribute.
* Gestionează **pagina de detaliu produs**.
* Gestionează **Favorite**:

  * salvarea și listarea produselor favorite ale fiecărui utilizator.

---

## 4. Aplicația `cart`

**Ce face:**

* Gestionează **coșul de cumpărături** pentru fiecare utilizator sau vizitator.
* Poate include atât produse din **Magazin**, cât și produse câștigate la **licitații** care trebuie plătite.
* Permite **adăugarea de produse** în coș (doar pentru utilizatori cu drept de cumpărător).
* Permite **eliminarea de produse** din coș.
* Permite **actualizarea cantității** (unde e cazul; la fashion de obicei 1).
* Calculează **sumarul coșului**:

  * total produse,
  * buyer protection fee (taxa de protecție cumpărător),
  * valoare estimată a transportului.
* Afișează **pagina de coș complet**.
* Afișează un coș mini / **offcanvas** în header, cu total și număr de articole.

---

## 5. Aplicația `orders`

**Ce face:**

* Gestionează **crearea comenzilor** la finalizarea checkout-ului (din coș sau din licitații câștigate).
* Stochează toate detaliile unei **comenzi**:

  * cine cumpără,
  * de la ce vânzător cumpără,
  * ce produse sunt comandate,
  * prețuri, comisioane, taxe și transport,
  * adresa de livrare și adresa de facturare folosite.
* Gestionează **statusurile comenzii**:

  * creată, plătită, în curs de expediere, livrată, finalizată, anulată.
* Gestionează **legătura cu plata** (status de plată în așteptare / reușită / eșuată).
* Gestionează **legătura cu livrarea** (în așteptare, trimis, livrat, retur).
* Permite cumpărătorului să vadă **lista comenzilor sale** și detaliile fiecărei comenzi.
* Permite vânzătorului să vadă **lista comenzilor primite** și detaliile fiecărei comenzi vândute.
* Gestionează **cererile de retur** la nivel de comandă sau produs:

  * motivul returului,
  * poze încărcate,
  * statusul returului: deschis, aprobat, respins, rambursat.
* Respectă regulile de **termen de retur** pentru PF și PJ, pentru Magazin și Licitații.

---

## 6. Aplicația `auctions`

**Ce face:**

* Gestionează **licitațiile** create de vânzători.
* Permite transformarea unui produs în **produs de licitație**.
* Stochează informațiile principale ale unei licitații:

  * produsul licitat,
  * preț de pornire,
  * preț minim de vânzare,
  * preț curent,
  * data și ora de început și de sfârșit,
  * statusul licitației: în așteptare, activă, încheiată, anulată.
* Gestionează **ofertele (bid-urile)** ale cumpărătorilor:

  * valoarea ofertei,
  * cine a licitat,
  * momentul licitării.
* Aplică regulile de **increment minim** al ofertei (de ex. +10%).
* La finalul licitației:

  * stabilește **câștigătorul** (dacă a fost atins prețul minim),
  * creează o **comandă** pentru câștigător,
  * definește termenul în care câștigătorul trebuie să plătească.
* Gestionează regulile speciale de **retur pentru licitații**:

  * în principiu 3 zile,
  * acceptat doar pentru produse neconforme cu descrierea.

---

## 7. Aplicația `authenticator`

**Ce face:**

* Gestionează **pagina „Autentificare Produse”** unde utilizatorul poate:

  * încărca poze cu produsul,
  * introduce detalii (brand, model etc.),
  * lăsa un email dacă nu are cont.
* Trimite cererea de autentificare către **platforma externă** de verificare a autenticității (prin API).
* Primește și salvează **rezultatul autentificării**:

  * verdict (autentic / nu),
  * certificat digital sau link extern.
* Leagă rezultatul de un produs din **catalog** atunci când cererea se referă la un produs Snobistic.
* Permite afișarea în pagina de produs a:

  * unui **badge „Autentificat”**,
  * link-ului sau documentului cu **certificatul de autenticitate**.

---

## 8. Aplicația `messaging`

**Ce face:**

* Gestionează **conversațiile** dintre cumpărător și vânzător:

  * o conversație separată pentru fiecare comandă.
* Gestionează **conversațiile cu suportul**:

  * utilizator ↔ echipa Snobistic.
* Permite trimiterea de:

  * mesaje text,
  * fișiere/poze (de exemplu poze cu produsul, cu defectul, cu coletul).
* Afișează **lista de conversații** pentru fiecare utilizator (inbox).
* Afișează **firul de mesaje** dintr-o conversație.
* Marchează **mesajele citite / necitite**.
* Poate fi folosită pentru a implica **admin / shop manager** într-o discuție, la nevoie (de exemplu în caz de dispute).
* Poate afișa în **chat-ul cu suportul** informații despre **poziția utilizatorului în lista de așteptare (queue)**.

---

## 9. Aplicația `dashboard`

**Ce face:**

* Oferă **interfața de tip „cont”** pentru fiecare tip de utilizator.
* Pentru **cumpărător**:

  * afișează „Comenzile mele” (listă + detalii),
  * afișează „Favoritele mele”,
  * afișează „Dimensiunile mele” și permite modificarea lor,
  * afișează acces la facturi și documente disponibile.
* Pentru **vânzător**:

  * afișează „Articole Magazin” (produse postate, status, preț, SKU),
  * afișează „Articole Licitație” (licitații create și statusul lor),
  * afișează „Articole Vândute” (comenzi finalizate),
  * afișează „Istoric Articole” și permite repostarea produselor,
  * afișează secțiunea „Wallet” (sold și tranzacții),
  * afișează setările de cont și de vânzător.
* Pentru **shop manager**:

  * afișează lista de produse în **validare** (de la vânzători),
  * permite aprobarea sau respingerea produselor,
  * afișează istoricul de validări.
* Pentru **admin**:

  * afișează rapoarte: comisioane, vânzări, retururi, scoruri,
  * afișează și permite modificarea **setărilor globale**:

    * comisioane,
    * buyer protection fee,
    * termene de retur,
    * termene de generare AWB,
    * limite pentru licitații,
    * parametri de calcul pentru scorul de seriozitate.

---

## 10. Aplicația `payments`

**Ce face:**

* Gestionează **plățile online** pentru comenzi:

  * inițierea plății (de ex. către procesator card),
  * primirea rezultatului plății (reușită, eșec, anulare).
* Leagă **comanda** de tranzacțiile de plată efectuate.
* Calculează și gestionează **taxa de Buyer Protection**.
* Aplică **comisionul de platformă** pentru vânzători, pe baza nivelului definit în `accounts` (Amator / Rising / Top / VIP) și calculează suma **„Tu primești”** (net pentru vânzător).
* Gestionează partea tehnică de **escrow**:

  * reținerea banilor plătiți de cumpărător,
  * marcarea banilor ca „în escrow” până la confirmarea comenzii sau expirarea termenului de retur,
  * eliberarea banilor către vânzător,
  * inițierea de rambursări dacă este nevoie.
* La eliberarea escrow-ului, trimite sumele corespunzătoare către **Wallet-ul vânzătorului**.
* Gestionează **plata la ramburs**, care este mereu disponibilă ca opțiune de plată:

  * platforma se ocupă de **încasarea banilor de la curier**,
  * platforma se ocupă de **decontarea sumelor către Wallet-ul vânzătorului**,
  * verifică dacă există **limite de valoare sau reguli speciale** (de exemplu pe baza scorului de seriozitate),
  * ia în calcul eventuale **taxe suplimentare pentru ramburs** (comision ramburs, costuri curier etc.).

---

## 11. Aplicația `support`

**Ce face:**

* Gestionează **tichetele de suport** deschise de utilizatori:

  * pentru retururi,
  * pentru produse neconforme,
  * pentru probleme de plată sau livrare,
  * pentru alte întrebări.
* Leagă tichetele de:

  * un anumit utilizator,
  * o anumită comandă sau licitație (dacă e cazul).
* Stabilește și urmărește **statusul fiecărui tichet**:

  * nou, în lucru, rezolvat, respins.
* Gestionează **coada tichetelelor** și poziția utilizatorului în listă (queue), astfel încât acesta să vadă cât de departe este de un operator.
* Permite echipei Snobistic să comunice cu utilizatorul în cadrul tichetului, eventual și cu vânzătorul.
* Se integrează cu **messaging** pentru partea de conversație efectivă (dacă alegi varianta asta).

---

## 12. Aplicația `invoices`

**Ce face:**

* Gestionează toate **documentele fiscale** care țin de platformă:

  * facturi de comision emise de Snobistic către vânzători,
  * facturi de transport și buyer protection emise de Snobistic către cumpărători,
  * eventual facturi de produs emise automat pentru vânzători PJ (dacă se integrează un sistem extern),
  * facturi storno pentru retururi.
* Stochează informațiile fiecărei facturi:

  * număr, serie, dată, sumă, TVA, tip factură.
* Stochează sau generează **fișierul PDF** al facturii.
* Permite **descărcarea facturilor** de către:

  * cumpărător (din contul lui),
  * vânzător (facturile de comision),
  * admin (dintr-un panou de administrare intern).

---

## 13. Aplicația `logistics`

**Ce face:**

* Gestionează **curierii** folosiți pe platformă:

  * nume, tip serviciu (standard, express, ramburs),
  * tarife.
* Gestionează **tarifele de livrare**:

  * în funcție de curier, zonă, greutate sau altă regulă aleasă.
* Gestionează **AWB-urile**:

  * permite vânzătorului să genereze sau să introducă AWB,
  * salvează numărul de AWB pentru fiecare comandă,
  * asociază pozele obligatorii (conținut colet și colet ambalat).
* Gestionează **statusul livrării**:

  * creat, în tranzit, livrat, returnat.
* Afișează în panoul vânzătorului:

  * lista de **Colete Netrimise** (comenzi plătite, dar fără AWB),
  * lista de **Colete Trimise** (comenzi cu AWB și status de livrare).
* Permite cumpărătorului să vadă **tracking-ul coletelelor** (statusul AWB-ului).
* Respectă regula de **3 zile pentru generarea AWB**:

  * dacă termenul este depășit, trimite informație mai departe pentru scăderea scorului de seriozitate și eventual anularea comenzii.

---

## 14. Aplicația `wallet`

**Ce face:**

* Gestionează **portofelul intern** al fiecărui utilizator:

  * soldul disponibil în RON.
* Înregistrează toate **tranzacțiile legate de wallet**:

  * sume încasate din vânzări (după eliberarea escrow),
  * bonusuri din referral,
  * sume primite în urma retururilor,
  * retrageri de bani către contul bancar al utilizatorului,
  * încărcări manuale (dacă va exista opțiunea),
  * taxe și comisioane reținute.
* Primește automat **bonusurile de referral** (1% din sumele cheltuite de utilizatorii invitați, după finalizarea tranzacțiilor fără retur).
* Actualizează **soldul** la fiecare tranzacție.
* Permite utilizatorului:

  * să vadă **soldul curent**,
  * să vadă **istoricul tranzacțiilor** (filtrat pe perioade),
  * să inițieze o **cerere de retragere** de bani în contul bancar.
* Respectă regula de **sumă minimă de retragere** (de ex. minim 1 RON, configurabil).
* Poate permite **plata cu wallet-ul** la checkout, dacă există sold suficient.
* Se integrează cu:

  * `payments` (pentru eliberarea banilor din escrow),
  * `orders` și `support` (pentru refund-uri),
  * `accounts` (pentru bonusuri referral).

---