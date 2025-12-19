## 1. Autentificare & înregistrare

### `accounts/login.html` (LoginView)

**Scop:** autentificare clară, fără fricțiuni.

Ce trebuie să conțină:

* Titlu: „Autentificare în cont”.
* Form cu:

  * Email
  * Parolă
  * Bifă „Ține-mă minte”
* CTA-uri secundare:

  * Link „Ai uitat parola?” → `accounts:password_reset`
  * Link „Nu ai cont? Creează-ți unul” → `accounts:register`
* Mesaje de eroare clare (email/parolă greșite, cont neactivat).
* Mic mesaj securitate: „Nu împărtăși niciodată codurile sau parola cu altcineva.”

---

### `accounts/register.html` (RegisterView)

**Scop:** crearea contului (buyer/seller).

Ce trebuie să conțină:

* Titlu: „Creează-ți cont pe Snobistic”.
* Form cu:

  * Nume, Prenume
  * Email
  * Parolă + confirmare
  * Telefon
  * Opțiuni:

    * „Vreau doar să cumpăr”
    * „Vreau să vând și să cumpăr” (checkbox / radio)
  * (opțional) „Ai cod de recomandare?” – input referral.
* Accept termeni:

  * Checkbox „Sunt de acord cu Termeni & condiții, Politica de confidențialitate etc.” cu link-uri.
* Info după submit:

  * Text clar: „Ți-am trimis un email pentru activare. Verifică și folderul Spam/Promotions”.

---

### `accounts/registration_email_sent.html`

**Scop:** confirmă trimiterea emailului de activare.

Conținut:

* Mesaj: „Ți-am trimis un email de activare la [email].”
* Instrucțiuni:

  * Verifică spam
  * Link „Resend” → `accounts:resend_activation`
* Eventual îndemn: „După activare te poți autentifica aici → link login”.

---

### `accounts/activation_result.html` (folosit de `activate_account`)

**Scop:** afișează rezultatul activării.

Conținut:

* Pentru succes:

  * Icon/mesaj verde: „Contul tău a fost activat cu succes.”
  * Buton „Autentifică-te” → `accounts:login`
* Pentru erori:

  * Mesaj de tip: „Link de activare expirat / invalid”.
  * Buton „Trimite un nou email de activare” → `accounts:resend_activation`.

---

### `accounts/resend_activation.html`

**Scop:** retrimitere email de activare.

Conținut:

* Form cu:

  * Email
* Mesaj:

  * „Dacă contul tău nu este încă activ, îți vom retrimite linkul.”
* Confirmare după POST (sau pagină separată `resend_activation_done.html`):

  * „Dacă există un cont cu acest email, am trimis un nou link de activare.”

---

## 2. 2FA – flux principal

### `accounts/two_factor.html` (TwoFactorView)

**Scop:** ecranul în care utilizatorul introduce codul 2FA la login.

Conținut:

* Titlu: „Introdu codul de autentificare în doi pași”.
* Form:

  * Input cod 6 cifre (sau 8, în funcție de TOTP).
* Mesaje:

  * „Verifică aplicația ta de autentificare / email / SMS.”
* Opțiuni suplimentare:

  * Link „Folosește un cod de backup” (dacă ai implementat).
  * Checkbox „Marchează acest dispozitiv ca de încredere” (trusted device).
* Eroare clară la cod invalid/expirat.

---

### `accounts/two_factor_setup.html` (two_factor_setup)

**Scop:** configurare 2FA (prima dată).

Conținut:

* Explicații scurte: ce este 2FA, de ce e important.
* Pentru TOTP:

  * QR code pentru aplicații (Google Authenticator, Authy).
* Cheie secretă afișată text pentru backup.
* Pași:

  * „Scanează codul QR”
  * „Introdu codul de 6 cifre din aplicație pentru verificare”
* Buton „Continuă →” către `two_factor_setup_verify`.

---

### `accounts/two_factor_setup_verify.html` (two_factor_setup_verify)

**Scop:** verifică codul introdus la setup.

Conținut:

* Input pentru cod TOTP.
* Eroare clară dacă nu se potrivește.
* După succes:

  * Mesaj: „2FA este activă pentru contul tău.”
  * Generare și afișare coduri backup (sau redirect spre pagină dedicată cu coduri).

---

### `accounts/backup_codes.html` (regenerate_backup_codes)

**Scop:** afișează codurile de backup și confirmă regenerarea lor.

Conținut:

* Listă coduri (obligatoriu user-ul să le salveze).
* Avertisment: „După regenerare, codurile vechi nu mai funcționează.”
* Buton de confirmare „Am salvat codurile”.

---

## 3. Resetare / schimbare parolă

### `accounts/password_reset.html` (CustomPasswordResetView)

* Form cu:

  * Email
* Mesaj: „Îți vom trimite un link de resetare dacă emailul există.”

### `accounts/password_reset_done.html`

* Mesaj: „Dacă emailul este înregistrat, ți-am trimis instrucțiuni.”

