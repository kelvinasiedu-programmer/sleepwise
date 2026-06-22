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
× common drug classes, sourced from NIH ODS / MedlinePlus / openFDA labels — rather
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
secrets — reviewers can clone and run it immediately.

## 5. Stateless — no health data stored

**Decision:** Requests carry meds/conditions as input and nothing is persisted.

**Why:** Storing health information triggers real privacy obligations (FTC Health
Breach Notification Rule, and HIPAA-adjacent expectations). The cheapest way to be
safe is to not hold the data at all in v1.

## 6. Scope: one goal (sleep), six supplements

**Decision:** Lock v1 to sleep and a fixed shortlist.

**Why:** A narrow, well-evidenced domain is verifiable and shippable in a week. Breadth
is a roadmap item, not a v1 requirement.

## Request flow

```
1. Your input            goal=sleep, meds[], conditions[]
2. Normalize meds        RxNorm (+ local fallback) -> drug classes
3. SAFETY LAYER          rule engine -> ALLOW / WARN / BLOCK   <-- deterministic, runs first
4. Evidence retrieval    curated, cited (RAG-ready interface)
5. LLM explanation       structured output, cite-only
6. Result                recommendations, risks, defer-to-pro, buy links
```

## Testing strategy

The tests encode the *requirements*, not just the code: known-dangerous pairs must be
caught. If a refactor ever lets valerian + a benzodiazepine through as ALLOW, the suite
goes red. That is the point.
