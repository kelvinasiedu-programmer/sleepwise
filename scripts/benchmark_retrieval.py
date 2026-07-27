"""Benchmark retrieval backends: BM25 vs a local embedding model.

    python scripts/benchmark_retrieval.py

Answers a question the project could previously only assert: is the from-scratch BM25
retriever good enough, or is the deployed app leaving quality on the table by not using
embeddings?

Design notes:

* Queries are split into `lexical` (share vocabulary with the target chunk) and
  `paraphrase` (deliberately do not). Reporting one aggregate number would hide the
  difference that matters, because lexical overlap is exactly what BM25 is good at.
* The embedding backend runs **locally** - no API key, no per-run cost, and anyone who
  clones the repo can reproduce these numbers. A result nobody else can verify is not
  much of a result.
* This is a dev-time script, not part of CI. The deployed service keeps zero-dependency
  BM25; pulling a transformer stack into a 512 MB free-tier container to serve twenty
  documents would be a poor trade.

Requires: pip install -r requirements-bench.txt
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.retrieval import BM25Index, CorpusChunk, load_corpus, tokenize  # noqa: E402
from evals.metrics import mean, recall_at_k, reciprocal_rank  # noqa: E402

CASES_PATH = ROOT / "evals" / "datasets" / "retrieval_benchmark.json"
OUT_PATH = ROOT / "docs" / "RETRIEVAL_BENCHMARK.md"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
K = 3


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rank_bm25(corpus: list[CorpusChunk], queries: list[str]) -> list[list[str]]:
    index = BM25Index([tokenize(c.text) for c in corpus])
    ids = [c.id for c in corpus]
    ranked = []
    for query in queries:
        scores = index.scores(tokenize(query))
        order = sorted(zip(ids, scores, strict=True), key=lambda p: p[1], reverse=True)
        ranked.append([cid for cid, _ in order])
    return ranked


def rank_embeddings(corpus: list[CorpusChunk], queries: list[str]) -> list[list[str]] | None:
    """Rank by cosine similarity using a local sentence-transformer.

    Returns None (rather than exploding) when the optional dependency is absent, so the
    script still reports the BM25 half on a machine that has not installed it.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None

    model = SentenceTransformer(EMBED_MODEL)
    doc_vectors = model.encode([c.text for c in corpus]).tolist()
    query_vectors = model.encode(queries).tolist()
    ids = [c.id for c in corpus]

    ranked = []
    for qv in query_vectors:
        scored = [(cid, _cosine(qv, dv)) for cid, dv in zip(ids, doc_vectors, strict=True)]
        scored.sort(key=lambda p: p[1], reverse=True)
        ranked.append([cid for cid, _ in scored])
    return ranked


def score(ranked: list[list[str]], cases: list[dict]) -> dict[str, dict[str, float]]:
    """recall@K and MRR overall and per query type."""
    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for order, case in zip(ranked, cases, strict=True):
        relevant = set(case["relevant"])
        pair = (recall_at_k(order, relevant, K), reciprocal_rank(order, relevant))
        buckets[case["type"]].append(pair)
        buckets["all"].append(pair)
    return {
        name: {
            f"recall@{K}": mean([r for r, _ in pairs]),
            "mrr": mean([m for _, m in pairs]),
            "n": len(pairs),
        }
        for name, pairs in buckets.items()
    }


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    corpus = load_corpus()
    queries = [c["query"] for c in cases]
    print(f"{len(cases)} queries over {len(corpus)} chunks\n")

    results = {"BM25 (deployed)": score(rank_bm25(corpus, queries), cases)}

    print(f"Loading {EMBED_MODEL} (first run downloads ~90 MB)...")
    embedded = rank_embeddings(corpus, queries)
    if embedded is None:
        print("sentence-transformers not installed; reporting BM25 only.")
        print("  pip install -r requirements-bench.txt")
    else:
        results["MiniLM embeddings"] = score(embedded, cases)

    groups = ["all", "lexical", "paraphrase"]
    header = f"| Backend | {' | '.join(f'{g} recall@{K} / MRR' for g in groups)} |"
    sep = "|---" * (len(groups) + 1) + "|"
    rows = []
    for backend, scores in results.items():
        cells = []
        for g in groups:
            s = scores.get(g)
            cells.append(f"{s[f'recall@{K}']:.2f} / {s['mrr']:.2f}" if s else "-")
        rows.append(f"| {backend} | {' | '.join(cells)} |")

    table = "\n".join([header, sep, *rows])
    print("\n" + table + "\n")

    counts = {g: results[next(iter(results))].get(g, {}).get("n", 0) for g in groups}
    OUT_PATH.write_text(
        "# Retrieval benchmark: BM25 vs local embeddings\n\n"
        "<!-- Generated by scripts/benchmark_retrieval.py. Do not edit by hand; "
        "re-run the script instead. -->\n\n"
        f"{len(cases)} queries over {len(corpus)} chunks, k={K}. "
        f"Query mix: {counts['lexical']} lexical, {counts['paraphrase']} paraphrase.\n\n"
        "```bash\n"
        "pip install -r requirements-bench.txt\n"
        "python scripts/benchmark_retrieval.py\n"
        "```\n\n"
        f"{table}\n\n"
        "**lexical** queries share vocabulary with the target chunk; **paraphrase**\n"
        "queries deliberately do not. The split matters because lexical overlap is\n"
        "precisely what BM25 is built to exploit, so a single aggregate number would\n"
        "flatter it.\n\n"
        "Embeddings run locally via sentence-transformers, so these numbers are\n"
        "reproducible without an API key. The deployed service still uses BM25: see\n"
        "the interpretation in DECISIONS.md.\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"written to {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
