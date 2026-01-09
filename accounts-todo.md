Mai jos ai **planul COMPLET de template-uri** (canonical), **100% aliniat cu `views.py` + `urls.py`** pe care le-ai lipit. Îl poți folosi ca checklist “există / lipsește / de îmbunătățit”.

---

# Plan complet templates `accounts/` (conform views)

## 0) Convenții + reguli globale (toate template-urile)

* **Path base:** `templates/accounts/...`
* **Extends:** `{% extends "base.html" %}`
* **Mesaje:** afișezi `messages` (success/error/info)
* **Erori:** `form.non_field_errors` + `field.errors`
* **Toate forms:** `{% csrf_token %}`
* **Acțiuni critice:** **POST only** (logout, delete, 2FA disable/revoke etc.)
* **Next propagation:**

  * la login/register: folosești **`{{ next }}` din context** (nu doar `request.GET.next`)
  * la link-uri între login/register: adaugi `?next={{ next|urlencode }}` dacă `next` există

---

# 1) Auth templates (views din `accounts/auth/*`)

## 1.1 `templates/accounts/auth/login.html`

**View:** `LoginView`
**Must-have:**

* Fields: `username`, `password`, `remember_me`
* Hidden next: `<input type="hidden" name="next" value="{{ next }}">` (dacă `next`)
* Link reset: `{% url 'accounts:password_reset' %}`
* Link register: `{% url 'accounts:register' %}` + păstrare `next`
* (Optional) Social buttons dacă există:

  * `social_google_url`
  * `social_facebook_url`
  * `social_apple_url`
* Honeypot optional
* UI: mesaje + erori globale

## 1.2 `templates/accounts/auth/register.html`

**View:** `RegisterView`
**Must-have:**

* Hidden next: `<input type="hidden" name="next" value="{{ next }}">`
* Form fields (din `RegisterForm`): (role, nume, email, phone, DOB, iban seller etc.)
* Checkbox terms + link legal pages
* Link login + păstrare `next`
* (Optional) Social buttons: `social_*_url`
* UI: mesaje + erori

## 1.3 `templates/accounts/auth/registration_email_sent.html`

**View:** `registration_email_sent()`
**Must-have:**

* Confirmare “ți-am trimis email”
* Instrucțiuni Spam/Promotions
* **Form POST** către `{% url 'accounts:resend_activation' %}`:

  * input `email`
  * CSRF
  * (recomandat) hidden next dacă vrei păstrare redirect:

    * `<input type="hidden" name="next" value="{{ request.GET.next }}">`
* Link back login: `{% url 'accounts:login' %}`

## 1.4 (Nu există template) activare cont

**View:** `activate_account()`

* Redirect + messages (nu randează template)

## 1.5 (Nu există template) resend activation

**View:** `resend_activation`

* Endpoint POST-only, folosit din `registration_email_sent.html`

---

# 2) 2FA templates (views din `accounts/auth/*`)

## 2.1 `templates/accounts/auth/two_factor.html`

**View:** `TwoFactorView`
**Must-have:**

* Field: `code` (acceptă și backup codes)
* Checkbox: `remember_device` (view verifică `== "on"`)
* CSRF
* UI: mesaje + erori
* Text suport: TOTP/Email/SMS/Backup

> Hidden `next` nu e obligatoriu (next e în session), dar poți include dacă vrei.

## 2.2 `templates/accounts/auth/two_factor_setup.html`

**View:** `two_factor_setup()`
**Must-have:**

* Primește `otpauth_uri`
* QR generator (client-side) + fallback “copy uri”
* Form POST către `{% url 'accounts:two_factor_setup_verify' %}` cu:

  * `code` (6 cifre)
  * CSRF
* CTA cancel: `{% url 'accounts:profile_security' %}`

## 2.3 (Nu există template) verify setup

**View:** `two_factor_setup_verify()`

* POST -> redirect + messages

## 2.4 (Nu există template) 2FA manage

* Management 2FA se face **în `profile_security.html`** (enable/disable/regenerate/revoke)

---

# 3) Password templates (views din `accounts/password/*`)

## 3.1 `templates/accounts/password/password_reset.html`

**View:** `CustomPasswordResetView`
**Must-have:**

* Form email (crispy)
* CSRF
* Submit
* Link back login
* UI mesaje

## 3.2 `templates/accounts/password/password_reset_done.html`

**View:** `CustomPasswordResetDoneView`
**Must-have:**