### `accounts/password_reset_confirm.html`

* Form cu:

  * Parolă nouă
  * Confirmare parolă
* Validări: minim caractere, complexitate etc.

### `accounts/password_reset_complete.html`

* Mesaj: „Parola a fost resetată cu succes.”
* Buton „Autentifică-te”.

### `accounts/password_change.html` (CustomPasswordChangeView)

* Necesită user logat.
* Form:

  * Parolă veche
  * Parolă nouă + confirmare
* Sfat mic: „Evită parolele pe care le folosești în alte conturi.”

### `accounts/password_change_done.html`

* Confirmare schimbare parolă.
* Recomandare: „Dacă nu tu ai făcut această schimbare, contactează imediat suportul.”

---

## 4. Profil – overview & secțiuni principale

### `accounts/profile.html` (profile)

**Scop:** hub-ul zonei de cont.

Conținut:

* Secțiune „Bun venit, [prenume]”
* Carduri rezumate:

  * Date personale (edit link)
  * Adrese (nr. adrese, link edit)
  * Dimensiuni (status complet/incomplet)
  * Vânzător:

    * Nivel vânzător + comision
    * Trust score
    * KYC status
* Shortcut buttons:

  * „Vezi comenzi” (în `dashboard`)
  * „Vezi articole vândute” (în `dashboard` pentru seller)

---

### `accounts/profile_data.html` (profile_data)

**Scop:** editarea datelor de profil.

Conținut:

* Form mare cu:

  * Nume, prenume
  * Email (poate doar afișat, nu editabil direct)
  * Telefon
  * Data nașterii
  * Tip persoană:

    * PF / PJ
  * Dacă PJ:

    * Nume firmă
    * CUI
    * TVA (plătitor/neplătitor)
    * Adresă firmă
    * IBAN
* Mesaje:

  * „Aceste date vor apărea pe facturile emise în numele tău.”
* Buton „Salvează schimbările”.

---

### `accounts/profile_security.html` (profile_security)

**Scop:** toate setările de securitate la un loc.

Conținut:

* Secțiune 1 – Parolă:

  * Buton „Schimbă parola” → `accounts:password_change`
* Secțiune 2 – 2FA:

  * Badge: 2FA activă/neactivă.
  * Butoane:

    * „Activează 2FA” → `accounts:enable_2fa` sau `two_factor_setup`
    * „Dezactivează 2FA” → `accounts:disable_2fa` (cu confirmare).
    * „Activează 2FA prin Email / SMS” → `enable_2fa_email` / `enable_2fa_sms`.
    * „Generează coduri backup din nou” → `regenerate_backup_codes`.
* Secțiune 3 – Dispozitive de încredere:

  * Listă cu:

    * Device name / browser + locație aproximativă + data adăugării.
    * Buton „Revocă” → `accounts:revoke_trusted_device`.
* Secțiune 4 – Activitate recentă:

  * Ultimele logări (IP, device, dată).
  * Alertă dacă vezi ceva suspect.

---

## 5. Profil – adrese

### `accounts/address_list.html` (address_list)

**Scop:** toate adresele user-ului.

Conținut:

* Listă tip carduri:

  * Etichetă: „Adresa de livrare principală”, „Adresa de facturare”.
  * Nume persoană/contact, adresă completă, telefon.
  * Badge „Implicită”.
* Acțiuni:

  * „Editează”
  * „Șterge”
  * „Setează ca implicită” (dacă ai view separat sau buton cu POST).
* Buton mare „Adaugă adresă nouă” → `address_form`.

---

### `accounts/address_form.html` (address_form add/edit)

**Scop:** formular adăugare / editare.

Conținut:

* Form:

  * Nume destinatar
  * Telefon
  * Stradă, număr, bloc, apartament
  * Localitate, Județ, Cod poștal
  * Țară
  * Tip adresă:

    * „Doar livrare”
    * „Doar facturare”
    * „Livrare + facturare”
  * Checkbox „Setează ca implicită”
* Mesaje de eroare + hint-uri (ex: „Te rugăm să scrii date reale; curierul le va folosi pentru livrare.”)

---

### `accounts/address_confirm_delete.html` (address_delete)

**Scop:** confirmare ștergere.

Conținut:

* Text: „Ești sigur că vrei să ștergi această adresă?”
* Afișare adresă în clar.
* Buton „Da, șterge” + „Anulează”.

---

## 6. 2FA – email, SMS & trusted devices

### `accounts/enable_2fa.html` (enable_2fa)

* Confirmare de tip:

  * „Vrei să activezi 2FA pentru contul tău?”
  * Buton „Începe configurarea” → redirect practic către `two_factor_setup`.

### `accounts/enable_2fa_email.html`

* Explică:

  * „La fiecare login îți vom trimite un cod pe email.”
* Bifă confirmare + buton „Activează”.

### `accounts/enable_2fa_sms.html`

* Similar cu email, dar:

  * Input pentru număr de telefon (dacă nu e deja validat).
  * Info despre costuri (dacă există) sau limitări.

