Perfect, hai să scoatem doar „ce mai e de făcut”, fără ce e deja ok. 🔍

---

## A. Corecții / fine-tuning pe master data

1. **Subcategorii: Costume de baie / lenjerie intimă**

   * Decide și aplică:

     * păstrezi **un singur** entry, cu `is_non_returnable=True`,
       **sau**
     * păstrezi ambele, dar le diferențiezi clar (nume / folosire).

2. **Subcategoriile „Alt tip de …”**

   * Setezi valori de fallback (realiste) pentru:

     * `avg_weight_kg`
     * `co2_avoided_kg`
     * `trees_equivalent`
   * Sau accepți explicit că nu au impact (dar atunci și UI-ul ar trebui să știe).

3. **Branduri – câmpul `group`**

   * Verificat / setat corect `group` pentru:

     * Max Mara Group, Ralph Lauren, Tommy Hilfiger, Gant, COS etc.
   * Ca să poți grupa clar „premium”, „mid”, „fast fashion” în filtre / analytics.

4. **Materiale – flag `is_sustainable`**

   * Verificare rapidă:

     * toate materialele „verzi” din plan au `is_sustainable=True`,
     * niciun material „gri” nu e marcat greșit ca sustenabil.

---

## B. Forms & validare – ce lipsește acum

### 1. `ProductSizeDetailsForm`

**De implementat:**

1. Reguli pe `size_group`:

   * Îmbrăcăminte:

     * `size_alpha` obligatoriu,
     * FR/IT/GB opționale.
   * Încălțăminte:

     * `shoe_size_eu` obligatoriu.
   * Accesorii:

     * `size_alpha` = „One Size” (precompletat / forțat).

2. Hint pentru mărime literă:

   * Dacă FR/IT/GB completate, dar `size_alpha` gol:

     * nu blochezi formularul,
     * setezi un flag (ex. `show_size_alpha_hint`) pentru mesaj în template.

3. „Altă mărime” – de scos (când ești pregătit):

   * eliminat `OTHER` din `SIZE_CHOICES`,
   * eliminat `size_other_label` din model + forms + wizard,
   * updatat `display_size()` + orice logică de SKU care îl folosea.

---

### 2. `ProductDimensionsForm`

**De implementat în `clean()`:**

* Reguli de **obligatoriu/opțional** pe baza `measurement_profile`:

  * TOP, DRESS, JUMPSUIT, PANTS, SKIRT, SHOES, BAGS, BELTS, JEWELRY/ACCESSORY.

**În plus, în template step_dimensions:**

* arăți DOAR câmpurile relevante profilului,
* restul ascunse / disabled (ca să nu pară „random” pentru seller).

---

## C. Sustenabilitate – UX de finisat

1. Checkbox „Nici una” vs celelalte:

   * JS simplu:

     * dacă user bifează „Nici una” → debifezi + dezactivezi celelalte 5;
     * dacă bifează oricare din cele 5 → debifezi + dezactivezi „Nici una”.

2. „Materiale sustenabile”:

   * Ascunzi / dezactivezi checkbox-ul dacă:

     * compoziția nu conține niciun material cu `is_sustainable=True`.
   * Folosești un flag în form (`has_sustainable_materials`).

---

## D. Wizard – completat comportamentul

1. `ProductPhotosForm`:

   * Impus efectiv:

     * minim 4 poze (1 main + min. 3 extra) în `clean()`.

2. `moderation_status` la creare:

   * Schimbat flow:

     * wizard → setează `PENDING` (nu direct `APPROVED`).
   * Restul fluxului (APPROVED / PUBLISHED / SOLD) se va lega de `dashboard` și `orders`.

3. Refactor subcategorie dublă (Costume de baie):

   * decis clar care rămâne / cum se folosesc cele două.

---
