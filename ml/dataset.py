"""Synthetic training data for the medication normalizer.

There is no public corpus of "messy things people type into a medication box", so the
training set is generated from the known drug names by applying the corruptions that
actually show up in free text: dosage strengths, formulation words, salt names, spacing
and punctuation noise, and keyboard typos.

Two properties matter more than volume:

* **Held-out drugs.** Some known drugs are excluded from training entirely, so the test
  set can measure generalisation to a name the model never saw rather than memorisation.
* **Negatives.** Real drugs that this project does not cover (ibuprofen, quetiapine, and
  so on) are included with an `unknown` label. Getting these right is the safety-critical
  behaviour: predicting a class for an uncovered drug is a false accept, which is how a
  missed interaction becomes a confident recommendation.
"""

from __future__ import annotations

import random

from app.normalize import LOCAL_DRUG_CLASSES

UNKNOWN = "unknown"

# Common US drugs deliberately outside this project's coverage. A model that assigns any
# of these a drug class is producing a false accept.
NEGATIVE_DRUGS = [
    "ibuprofen",
    "acetaminophen",
    "paracetamol",
    "quetiapine",
    "atorvastatin",
    "simvastatin",
    "omeprazole",
    "pantoprazole",
    "albuterol",
    "salbutamol",
    "gabapentin",
    "pregabalin",
    "amoxicillin",
    "azithromycin",
    "cetirizine",
    "loratadine",
    "montelukast",
    "hydrochlorothiazide",
    "furosemide",
    "spironolactone",
    "bupropion",
    "venlafaxine",
    "duloxetine",
    "mirtazapine",
    "trazodone",
    "lamotrigine",
    "topiramate",
    "lithium",
    "risperidone",
    "aripiprazole",
    "allopurinol",
    "colchicine",
    "methotrexate",
    "warfarina",  # near-miss spelling
    "vitamin d",
    "fish oil",
    "multivitamin",
    "probiotic",
    "creatine",
    "caffeine",
]

# Formulation and salt tokens that ride along with real entries.
SUFFIXES = [
    "",
    "",
    "",
    "5mg",
    "10 mg",
    "20mg",
    "100mg",
    "0.5 mg",
    "1mg",
    "2.5mg",
    "500 mg",
    "tablet",
    "tab",
    "capsule",
    "cap",
    "er",
    "xr",
    "sr",
    "cr",
    "odt",
    "sodium",
    "hcl",
    "hydrochloride",
    "succinate",
    "tartrate",
    "besylate",
    "potassium",
    "oral",
    "daily",
    "once daily",
    "bid",
    "prn",
    "as needed",
    "at night",
    "nightly",
]
PREFIXES = ["", "", "", "", "generic", "tab", "rx"]
_ADJACENT = {
    "a": "qws",
    "b": "vgn",
    "c": "xdv",
    "d": "serfcx",
    "e": "wsdr",
    "f": "drtgvc",
    "g": "ftyhbv",
    "h": "gyujnb",
    "i": "ujko",
    "j": "huikmn",
    "k": "jiolm",
    "l": "kop",
    "m": "njk",
    "n": "bhjm",
    "o": "iklp",
    "p": "ol",
    "q": "wa",
    "r": "edft",
    "s": "awedxz",
    "t": "rfgy",
    "u": "yhji",
    "v": "cfgb",
    "w": "qase",
    "x": "zsdc",
    "y": "tghu",
    "z": "asx",
}


def _typo(name: str, rng: random.Random) -> str:
    """One realistic keyboard-ish typo: swap, drop, double, or mis-key a character."""
    if len(name) < 4:
        return name
    i = rng.randrange(1, len(name) - 1)
    kind = rng.choice(("swap", "drop", "double", "adjacent"))
    if kind == "swap":
        return name[:i] + name[i + 1] + name[i] + name[i + 2 :]
    if kind == "drop":
        return name[:i] + name[i + 1 :]
    if kind == "double":
        return name[:i] + name[i] + name[i:]
    replacement = _ADJACENT.get(name[i])
    return name[:i] + rng.choice(replacement) + name[i + 1 :] if replacement else name


def corrupt(name: str, rng: random.Random) -> str:
    """Apply a random, realistic set of corruptions to a drug name."""
    text = name
    if rng.random() < 0.30:
        text = _typo(text, rng)
    parts = [rng.choice(PREFIXES), text, rng.choice(SUFFIXES)]
    if rng.random() < 0.15:
        parts.append(rng.choice(SUFFIXES))
    text = " ".join(p for p in parts if p)
    if rng.random() < 0.12:
        text = text.replace(" ", "-", 1)
    if rng.random() < 0.10:
        text = text.upper()
    elif rng.random() < 0.20:
        text = text.title()
    if rng.random() < 0.08:
        text = f"  {text} "
    return text


def build(
    seed: int = 20260624, per_name: int = 40, holdout_frac: float = 0.2
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    """Return (train, test, held_out_drug_names).

    Held-out drugs contribute only to the test set, so their score measures
    generalisation to unseen names rather than recall of memorised ones.
    """
    rng = random.Random(seed)
    names = sorted(LOCAL_DRUG_CLASSES)
    rng.shuffle(names)
    cut = int(len(names) * holdout_frac)
    held_out, trainable = names[:cut], names[cut:]

    train: list[tuple[str, str]] = []
    test: list[tuple[str, str]] = []

    for name in trainable:
        label = LOCAL_DRUG_CLASSES[name]
        for i in range(per_name):
            sample = (corrupt(name, rng), label)
            # Every fifth variant of a trainable drug goes to the test set, so accuracy on
            # seen names is also measured on strings the model was not fitted to.
            (test if i % 5 == 0 else train).append(sample)

    for name in held_out:
        label = LOCAL_DRUG_CLASSES[name]
        for _ in range(per_name // 2):
            test.append((corrupt(name, rng), label))

    for drug in NEGATIVE_DRUGS:
        for i in range(12):
            sample = (corrupt(drug, rng), UNKNOWN)
            (test if i % 3 == 0 else train).append(sample)

    rng.shuffle(train)
    rng.shuffle(test)
    return train, test, held_out