* Confirmare “dacă emailul există”
* Link login
* Link “încearcă alt email” (opțional)

## 3.3 `templates/accounts/password/password_reset_confirm.html`

**View:** `CustomPasswordResetConfirmView`
**Must-have:**

* Caz `validlink`:

  * form new_password1/new_password2
  * CSRF + submit
* Caz invalid:

  * alert + link `{% url 'accounts:password_reset' %}`
* Link back login

## 3.4 `templates/accounts/password/password_reset_complete.html`

**View:** `CustomPasswordResetCompleteView`
**Must-have:**

* Confirmare “parolă schimbată”
* Link login

## 3.5 `templates/accounts/password/password_change.html`

**View:** `CustomPasswordChangeView`
**Must-have:**

* Form old_password/new_password1/new_password2
* CSRF + submit
* Link back security: `{% url 'accounts:profile_security' %}`

## 3.6 `templates/accounts/password/password_change_done.html`

**View:** `CustomPasswordChangeDoneView`
**Must-have:**

* Confirmare
* Link `{% url 'accounts:profile_security' %}`

## 3.7 Email templates reset (obligatorii)

**View:** `CustomPasswordResetView` folosește explicit:

* `templates/accounts/password/password_reset_email.html`
* `templates/accounts/password/password_reset_subject.txt`

**Must-have în email:**

* link complet reset
* text “dacă nu ai cerut, ignoră”

---

# 4) Profile templates (views din `accounts/profile/*`)

## 4.1 `templates/accounts/profile/profile.html`

**View:** `profile()`
**Must-have:**

* Afișare counters:

  * `favorites_count`, `addresses_count`
  * `dimensions_complete`
* Afișare seller info (dacă există):

  * `seller_level_label`, `seller_commission_label`, `seller_trust_score`
* Linkuri către subpagini:

  * `{% url 'accounts:profile_personal' %}`
  * `{% url 'accounts:profile_security' %}`
  * `{% url 'accounts:profile_dimensions' %}`
  * `{% url 'accounts:address_list' %}`
  * `{% url 'accounts:sessions_center' %}`
  * `{% url 'accounts:roles_center' %}`
  * `{% url 'accounts:kyc_center' %}`
  * `{% url 'accounts:seller_settings' %}` (doar dacă seller)

## 4.2 `templates/accounts/profile/profile_data.html`

**View:** `profile_personal()`
**Must-have:**

* Form personal (ProfilePersonalForm): `form`

  * dacă upload avatar: `enctype="multipart/form-data"`
* Form preferințe (ProfilePreferencesForm): `prefs_form`
* IMPORTANT: butonul de preferințe trebuie să trimită `name="save_prefs"`

  * ca view să știe că e branch-ul de prefs
* UI mesaje + erori

## 4.3 `templates/accounts/profile/profile_security.html`

**View:** `profile_security()`
**Context:** `devices`, `events`, `backup_codes_once`
**Must-have:**

### A) Change password

* Link `{% url 'accounts:password_change' %}`

### B) Email change request (POST-only)

* **Form POST** către `{% url 'accounts:email_change_request' %}`

  * input `new_email`
  * CSRF

### C) 2FA management

* Enable TOTP: link `{% url 'accounts:enable_2fa' %}`
* Enable Email: link `{% url 'accounts:enable_2fa_email' %}`
* Enable SMS: link `{% url 'accounts:enable_2fa_sms' %}`
* Disable 2FA: **form POST** `{% url 'accounts:disable_2fa' %}` + CSRF
* Regenerate backup codes: **form POST** `{% url 'accounts:regenerate_backup_codes' %}` + CSRF
* Afișezi `backup_codes_once` dacă există (o singură dată)

### D) Trusted devices

* Listezi `devices`
* Revoke: **form POST** către `{% url 'accounts:revoke_trusted_device' pk=device.pk %}` + CSRF

### E) Events (ultimele 20)

* Listezi `events`

### F) Delete account

* Request code: **form POST** `{% url 'accounts:delete_account_request' %}` + CSRF
* Link confirm page: `{% url 'accounts:delete_account_confirm' %}`

### G) Logout all sessions

* **form POST** `{% url 'accounts:logout_all_sessions' %}` + CSRF

### H) GDPR export

* Link `{% url 'accounts:gdpr_export' %}` (GET în view)

## 4.4 `templates/accounts/profile/profile_dimensions.html`

**View:** `profile_dimensions()`
**Must-have:**

