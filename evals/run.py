"""SleepWise evaluation harness.

Run:  python -m evals.run

Prints a scorecard for retrieval quality, the safety rule engine, and explanation
faithfulness, and exits non-zero if any metric falls below its threshold (so CI catches
regressions). Uses the deterministic template explanation, so results are reproducible
with no API keys.
"""

from __future__ import annotations

import json
from pathlib import Path

from app import explain, pages, safety
from app.evidence import retrieve
from app.models import UserInput
from app.normalize import to_drug_classes
from app.recommend import load_catalog, recommend
from app.retrieval import BM25Index, load_corpus, tokenize
from evals import metrics

DATASETS = Path(__file__).resolve().parent / "datasets"
RECALL_K = 3
THRESHOLDS = {
    "recall@3": 0.8,
    "mrr": 0.8,
    "safety": 1.0,
    "coverage": 1.0,
    "hallucinations": 0,
    "definitive_claims": 0,
}

# Phrases that would turn an educational result into a definitive medical claim.
# Cautious wording is a requirement of the system, not a style preference, so it is
# enforced here: any hit fails the scorecard and therefore CI.
PROHIBITED_PHRASES = [
    "is safe",
    "are safe",
    "perfectly safe",
    "completely safe",
    "totally safe",
    "guaranteed",
    "will cure",
    "will treat",
    "will fix",
    "proven to cure",
    "no side effects",
    "risk-free",
    "no risk",
    "cannot interact",
    "you should take",
]


def _load(name: str):
    return json.loads((DATASETS / name).read_text(encoding="utf-8"))


def run_retrieval() -> tuple[float, float]:
    corpus = load_corpus()
    index = BM25Index([tokenize(chunk.text) for chunk in corpus])
    ids = [chunk.id for chunk in corpus]
    recalls, rrs = [], []
    for case in _load("retrieval_cases.json"):
        scores = index.scores(tokenize(case["query"]))
        ranked_pairs = sorted(zip(ids, scores, strict=True), key=lambda p: p[1], reverse=True)
        ranked = [chunk_id for chunk_id, _ in ranked_pairs]
        relevant = set(case["relevant"])
        recalls.append(metrics.recall_at_k(ranked, relevant, RECALL_K))
        rrs.append(metrics.reciprocal_rank(ranked, relevant))
    return metrics.mean(recalls), metrics.mean(rrs)


def run_safety() -> float:
    supplements, rules = load_catalog()
    by_id = {s.id: s for s in supplements}
    cases = _load("safety_cases.json")
    passed = 0
    for case in cases:
        user = UserInput(meds=case.get("meds", []), conditions=case.get("conditions", []))
        result = safety.evaluate(user, by_id[case["supplement"]], rules, to_drug_classes(user.meds))
        passed += int(result.status == case["expected"])
    return passed / len(cases) if cases else 1.0


def run_faithfulness() -> tuple[float, int]:
    supplements, rules = load_catalog()
    coverages: list[float] = []
    hallucinations = 0
    for supp in supplements:
        result = safety.evaluate(UserInput(), supp, rules, set())
        ev = retrieve(supp)
        text = explain._render_template(supp, result, ev)
        facts = [item.claim for item in ev] + [reason.message for reason in result.reasons]
        coverages.append(metrics.coverage(text, facts))
        hallucinations += len(metrics.hallucinated_numbers(text, " ".join(facts)))
    return metrics.mean(coverages), hallucinations


def _count_violations(text: str) -> int:
    lowered = text.lower()
    return sum(1 for phrase in PROHIBITED_PHRASES if phrase in lowered)


def run_language_safety() -> int:
    """Scan every generated explanation and rendered content page for definitive claims."""
    supplements, rules = load_catalog()
    violations = 0

    profiles = [
        UserInput(),
        UserInput(meds=["lorazepam", "warfarin"], current_supplements=["melatonin"]),
        UserInput(conditions=["pregnancy", "kidney_disease"]),
    ]
    for user in profiles:
        response = recommend(user, supplements, rules)
        for rec in [*response.recommended, *response.not_recommended]:
            violations += _count_violations(rec.explanation)
        violations += 0 if "not medical advice" in response.disclaimer.lower() else 1

    corpus = load_corpus()
    for supplement in supplements:
        chunks = [c for c in corpus if c.supplement_id == supplement.id]
        violations += _count_violations(pages.render_supplement(supplement, chunks, rules).body)
    by_id = {s.id: s for s in supplements}
    seen: set[str] = set()
    for rule in rules:
        slug = pages.interaction_slug(rule)
        if slug in seen:
            continue
        seen.add(slug)
        violations += _count_violations(
            pages.render_interaction(rule, by_id[rule.supplement_id]).body
        )
    return violations


def main() -> int:
    recall, mrr = run_retrieval()
    safety_pass = run_safety()
    cov, halluc = run_faithfulness()
    claims = run_language_safety()

    rows = [
        ("Retrieval recall@3", recall, THRESHOLDS["recall@3"], recall >= THRESHOLDS["recall@3"]),
        ("Retrieval MRR", mrr, THRESHOLDS["mrr"], mrr >= THRESHOLDS["mrr"]),
        (
            "Safety rule accuracy",
            safety_pass,
            THRESHOLDS["safety"],
            safety_pass >= THRESHOLDS["safety"],
        ),
        ("Explanation coverage", cov, THRESHOLDS["coverage"], cov >= THRESHOLDS["coverage"]),
        (
            "Hallucinated numbers",
            halluc,
            THRESHOLDS["hallucinations"],
            halluc <= THRESHOLDS["hallucinations"],
        ),
        (
            "Definitive-claim phrases",
            claims,
            THRESHOLDS["definitive_claims"],
            claims <= THRESHOLDS["definitive_claims"],
        ),
    ]

    print("\nSleepWise evaluation scorecard")
    print("-" * 56)
    ok = True
    for name, value, threshold, passed in rows:
        ok = ok and passed
        shown = f"{value:.3f}" if isinstance(value, float) else str(value)
        print(f"{name:<22} {shown:>8}   target {threshold:<5} [{'PASS' if passed else 'FAIL'}]")
    print("-" * 56)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
