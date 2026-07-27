# Engineering decisions

This file records *why* SleepWise is built the way it is. The reasoning matters more
than the code.

## 1. Safety is deterministic, the LLM is not in the loop

**Decision:** A pure-Python rule engine (`app/safety.py`) decides ALLOW / WARN / BLOCK
for every supplement, and it runs *before* any language model. The LLM may only
restate the engine's output and the cited evidence.

**Why:** In a health context, a hallucinated "these are safe together" can cause real
harm. The only defensible design is for safety-critical logic to be deterministic,
inspectable, and unit-tested. The model is a presentation layer, not a decision maker.

**Consequence:** Every safety claim is traceable to a rule with a source URL, and the
rules are covered by tests. There is no path for the model to invent an interaction.

## 2. Hand-curated interaction table instead of a licensed database

**Decision:** Ship a small, hand-verified interaction table for six sleep supplements
× common drug classes, sourced from NIH ODS / MedlinePlus / openFDA labels - rather
than integrating DrugBank or the Natural Medicines Database.

**Why:** The authoritative supplement↔drug interaction databases are commercial and
expensive. For a focused v1, a narrow table I can personally verify is *safer* (I know
every entry) and free. Honesty about coverage beats a false sense of completeness.

**Trade-off:** Coverage is limited and explicitly advertised as such. Each row carries
a `verified` flag; unverified rows are flagged in the UI and README.

## 3. Drug-class matching with graceful offline fallback

**Decision:** Map medication names to drug classes via NIH RxNorm, but keep a small
local lookup so the app and tests run with no network (`app/normalize.py`).

**Why:** External APIs fail, rate-limit, and are slow in tests. Production code should
degrade gracefully rather than break. The local map also makes the safety tests
deterministic.

## 4. Structured output for the explanation layer

**Decision:** The LLM call (when enabled) uses a strict system prompt plus structured
output; with no API key it falls back to a deterministic, citation-locked template.

**Why:** Structured output makes it physically hard for the model to add an
unsupported claim. The template fallback means the project runs out-of-the-box with no
secrets - reviewers can clone and run it immediately.

## 5. Stateless - no health data stored

**Decision:** Requests carry meds/conditions as input and nothing is persisted.

**Why:** Storing health information triggers real privacy obligations (FTC Health
Breach Notification Rule, and HIPAA-adjacent expectations). The cheapest way to be
safe is to not hold the data at all in v1.

## 6. Scope: one goal (sleep), six supplements

**Decision:** Lock v1 to sleep and a fixed shortlist.

**Why:** A narrow, well-evidenced domain is verifiable and shippable in a week. Breadth
is a roadmap item, not a v1 requirement.

## 7. Retrieval: BM25 by default, embeddings optional

**Decision:** Evidence is retrieved by a from-scratch BM25 index over a curated corpus
(`data/evidence_corpus.json`). An embedding backend is available behind
`SLEEPWISE_RETRIEVER=embedding` + `OPENAI_API_KEY`, and `get_retriever` falls back to BM25
on any error.

**Why:** BM25 is real, well-understood retrieval that needs no model, no service, and no
memory budget - so the deployed free-tier app does genuine RAG out of the box. The
embedding path demonstrates the upgrade without forcing a dependency or a key.

**Measured, not assumed.** `scripts/benchmark_retrieval.py` compares both over 24 queries
(full results in [`docs/RETRIEVAL_BENCHMARK.md`](docs/RETRIEVAL_BENCHMARK.md)):

| Backend | all recall@3 / MRR | lexical | paraphrase |
|---|---|---|---|
| BM25 | 0.75 / 0.74 | 1.00 / 1.00 | 0.50 / 0.47 |
| MiniLM embeddings | 0.94 / 0.93 | 1.00 / 1.00 | 0.88 / 0.85 |

BM25 is perfect on queries that share vocabulary with the target and roughly a coin flip
on paraphrases; embeddings match it on the former and nearly double it on the latter.

**Why that does not change the default.** The app never passes a user's own words to the
retriever. The query is assembled from the supplement name and fixed terms
(`"sleep melatonin benefits dose risks interactions"`), and retrieval is then filtered to
that supplement's own chunks - which is the lexical, small-candidate-set case where BM25
scores 1.00. Adding a transformer stack to a 512 MB container to serve twenty documents
would cost startup time, memory, and reproducibility for no measured gain *on the queries
this system actually issues*.

**What would change it.** Free-text user questions. The paraphrase column is a direct
measure of what BM25 would cost the moment someone types "will it leave me groggy"
instead of "melatonin side effects drowsiness" - and at that point the embedding backend
already exists behind a flag. The benchmark is the trigger condition, written down.

## 8. The LLM writes prose only - never safety

**Decision:** When `ANTHROPIC_API_KEY` is set, an LLM rewrites the *already-vetted* facts
into friendlier prose. The authoritative ALLOW/WARN/BLOCK status and the structured
`warnings` list come from the rule engine and are returned separately; the model output
only fills the human-readable `explanation` string. With no key, the deterministic
template is used.

**Why:** This keeps the safety invariant intact even with generation enabled - the UI
shows engine-produced warnings regardless of what the prose says - while still letting the
app benefit from an LLM when one is available.

## 9. Cautious language is enforced, not promised

**Decision:** The eval harness scans every generated explanation and every rendered
content page for definitive-claim phrasing ("is safe", "guaranteed", "will cure", and
similar) and fails CI on any hit. Every result carries the disclaimer, and the
professional-help path is shown with every result: free walk-in pharmacist consultations,
plus the HHS health-center finder for people without a regular clinician.

**Why:** In a health tool, "we use careful wording" is worthless as a promise unless a
machine checks it. Encoding the banned-claims list as a failing test makes cautious
wording a tested property of the system, the same way the dangerous-pair rules are.

## Request flow

```
1. Your input            goal=sleep, meds[], conditions[]
2. Normalize meds        RxNorm (+ local fallback) -> drug classes
3. SAFETY LAYER          rule engine -> ALLOW / WARN / BLOCK   <-- deterministic, runs first
4. Evidence retrieval    BM25 RAG over the evidence corpus (embeddings optional)
5. LLM explanation       optional; cite-only, deterministic template fallback
6. Result                recommendations, risks, defer-to-pro, buy links
```

## Testing strategy

The tests encode the *requirements*, not just the code: known-dangerous pairs must be
caught. If a refactor ever lets valerian + a benzodiazepine through as ALLOW, the suite
goes red. That is the point.