* `form` (ProfileDimensionsForm)
* `dimensions_complete` indicator
* CSRF + submit

---

# 5) Addresses templates (accounts/profile/*)

## 5.1 `templates/accounts/profile/address_list.html`

**View:** `address_list()`
**Must-have:**

* List adrese
* Link add: `{% url 'accounts:address_add' %}`
* Link edit: `{% url 'accounts:address_edit' pk=address.pk %}`
* Delete: **form POST** `{% url 'accounts:address_delete' pk=address.pk %}` + CSRF

> Nu există confirm delete page în flow-ul actual.

## 5.2 `templates/accounts/profile/address_form.html`

**View:** `address_form()`
**Must-have:**

* `form` (AddressForm)
* CSRF + submit
* cancel back `{% url 'accounts:address_list' %}`

---

# 6) Seller templates (accounts/profile/*)

## 6.1 `templates/accounts/profile/seller_settings.html`

**View:** `seller_settings()`
**Context:** `form`, `locations`, `add_form`
**Must-have:**

* Seller settings form (`form`) CSRF + submit
* List locations (`locations`)
* Add location form (`add_form`) **POST** către `{% url 'accounts:seller_location_add' %}`
* Make default: **form POST** `{% url 'accounts:seller_location_make_default' pk=loc.pk %}`
* Delete loc: **form POST** `{% url 'accounts:seller_location_delete' pk=loc.pk %}`

> Nu există pagini separate pentru add/delete locations.

---

# 7) KYC user templates (accounts/profile/*)

## 7.1 `templates/accounts/profile/kyc_center.html`

**View:** `kyc_center()`
**Context:** `profile`, `kyc_request`, `documents`, `form`
**Must-have:**

* Afișare status request + list documents
* Upload form (KycDocumentForm) CSRF + submit
* Delete document:

  * link către `{% url 'accounts:kyc_document_delete' pk=doc.pk %}` (GET -> confirm)

## 7.2 `templates/accounts/profile/kyc_document_confirm_delete.html`

**View:** `kyc_document_delete()`
**Must-have:**

* Confirmare
* **POST** + CSRF către același URL

---

# 8) Staff KYC templates (accounts/staff/*)

## 8.1 `templates/accounts/staff/kyc_queue.html`

**View:** `staff_kyc_queue()`
**Must-have:**

* Listă KycRequest + link review:

  * `{% url 'accounts:staff_kyc_review' pk=req.pk %}`

## 8.2 `templates/accounts/staff/kyc_review.html`

**View:** `staff_kyc_review()`
**Must-have:**

* Detalii request + list docs
* Approve: **form POST** `{% url 'accounts:staff_kyc_approve' pk=kyc_request.pk %}` + CSRF
* Reject: **form POST** `{% url 'accounts:staff_kyc_reject' pk=kyc_request.pk %}` + CSRF

  * textarea `name="reason"`

> Nu există `staff_kyc_reject.html`.

---

# 9) Roles templates (accounts/profile/*)

## 9.1 `templates/accounts/profile/roles_center.html`

**View:** `roles_center()`
**Must-have:**

* status roles din `profile`
* Upgrade seller: **form POST** `{% url 'accounts:upgrade_to_seller' %}` + CSRF
* Downgrade: **form POST** `{% url 'accounts:downgrade_roles' %}` + CSRF
* Toggle seller_can_buy: **form POST** `{% url 'accounts:toggle_seller_can_buy' %}` + CSRF

---

# 10) Sessions templates (accounts/profile/*)

## 10.1 `templates/accounts/profile/sessions_center.html`

**View:** `sessions_center()`
**Must-have:**

* list trusted devices (`devices`)
* logout all sessions: **form POST** `{% url 'accounts:logout_all_sessions' %}` + CSRF

---

# 11) Delete account templates (accounts/profile/*)

## 11.1 `templates/accounts/profile/delete_account_confirm.html`

**View:** `delete_account_confirm()`
**Must-have:**

* `form` (DeleteAccountConfirmForm)
* CSRF + submit
* explicație consecințe
* Link back security

> Nu există `delete_account_request.html` (request e POST-only din security).

---

# 12) Ce NU ai voie să uiți (fișiere “invizibile” dar obligatorii)

* `templates/accounts/password/password_reset_email.html`
* `templates/accounts/password/password_reset_subject.txt`

---

Dacă vrei, îți fac imediat și o listă “**tree**” (ca în terminal) cu toate fișierele + path-urile exacte, ca să copiezi direct în proiect.
