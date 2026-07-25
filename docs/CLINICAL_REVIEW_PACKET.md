# Clinical review packet - SleepWise interaction rules and dose ranges

**For:** a licensed pharmacist or clinician
**From:** Kelvin Asiedu, SleepWise (independent educational project)
**Prepared:** June 2026 · dataset version 2026-06-24 · engine 1.1.0
**Estimated time:** 20-30 minutes for Priority A and B, which is the part that matters most

---

## What I am asking

SleepWise is a free, non-commercial educational tool that checks common sleep supplements
against a user's medications and health flags. It makes no money, sells nothing, and
carries no advertising. It states plainly on every page that it has **not** been reviewed
by a licensed professional.

I would like that to stop being true.

I am asking you to review the 19 interaction rules and 6 dose ranges below and mark each
one **keep / narrow / remove / needs a different source**. You do not need to write
anything long. A tick and a note is enough.

An external technical review found that only about 12 of 27 sampled claims are directly
supported by the page they cite. I have grouped the rules so the most doubtful ones come
first. If you only have 20 minutes, **Priority A and B are the ones worth your time.**

## What I am not asking

- Not asking you to endorse the product, the site, or my code.
- Not asking for anything that creates a duty of care to users. This is a review of
  reference material, not clinical supervision.
- Not asking you to write content. If a claim has no good source, the correct answer is
  "remove it," and I will remove it.

## How to mark each row

| Code | Meaning |
|---|---|
| **K** | Keep as written. Severity and wording are defensible. |
| **N** | Narrow it. Right idea, too broad (e.g. applies to one drug, not the whole class). Note the narrowing. |
| **R** | Remove. Not supportable, or not clinically meaningful at these doses. |
| **S** | Keep, but needs a better source. Note one if you have it. |
| **?** | Outside your comfort zone. Leave it, I will treat it as unverified. |

Severity key used by the tool: **BLOCK** = "ask a clinician first, no self-directed use";
**WARN** = "use caution, discuss it". There is no "safe" verdict anywhere in the product.

---

## Priority A - rules whose cited source does not appear to cover them (7 rules)

All seven cite the MedlinePlus herbs and supplements index. That index does not have
entries for L-theanine, glycine, or ashwagandha, and its herb content is currently listed
as unavailable. **My default action for every row here is REMOVE unless you tell me
otherwise**, because I would rather show nothing than a warning I cannot stand behind.

| # | Supplement | Trigger | Sev | Current message (abridged) | K/N/R/S/? | Note |
|---|---|---|---|---|---|---|
| 3 | Valerian | Opioids | BLOCK | Adds to opioid-related CNS depression; can be dangerous | | |
| 14 | L-theanine | Antihypertensives | WARN | May lower BP and add to antihypertensive medication | | |
| 15 | Glycine | Clozapine | WARN | May reduce clozapine effectiveness | | |
| 16 | Ashwagandha | Pregnancy | BLOCK | Not recommended during pregnancy | | |
| 17 | Ashwagandha | Immunosuppressants | WARN | May stimulate immunity, counteracting therapy | | |
| 18 | Ashwagandha | Thyroid hormone | WARN | May raise thyroid hormone levels | | |
| 19 | Ashwagandha | Sedative-hypnotics | WARN | May add to sedative effect | | |

**Specific questions on Priority A:**

- **#3 (valerian + opioids):** additive CNS depression seems mechanistically sound, but is
  BLOCK the right severity, and is there a source you would cite instead?
- **#15 (glycine + clozapine):** the clozapine-augmentation literature I can find used
  roughly 30-60 g/day of glycine. SleepWise displays a **3-5 g** sleep dose. Is a warning
  at 3-5 g meaningful, or is this rule an artifact of a much higher research dose?
- **#16-19 (ashwagandha):** NCCIH has an ashwagandha page. Would you accept these four
  claims if they cited that instead, and are any of them too broad as written?

---

## Priority B - one source, five claims that may outrun it (5 rules)

All five cite the NCCIH melatonin page. The technical review found that page supports the
anticoagulant/bleeding caution and the circadian and jet-lag material, but did **not** find
support for the blood-pressure, diabetes, or immunosuppressant claims.

| # | Supplement | Trigger | Sev | Current message (abridged) | K/N/R/S/? | Note |
|---|---|---|---|---|---|---|
| 5 | Melatonin | Antiplatelets | WARN | May add to antiplatelet effect and bleeding risk | | |
| 6 | Melatonin | Antihypertensives | WARN | May influence BP and interact with antihypertensives | | |
| 7 | Melatonin | Antidiabetics | WARN | May affect blood glucose | | |
| 8 | Melatonin | Immunosuppressants | WARN | May stimulate immune activity, counteracting therapy | | |
| 9 | Melatonin | Benzodiazepines | WARN | Adds to sedative effect | | |

