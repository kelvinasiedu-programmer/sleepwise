# Citation audit

**Date:** June 2026 · **Auditor:** Kelvin Asiedu (project author, not a clinician)

An external review found that only about 12 of 27 sampled claims were directly supported
by the page they cited. This is the record of checking every one against its live source
and acting on the result.

**Method.** Each cited page was fetched and asked, claim by claim, whether it states the
thing being attributed to it. A claim counted as confirmed only if the page says it.
Where a page did not support a claim, the claim was **removed or demoted** - never
rewritten to fit a different source, and never replaced with a guess.

**This is not a clinical review.** It verifies that claims match their citations. Whether
a claim is clinically appropriate, and whether the severities are right, still needs a
licensed pharmacist (see [`CLINICAL_REVIEW_PACKET.md`](CLINICAL_REVIEW_PACKET.md)).

## Outcome

| | Before | After |
|---|---|---|
| Interaction rules | 19 (7 source-confirmed) | 17 (15 source-confirmed) |
| Evidence chunks | 20 (8 marked confirmed, 2 wrongly) | 17 (12 source-confirmed) |
| Dose ranges with a source | 0 of 6, unlabelled | 0 of 6, **labelled as unconfirmed** |
| Dead citations in the data | 16 records | 0 |

## Sources checked

| Source | Verdict |
|---|---|
| [NCCIH Melatonin](https://www.nccih.nih.gov/health/melatonin-what-you-need-to-know) | Supports blood thinners, side effects, jet lag / DSWPD. Silent on blood pressure, diabetes, immunosuppressants, benzodiazepines, and any mg range. |
| [ODS Magnesium](https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/) | Supports the 350 mg supplemental UL, the antibiotic and bisphosphonate interactions with exact separation intervals, and renal accumulation. **Mentions neither sleep nor the glycinate form.** |
| [ODS Valerian](https://ods.od.nih.gov/factsheets/Valerian-HealthProfessional/) | Calls the insomnia evidence "inconclusive" and additive sedation a "theoretical possibility". No opioid mention, no recommended dose range. |
| [NCCIH Ashwagandha](https://www.nccih.nih.gov/health/ashwagandha) | Supports all four previously unsourced rules, plus diabetes, blood pressure, and rare liver injury. |
| MedlinePlus herbs index (was cited 16 times) | Carries no entry for L-theanine, glycine, or ashwagandha. **Dropped entirely.** |

## Removed

| Claim | Why |
|---|---|
| melatonin + antihypertensive | The cited page does not mention blood pressure |
| melatonin + antidiabetic | The cited page does not mention blood glucose |
| melatonin + immunosuppressant | The cited page does not mention immunosuppressants |
| l-theanine + antihypertensive | Cited a page with no L-theanine entry |
| glycine + clozapine | Cited a page with no glycine entry; the clozapine literature also used 30-60 g, against a displayed 3-5 g sleep dose, so this was misleading at the dose shown |

## Corrected

- **Two claims were marked `verified: true` and were not supported**: magnesium/sleep
  quality and magnesium-glycinate tolerability. Both demoted. This is the finding I am
  least comfortable with: the flag was aspirational rather than checked.
- **Valerian wording** now matches the source: "inconclusive" evidence, additive sedation
  as a "theoretical possibility" rather than an established interaction.
- **Magnesium interactions** now carry the exact intervals the source gives (2 hours
  before, or 4 to 6 hours after) instead of a vague "several hours".
- **Melatonin dose range** (0.5-5 mg) is unsupported by any cited source and is withheld.
- **Magnesium dose ceiling lowered from 400 mg to 350 mg**, because the previous figure
  contradicted the supplemental UL stated on the very page it cited.

## Re-cited and now confirmed

All four ashwagandha rules moved from the dead MedlinePlus index to the NCCIH ashwagandha
page, which supports every one. Two further sourced rules were added from the same page
(diabetes, blood pressure), and its liver-injury warning was added to the evidence.

## Kept as precautionary, not confirmed

Two rules stay in place, labelled and shown as precautionary rather than substantiated:

- **valerian + opioids** - opioids are CNS depressants, so additive sedation is plausible;
  the source discusses sedative drugs generally rather than opioids by name.
- **melatonin + benzodiazepines** - the source reports drowsiness but not this pairing.

Deleting a plausible caution to tidy up a citation would make the tool less safe for the
person at risk. They are labelled, not hidden. See the editorial policy.

## Still outstanding

- **No dose range has a source.** All six are labelled unconfirmed. Establishing them
  needs either a range-specific citation or a pharmacist.
- **L-theanine and glycine have no confirmed source at all.** They remain in the catalogue
  with their evidence withheld, so their pages say plainly that nothing is confirmed. That
  is honest but not useful; a real source or removal is the eventual fix.
- **Severities are unreviewed.** Whether valerian + benzodiazepine warrants the strongest
  level is a clinical judgement this audit cannot make.
