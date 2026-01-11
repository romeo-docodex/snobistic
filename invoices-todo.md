## invoices — audit (format fix)

### ✅ CE AVEM

* **Model `Invoice`** cu:

  * legare la `orders.Order` (`order`)
  * tip factură (`invoice_type`: product/shipping/commission/return)
  * buyer + seller (seller opțional)
  * sume (net/vat_percent/vat_amount/total), monedă
  * status + timestamps
  * `invoice_number` generat automat după primul `save()`
* **Admin**: listare + filtre + search (ok pentru început).
* **Views**

  * `invoice_detail_view`: pagină HTML de detaliu, cu check de acces.
  * `invoice_pdf_view`: generare PDF via WeasyPrint, cu template dedicat.
* **Templates**

  * `invoice_detail.html`: UI modern, clar.
  * `invoice_pdf.html`: layout A4 ok pentru WeasyPrint.
* **Urls**: detail + download.

---

## ❌ CE LIPSEȘTE (blocante / “marketplace-grade”)

1. **Bug major: `invoice_number` = `unique=True` + `blank=True` (fără `null=True`)**

   * În DB (mai ales Postgres), `""` este valoare, deci **a doua factură fără număr setat înainte de insert poate crăpa** pe unique.
   * Tu îl setezi abia după `super().save()`, deci **insert-ul inițial intră cu string gol** → coliziune.

2. **Snapshot fiscal (date “înghețate” la emitere)**

   * O factură corectă nu ar trebui să depindă de `User.get_full_name` sau email “live”.
   * Lipsesc câmpuri de tip snapshot:

     * emitent: denumire firmă, CUI/VAT, RC, adresă, IBAN, bancă, etc.
     * beneficiar: nume/firmă, adresă, CUI (dacă e PJ), etc.
   * Fără snapshot, dacă user își schimbă datele, **factura istorică se “rescrie”**.

3. **Linii de factură (line items)**

   * Acum ai doar totaluri (net/TVA/total) și o descriere generică.
   * Marketplace real: ai nevoie de `InvoiceLine` (descriere, cantitate, unit price, VAT, total, SKU, referință produs, etc.), mai ales pentru product invoices / shipping / buyer protection.

4. **Stocare PDF**

   * Momentan PDF-ul se generează “on-the-fly” la fiecare download.
   * Lipsesc:

     * `pdf_file = FileField(...)` + generare o singură dată
     * `pdf_generated_at`, `pdf_sha256`, versionare (dacă regenerezi)
   * Altminteri: cost CPU + inconsistențe dacă template-ul se schimbă.

5. **Workflow complet de emitere / anulare / storno**

   * Ai `Status`, dar lipsește logica:

     * emitere controlată (DRAFT → ISSUED)
     * `issued_at` setat la emitere (nu auto_now_add)
     * anulare / storno (inclusiv legare la factura inițială)
     * “return invoice” ar trebui de multe ori să fie **credit note / storno** cu relație clară.

6. **Listări + UX în dashboard**

   * Nu există:

     * “Facturile mele” pentru buyer
     * “Facturi comision” pentru seller
     * paginare, filtre (tip, status, perioadă), search după număr.
   * Nici integrare în `dashboard`.

7. **Integrare automată cu orders/payments**

   * Lipsesc trigger-e clare:

     * când se creează factura (la payment captured? la livrare? la finalizare?)
     * cine emite ce (platformă vs seller PJ)
     * generare buyer protection / shipping separată sau inclusă.

8. **Testare**

   * Lipsesc teste pentru:

     * acces (buyer/seller/staff)
     * generare număr (fără coliziuni)
     * calcule TVA/total
     * PDF generation fallback.

---

## 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (calitate, hardening, scalare)

### 1) Numerotare facturi (corectă, atomică, fără bug-ul de unique)

* Recomandare enterprise:

  * `invoice_number` **nullable** (`null=True, blank=True`) + unique
  * sau mai bine: `invoice_series`, `invoice_seq`, `issued_year` + `UniqueConstraint(series, year, seq)`
  * generare număr **înainte de insert** sau folosind un **counter atomic** (model separat “InvoiceCounter” pe an/serie).

### 2) Calcul sume (source of truth)

* Acum ai 3 câmpuri de sumă + procent TVA, dar **nu le calculezi**.
* Recomandare:

  * calculezi `vat_amount` și `total_amount` în `clean()`/`save()` (cu quantize la 2 zecimale)
  * validezi că `total = net + vat`.
* Ideal: folosești “Money” pattern (sau măcar utilitar comun pentru rounding).

### 3) `issued_at` vs `created_at`

* `issued_at = auto_now_add` nu e ideal dacă există draft.
* Mai corect:

  * `created_at` la creare,
  * `issued_at` `null=True` și setat când status devine `ISSUED`.

### 4) Modelul de părți: buyer/seller e prea simplist pentru fiscal

* Pentru comision: “buyer” nu e “beneficiar” logic.
* Introdu:

  * `issuer_type` (platform/seller)
  * `bill_to_type` (buyer/seller/platform)
  * plus snapshot fields (denumire, adresă, CUI etc.)

### 5) PDF generation

* Dacă rămâi pe WeasyPrint:

  * fallback ok, dar pune un mesaj mai “prod” + log
  * adaugă caching headers și/sau stocare PDF
  * regen doar dacă status = DRAFT sau dacă admin forțează.
* În view, în loc să redirecționezi la `dashboard:orders_list`, mai safe:

  * `return HttpResponse(status=403)` sau `PermissionDenied` (nu “teleporta” userul în alt context).

### 6) Template hardening

* `order.payment_status_label`, `order.latest_payment`, `order.escrow_status_label` trebuie să fie safe:

  * dacă lipsesc, template-ul poate pica.
  * folosește `{% if %}` mai defensiv sau expune în context valori default.

### 7) Admin (operator-ready)

* adaugă:

  * `readonly_fields` (invoice_number, issued_at, totals după emitere)
  * acțiuni: “Issue”, “Cancel”, “Regenerate PDF”
  * filtre pe perioadă (`date_hierarchy = "issued_at"`).

---

### Concluzie rapidă

App-ul e un **MVP bun ca UI + download PDF**, dar la nivel “marketplace fiscal” are 3 probleme critice:

1. **bug-ul de unique pe `invoice_number`**,
2. **lipsa snapshot-urilor fiscale + line items**,
3. **lipsa workflow-ului (issue/cancel/storno) și stocării PDF**.

Dacă vrei, următorul pas “dintr-o singură trecere” poate fi: refactor model (număr + snapshot + linii), apoi update views/templates + admin + migrații + teste minimale.
