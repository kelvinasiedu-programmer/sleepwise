"""Train and evaluate the medication normalizer, then export it as plain JSON.

    python -m ml.train

A character n-gram TF-IDF vectoriser feeding multinomial logistic regression. That
choice is deliberate rather than a limitation:

* Character n-grams are the right representation for the actual failure mode. Typos and
  formulation noise perturb characters, not words, so "lorazepan 1mg tab" still shares
  most of its 3-grams with "lorazepam".
* The whole problem is a few thousand short strings over 15 classes. A transformer here
  would be slower, unexplainable, and no more accurate.
* Fitted coefficients export to JSON, so **inference needs no scikit-learn at runtime.**
  The deployed service keeps its zero-dependency install; sklearn is a training-time tool.

The headline metric is not accuracy. It is the false-accept rate on drugs the project does
not cover, because assigning a class to an unknown drug is how a missed interaction turns
into a confident recommendation. Accuracy is allowed to lose to safety here.
"""

from __future__ import annotations

import difflib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.normalize import LOCAL_DRUG_CLASSES, _clean  # noqa: E402
from ml.dataset import UNKNOWN, build  # noqa: E402

MODEL_PATH = ROOT / "ml" / "normalizer_model.json"
LOG_PATH = ROOT / "ml" / "experiments.jsonl"
REPORT_PATH = ROOT / "docs" / "NORMALIZER.md"

# Below this probability the model declines to answer. Tuned on the held-out set for
# false accepts, not accuracy: see docs/NORMALIZER.md.
DEFAULT_THRESHOLD = 0.60
CONFIG = {
    "analyzer": "char_wb",
    "ngram_range": [2, 4],
    "min_df": 2,
    "sublinear_tf": True,
    "C": 4.0,
    "max_iter": 2000,
    "class_weight": "balanced",
    "seed": 20260624,
    "per_name": 40,
    "holdout_frac": 0.2,
}


def baseline_predict(text: str) -> str:
    """The pre-model matcher: exact dictionary, then fuzzy, with nothing vetoing it.

    Reimplemented here rather than calling `_match`, because `_match` now routes through
    the model veto. Calling it would measure the new behaviour and report it as the
    baseline, which would make the comparison meaningless.
    """
    cleaned = _clean(text)
    if not cleaned:
        return UNKNOWN
    for candidate in [cleaned, *cleaned.split()]:
        if candidate in LOCAL_DRUG_CLASSES:
            return LOCAL_DRUG_CLASSES[candidate]
    known = list(LOCAL_DRUG_CLASSES)
    for token in cleaned.split():
        close = difflib.get_close_matches(token, known, n=1, cutoff=0.85)
        if close:
            return LOCAL_DRUG_CLASSES[close[0]]
    return UNKNOWN


def exact_predict(text: str) -> str:
    """Dictionary hits only, with the fuzzy fallback removed.

    Isolating this shows how much of the baseline's accuracy - and how much of its false
    accepts - comes from fuzzy matching rather than exact lookup.
    """
    cleaned = _clean(text)
    if not cleaned:
        return UNKNOWN
    for candidate in [cleaned, *cleaned.split()]:
        if candidate in LOCAL_DRUG_CLASSES:
            return LOCAL_DRUG_CLASSES[candidate]
    return UNKNOWN


def score(pairs: list[tuple[str, str]], predict) -> dict:
    """Accuracy split by whether the truth is a covered drug, plus false accepts.

    false_accept_rate: of the entries whose true label is `unknown`, the share given a
    drug class anyway. This is the number that matters for safety.
    """
    known = [(t, y) for t, y in pairs if y != UNKNOWN]
    unknown = [(t, y) for t, y in pairs if y == UNKNOWN]

    known_hits = sum(1 for t, y in known if predict(t) == y)
    false_accepts = sum(1 for t, _ in unknown if predict(t) != UNKNOWN)
    return {
        "known_accuracy": known_hits / len(known) if known else 0.0,
        "unknown_rejected": ((len(unknown) - false_accepts) / len(unknown) if unknown else 1.0),
        "false_accept_rate": false_accepts / len(unknown) if unknown else 0.0,
        "n_known": len(known),
        "n_unknown": len(unknown),
    }