### `accounts/revoke_trusted_device.html`

* Scop: confirmare revocare.
* Mesaj:

  * „Ești sigur că vrei să revoci acest dispozitiv din lista de încredere?”
* Device info: browser, OS, dată.
* Buton confirmare.

---

## 7. Profil – dimensiuni personale

### `accounts/profile_dimensions.html`

**Scop:** dimensiuni folosite pentru recomandări și filtrare.

Conținut:

* Explicație:

  * „Completează-ți dimensiunile astfel încât să vezi haine care ți se potrivesc mai bine.”
* Form:

  * Înălțime, greutate (opțional)
  * Umeri
  * Bust
  * Talie
  * Șold
  * Lungime picior, interior picior
  * (orice vrei să folosești în matching).
* Hints:

  * Mic desen / link „Cum să te măsori corect” (chiar și o imagine statică).
* Status:

  * Badge „Complet” / „Incomplet”.

---

## 8. Seller – setări & locații

### `accounts/seller_settings.html` (seller_settings)

**Scop:** tot ce ține de vânzător într-un singur loc.

Conținut:

* Card „Status vânzător”:

  * Nivel: Amator / Rising / Top / VIP
  * Comision platformă % actual.
  * Trust score
  * Badge „KYC complet / incomplet”.
* Card „Detalii plăți”:

  * IBAN
  * Nume titular
  * Banca
  * Alte câmpuri relevante.
* Card „Locații marfă / depozite”:

  * Listă locații cu:

    * Adrese depozit, program
    * Badge implicită
    * Butoane „Editează”, „Șterge”
  * Buton „Adaugă locație” → `seller_location_add`.
* Info:

  * „Aceste date sunt folosite pentru calculul costurilor de transport și generarea documentelor de plată.”

---

### `accounts/seller_location_form.html` (seller_location_add)

* Form:

  * Nume locație (ex. „Depozit Oradea”)
  * Adresă completă
  * Tip (Depozit / Magazin / Punct drop-off)
  * Checkbox „Locație implicită”
* Hint: „Aceasta este adresa de unde curierii vor ridica coletele.”

### `accounts/seller_location_confirm_delete.html` (seller_location_delete)

* La fel ca la adrese – confirmare ștergere.
* Afișezi locația în clar.

*(`seller_location_default` doar face redirect, fără template)*

---

## 9. KYC – centrul de verificare

### `accounts/kyc_center.html` (kyc_center)

**Scop:** locul unde user-ul încarcă documente + vede statusul.

Conținut:

* Card „Status KYC”:

  * Stepper: „Neînceput → În verificare → Aprobat / Respins”
  * Data ultimei actualizări.
* Card „Documente încărcate”:

  * Listă cu:

    * Tip document (CI, Pașaport, Certificat înregistrare firmă).
    * Status (în așteptare, aprobat, respins + motiv respingere).
    * Buton „Șterge” → `kyc_document_delete`.
* Form „Încarcă document nou”:

  * Tip document (select)
  * Upload fișier
  * Info: format acceptat, dimensiune maximă, timp estimat verificare.
* Info legal:

  * 1–2 paragrafe simple de ce e necesar KYC și cum protejează tranzacțiile.

---

### `accounts/kyc_document_confirm_delete.html` (kyc_document_delete)

* Confirmare ștergere document.
* Afișezi tipul documentului și statusul lui.

---

## 10. Ștergere cont

### `accounts/delete_account_request.html` (delete_account_request)

**Scop:** user-ul cere ștergerea contului.

Conținut:

* Avertisment:

  * Ce se întâmplă cu:

    * Comenzi în curs
    * Wallet
    * Facturi
    * Date KYC (în măsura legii)
* Mic form:

  * Motiv (optional)
  * Checkbox: „Înțeleg că această acțiune este ireversibilă.”
* Buton „Solicită ștergerea contului”.

---

### `accounts/delete_account_confirm.html` (delete_account_confirm)

**Scop:** confirmare după ce ștergerea a fost procesată (sau programată).

Conținut:

* Mesaj: „Contul tău a fost șters (sau va fi șters în X zile conform politicii).”
* Info:

  * Ce date se păstrează legal (facturi, comenzi, etc. – text generic).
* Buton „Înapoi la Home”.

---

## 11. Ce lipsește încă din `urls.py` dar ține de `accounts`

Din planul mare știm că mai ai nevoie (mai încolo) de:

* O pagină „Referral & cod invitat”:

  * Template gen `accounts/referral_center.html`
  * Arăți:

    * Codul user-ului
    * Link de share cu cod
    * Statistici: câți invitați activi, câți au cumpărat, bonusuri în wallet.
* Eventual o pagină „Profil roluri & permisiuni” (dacă vrei să fie user-facing) unde vezi:

  * Ești buyer activ
  * Ești seller activ
  * Ești shop manager / admin (doar info, nu se schimbă de aici)

Putem adăuga ulterior rutele, dar e bine să știi din start că `accounts` va acoperi și zona asta.

---