**Specific question:** #6 may be defensible only for nifedipine specifically rather than
the whole antihypertensive class. Should it be narrowed to that, or removed?

---

## Priority C - rules that appear supported (7 rules, spot-check only)

These cite ODS or NCCIH pages that do appear to carry the relevant content. A quick
sanity check on severity is all I am after.

| # | Supplement | Trigger | Sev | Source | K/N/R/S/? | Note |
|---|---|---|---|---|---|---|
| 1 | Valerian | Benzodiazepines | BLOCK | ODS valerian | | |
| 2 | Valerian | Sedative-hypnotics | BLOCK | ODS valerian | | |
| 4 | Melatonin | Anticoagulants | WARN | NCCIH melatonin | | |
| 10 | Magnesium | Quinolone antibiotics | WARN | ODS magnesium | | |
| 11 | Magnesium | Tetracycline antibiotics | WARN | ODS magnesium | | |
| 12 | Magnesium | Bisphosphonates | WARN | ODS magnesium | | |
| 13 | Magnesium | Kidney disease | BLOCK | ODS magnesium | | |

**Note on #1 and #2:** the ODS valerian page describes the sedative interaction in
theoretical terms. Is BLOCK too strong, or is it the right conservative call for a
consumer tool?

**Note on #10-12:** these are separation-of-dosing issues, not "do not combine" issues.
The tool currently renders them at the same WARN level as mechanism-based cautions. Would
you distinguish them?

---

## Dose ranges (6)

These are displayed as "typical dose" with the label *general range, not a personal
recommendation*. Same marking codes.

| Supplement | Displayed | Timing | K/N/R/S/? | Note |
|---|---|---|---|---|
| Melatonin | 0.5-5 mg | 30-60 min before bed | | |
| Magnesium glycinate | 200-400 mg | evening | | |
| L-theanine | 200-400 mg | before bed | | |
| Glycine | 3-5 g | before bed | | |
| Valerian | 300-600 mg | 30-120 min before bed | | |
| Ashwagandha | 250-600 mg | evening | | |

**Specific concerns I already know about:**

1. **Magnesium 200-400 mg.** The ODS fact sheet sets a tolerable upper intake level of
   **350 mg/day for supplemental** magnesium in adults. The displayed range runs past that.
   It also does not say whether the figure is **elemental magnesium** or compound weight,
   which for glycinate is a large difference. Should this be narrowed, labelled elemental,
   or removed pending a range-specific source?
2. **Melatonin 0.5-5 mg.** I have not found a single source that states this exact range.
   Is there one you would cite, or should the range come down or come out?
3. **All six.** If a range has no range-specific citation, my default is to remove the
   number and describe the dose qualitatively instead. Tell me if that is the wrong call.

---

## Also worth a moment, if you have it

- **Coverage gaps.** The tool knows ~71 medication names across 14 drug classes. Anything
  it does not recognize now makes the profile "incomplete" and returns general information
  only, with no personalized verdict. Are there sleep-relevant interactions you would
  expect a tool like this to catch that are missing entirely?
- **Framing.** Every result ends by directing the user to a pharmacist or clinician. Is
  there anything in that framing that would annoy you if a patient brought it to your
  counter?

---

## Sign-off

Only fill in what you are comfortable with. I will publish exactly what you authorize and
nothing more.

```
Reviewer name: ______________________________________________

Credentials (e.g. PharmD, RPh, MD):  ________________________

License state / number (optional, not published): ___________

Date of review: _____________________________________________

Scope reviewed (circle):   Priority A    Priority B    Priority C    Doses    All

May I publish your name and credentials as the reviewer of the
scope above?                                  YES  /  NO

May I state that this dataset has received licensed pharmacist
review, without naming you?                   YES  /  NO

Signature: __________________________________________________
```

## What I will do with this

1. Apply every R and N immediately. Removals happen first, before anything else ships.
2. Re-cite the S rows or remove them if I cannot find the source.
3. Record your name, credentials, scope, and date in the dataset and on the site **only**
   to the extent the sign-off above authorizes. If you decline attribution, nothing is
   published and the site continues to say the data is not clinician-reviewed.
4. Version the dataset so this review is tied to a specific, inspectable snapshot.
5. Send you the diff of what changed, so you can confirm I applied it faithfully.

Corrections after the fact are welcome at any time through
[the project issue tracker](https://github.com/kelvinasiedu-programmer/sleepwise/issues)
or directly to me. If you later want your attribution withdrawn, I will remove it and say
so publicly.

Thank you. This is genuinely the one thing standing between this project and being
something I would be comfortable recommending to a friend.
