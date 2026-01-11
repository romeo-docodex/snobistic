## 8) Audit aplicația `messaging` — format Snobistic

### ✅ CE AVEM

* **Modele (minim funcționale)**

  * `Conversation` cu `participants` (M2M) + `last_updated`
  * `Message` cu `conversation` (FK), `sender`, `text`, `sent_at`, `attachment` (1 fișier)

* **Flux UI de bază**

  * Inbox: `conversation_list_view` (lista conversațiilor userului)
  * Start conversație: `ConversationStartForm` (după email) + `start_conversation_view`
  * Thread conversație: `conversation_detail_view` + form de mesaj cu fișier

* **Admin**

  * Management conversații + mesaje, search pe email și text

---

### ❌ CE LIPSEȘTE (raportat la scopul aplicației)

#### 1) Conversații pe comandă + conversații suport

* Lipsește orice concept de **tip conversație**:

  * `ORDER` (buyer↔seller) și `SUPPORT` (user↔staff).
* Lipsește legătura “**o conversație separată pentru fiecare comandă**”:

  * nu există `order = FK(...)` și nici un **unique constraint** ca să previi duplicate per comandă.
* Lipsește suportul pentru “**implică admin / shop manager**”:

  * nu există roluri/permisiuni/flow pentru a adăuga staff în conversație (ex: dispute).

#### 2) Citit / necitit real

* Nu există model/structură pentru **read state per utilizator**:

  * nu ai `last_read_at` per participant sau `MessageReadReceipt`.
* Nu există logică de “marchează ca citite” la deschiderea conversației.
* Badge-ul “unread” din template NU e unread (e doar count la toate mesajele primite).

#### 3) Atașamente “serioase” (poze/fișiere)

* Doar **un singur attachment** per mesaj; în cerințe e “fișiere/poze” la modul practic (multi).
* Lipsește validarea:

  * limită de mărime, tip mime, extensii permise, sanitizare nume, protecție upload.
* Lipsește afișare/preview pentru imagini (thumbnail), download controlat.

#### 4) Inbox “marketplace-grade”

* Lipsește:

  * preview ultim mesaj, “last message”, sortare robustă,
  * pagination (conversații și mesaje),
  * search/filter (order/support, necitite, arhivate),
  * “mute”, “archive”, “leave/close conversation”.

#### 5) Chat suport + queue position

* Lipsește complet integrarea cu un sistem de **queue**:

  * nu ai `SupportQueueEntry` / `Ticket` / `priority` / `position`.
* Nu există UI/endpoint pentru a afișa “poziția în așteptare”.

#### 6) Reguli de business & securitate

* Oricine poate porni conversație cu oricine **doar pe email**:

  * în marketplace, conversația buyer↔seller ar trebui permisă de regulă **doar dacă există order/listing context**.
* Atașamentele sunt accesibile direct prin `.url` (în funcție de storage) — lipsește protecție “doar participanții pot descărca”.

---

### 🛠️ CE TREBUIE ÎMBUNĂTĂȚIT (bug-uri, calitate, performanță)

#### 1) BUG în template: `{% set %}` nu există în Django

În `message_bubble.html` ai:

```django
{% set bubble_classes = "bg-primary text-white" %}
```

Asta va crăpa în Django template standard. Elimină complet (ai deja condițional pe class).

#### 2) “Unread” este greșit + costisitor

În `conversation_row.html`:

```django
{% with unread=conv.messages.exclude(sender=request.user).count %}
```

* Asta numără **toate mesajele primite vreodată**, nu necitite.
* În plus, e **N+1 queries** (câte un count per conversație în listă).

#### 3) N+1 pe participants și messages

`conversation_list_view` face:

```python
Conversation.objects.filter(participants=request.user)
```

Apoi template-ul iterează `conv.participants.all` + `conv.messages...` → vei avea query spam.
Ai nevoie de `prefetch_related("participants")` și o strategie de agregare/annotate pentru last/unread.

#### 4) Validare mesaj: text obligatoriu chiar dacă ai attachment

Modelul are `text = TextField()` fără blank, iar form-ul îl cere.
În practică vrei: **permite mesaj doar cu fișier**, dar impune regula:

* “trebuie text sau attachment (minim una)”.

#### 5) Permisiuni/consistență

* `ConversationStartForm.save()` creează conversații duplicate la infinit (aceiași participanți).
* Nu previi conversația “cu tine însuți”.
* `conversation_detail_view` nu marchează citite, nu are handling pentru upload invalid, nu are rate-limit/spam guard.

---

## Recomandarea mea de direcție (ca să fie enterprise, Snobistic-ready)

### Model recomandat (minim robust)

* `Conversation`

  * `kind` = `ORDER` / `SUPPORT` / `DISPUTE`
  * `order = FK(Order, null=True, blank=True, unique=True pentru ORDER)`
  * `created_at`, `updated_at`, `last_message_at`
* `ConversationParticipant` (through)

  * `conversation`, `user`
  * `role` = buyer/seller/staff
  * `last_read_at`
  * `is_archived`, `is_muted`, `left_at`
* `Message`

  * `text` (blank=True)
  * `created_at`
  * `type` (text/system)
* `MessageAttachment`

  * `message`, `file`, `mime`, `size`, `is_image`, `checksum`

### Views/UI

* Inbox cu:

  * last message preview, unread count real (din `last_read_at`)
  * paginate + search + filtre (ORDER/SUPPORT, necitite)
* Thread:

  * paginate mesaje
  * mark-as-read la view
  * upload sigur + preview imagini

### Securitate

* download attachments printr-un view protejat (permisiune = participant)
* limită mărime, whitelist mime, rate-limit pe postare mesaje

---

Dacă vrei, următorul pas îl facem exact ca la `accounts`: îți dau un **plan de refactor** “dintr-o singură trecere” (models → migrations → views → templates → admin), ca să ajungem la:

* conversație per comandă (garantat),
* suport separat cu queue,
* unread real,
* atașamente multiple și sigure,
* inbox performant (fără N+1).