def main() -> int:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        print("scikit-learn is required to train:  pip install -r requirements-bench.txt")
        return 1

    train, test, held_out = build(
        seed=CONFIG["seed"], per_name=CONFIG["per_name"], holdout_frac=CONFIG["holdout_frac"]
    )
    print(f"train {len(train)}  test {len(test)}  held-out drugs {len(held_out)}")

    x_train = [t for t, _ in train]
    y_train = [y for _, y in train]

    vec = TfidfVectorizer(
        analyzer=CONFIG["analyzer"],
        ngram_range=tuple(CONFIG["ngram_range"]),
        min_df=CONFIG["min_df"],
        sublinear_tf=CONFIG["sublinear_tf"],
        lowercase=True,
    )
    started = time.perf_counter()
    matrix = vec.fit_transform(x_train)
    clf = LogisticRegression(
        C=CONFIG["C"],
        max_iter=CONFIG["max_iter"],
        class_weight=CONFIG["class_weight"],
    )
    clf.fit(matrix, y_train)
    train_seconds = time.perf_counter() - started
    print(f"fitted in {train_seconds:.1f}s  features {len(vec.vocabulary_)}")

    def model_predict(text: str, threshold: float = DEFAULT_THRESHOLD) -> str:
        probs = clf.predict_proba(vec.transform([text]))[0]
        best = probs.argmax()
        return UNKNOWN if probs[best] < threshold else str(clf.classes_[best])

    # Threshold sweep: the operating point is chosen on false accepts.
    sweep = []
    for threshold in (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9):
        s = score(test, lambda t, th=threshold: model_predict(t, th))
        sweep.append(
            {"threshold": threshold, **{k: s[k] for k in ("known_accuracy", "false_accept_rate")}}
        )
        print(
            f"  threshold {threshold:.1f}  known acc {s['known_accuracy']:.3f}  "
            f"false accepts {s['false_accept_rate']:.3f}"
        )

    def veto_predict(text: str) -> str:
        """Exact dictionary hits stand. Fuzzy hits must be seconded by the model.

        The baseline's false accepts all come from fuzzy matching a near-miss name, so the
        model is used as a second opinion on exactly those cases rather than as a fallback
        for everything.
        """
        exact = exact_predict(text)
        if exact != UNKNOWN:
            return exact
        fuzzy = baseline_predict(text)
        if fuzzy == UNKNOWN:
            return model_predict(text)
        return fuzzy if model_predict(text) == fuzzy else UNKNOWN

    arms = {
        "Rules only (shipped baseline)": score(test, baseline_predict),
        "Exact dictionary only (no fuzzy)": score(test, exact_predict),
        "Model only": score(test, model_predict),
        "Rules then model": score(
            test, lambda t: b if (b := baseline_predict(t)) != UNKNOWN else model_predict(t)
        ),
        "Exact, model-vetoed fuzzy": score(test, veto_predict),
    }
    print()
    for name, s in arms.items():
        print(
            f"{name:34} known {s['known_accuracy']:.3f}  false accepts {s['false_accept_rate']:.3f}"
        )
    # Export to plain JSON so runtime inference needs no sklearn.
    MODEL_PATH.write_text(
        json.dumps(
            {
                "format": "char-tfidf-logreg/1",
                "config": CONFIG,
                "threshold": DEFAULT_THRESHOLD,
                "classes": list(clf.classes_),
                "vocabulary": {term: int(i) for term, i in vec.vocabulary_.items()},
                "idf": [round(float(v), 6) for v in vec.idf_],
                "coef": [[round(float(v), 6) for v in row] for row in clf.coef_],
                "intercept": [round(float(v), 6) for v in clf.intercept_],
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    size_kb = MODEL_PATH.stat().st_size / 1024
    print(f"exported {MODEL_PATH.name} ({size_kb:.0f} KB)")

    record = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": CONFIG,
        "threshold": DEFAULT_THRESHOLD,
        "features": len(vec.vocabulary_),
        "train_seconds": round(train_seconds, 2),
        "n_train": len(train),
        "n_test": len(test),
        "held_out_drugs": held_out,
        "arms": arms,
        "sweep": sweep,
    }
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    def row(name: str, s: dict) -> str:
        return (
            f"| {name} | {s['known_accuracy']:.3f} | {s['unknown_rejected']:.3f} "
            f"| {s['false_accept_rate']:.3f} |"
        )

    sweep_rows = "\n".join(
        f"| {r['threshold']:.1f} | {r['known_accuracy']:.3f} | {r['false_accept_rate']:.3f} |"
        for r in sweep
    )
    REPORT_PATH.write_text(
        "# Medication normalizer\n\n"
        "<!-- Generated by ml/train.py. Do not edit by hand; re-run the trainer. -->\n\n"
        f"Character n-gram TF-IDF into multinomial logistic regression. "
        f"{len(vec.vocabulary_)} features, fitted in {train_seconds:.1f}s on "
        f"{len(train)} synthetic examples, evaluated on {len(test)} held-out ones.\n\n"
        "```bash\npip install -r requirements-bench.txt\npython -m ml.train\n```\n\n"
        "## Results\n\n"
        "| Approach | Known-drug accuracy | Unknown correctly rejected | False-accept rate |\n"
        "|---|---|---|---|\n" + "\n".join(row(name, s) for name, s in arms.items()) + "\n\n"
        "**False-accept rate is the metric that matters.** It is the share of drugs this\n"
        "project does not cover that were nonetheless assigned a drug class. Every false\n"
        "accept is a potential missed interaction presented as a confident answer, so the\n"
        "operating point is chosen on this column rather than on accuracy.\n\n"
        "## Threshold sweep\n\n"
        "| Threshold | Known accuracy | False-accept rate |\n|---|---|---|\n"
        f"{sweep_rows}\n\n"
        f"Shipped threshold: **{DEFAULT_THRESHOLD}**. Below it the model declines to answer\n"
        "and the entry is treated as unrecognized, which makes the profile incomplete and\n"
        "withholds any personalized verdict.\n\n"
        "## Held-out drugs\n\n"
        f"{len(held_out)} of {len(LOCAL_DRUG_CLASSES)} names were excluded from training "
        "entirely, so their score measures generalisation to an unseen name rather than\n"
        "memorisation: "
        f"{', '.join(sorted(held_out))}.\n\n"
        "## Why not a transformer\n\n"
        "The task is a few thousand short strings over 15 classes, and the noise is\n"
        "character-level. n-grams model that directly, train in seconds, and export to\n"
        f"plain JSON ({size_kb:.0f} KB) so runtime inference needs no ML dependency at all.\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"report -> {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
