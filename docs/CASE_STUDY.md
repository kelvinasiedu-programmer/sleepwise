# Building SleepWise: making an AI health tool that won't hurt anyone

Most "AI for health" demos work like this: take a user's question, hand it to a language
model, and print whatever comes back. That is fine for a toy. It is dangerous the moment
the answer touches medication. A model that confidently tells someone their sleep
supplement is safe to take with their blood thinner — when it isn't — has done real harm,
and "the model said it, not me" is not a defense I wanted to rely on.

SleepWise is my attempt to build the opposite: a supplement-guidance tool for sleep where
the language model is never the thing deciding what is safe.

## The one rule everything else follows

A user enters their goal (sleep), their current medications, and a few health flags. They
get back a short list of evidence-backed supplements, each with doses, citations,
interaction warnings, and a clear "go talk to a professional" signal when it matters.

The rule I held to the whole way through: **safety is decided by deterministic code, before
any model runs.** Whether two things can be combined is answered by a plain Python rule
engine reading a hand-verified interaction table. The model's only job is to rewrite the
facts that engine already approved into friendlier prose — and it is given nothing else to
work with. If a medication maps to a drug class that conflicts with a supplement, the
engine flags it, full stop. No amount of clever prompting can talk it out of that.

This isn't only an ethics decision. It is also what makes the thing testable. You cannot
unit-test a vibe. You can absolutely unit-test "valerian plus a benzodiazepine returns
BLOCK," and that test fails loudly if anyone ever weakens it.

## What it actually does

- **Normalizes medications to drug classes.** A missed match is the scary failure here —
  it shows up as a falsely reassuring "ALLOW" — so the matcher handles brand names
  (Xanax), strips dosages out of free text ("warfarin 5mg"), and does conservative fuzzy
  matching for typos.
- **Runs the deterministic safety engine** per supplement, then a second pass that catches
  additive sedation when you'd be stacking several sedating supplements at once.
- **Retrieves evidence with real RAG.** I wrote a small BM25 index from scratch over a
  curated NIH/MedlinePlus corpus. No vector database, no external service, so it runs on a
  free tier. There's an optional embedding backend if you want semantic search, but BM25 is
  the honest default and it works.
- **Explains, optionally with an LLM.** With no API key it uses a deterministic template.
  With a key, a model rewrites the *already-vetted* facts. Either way the authoritative
  warnings come from the engine and are shown separately.

## How I keep myself honest

The part I'm most happy with is the evaluation harness. It scores three things and fails
CI if any of them regress:

- **Retrieval** — recall@k and MRR against a small labeled set, so I can actually claim the
  retriever surfaces the right evidence instead of hoping it does.
- **Safety** — a battery of profiles with expected ALLOW/WARN/BLOCK outcomes.
- **Faithfulness** — a check that the explanation only contains facts it was given, and that
  it never introduces a dose or number that wasn't in the source. This is the guardrail for
  the LLM path: if a model ever invents "take 50mg," the harness catches it.

On top of that the project runs the usual discipline on every push — linting, type
checking, tests across four Python versions with a coverage floor, and a dependency audit.

## What I'd be the first to tell a reviewer

It's a v1, and I'd rather name the edges than hide them. The interaction table is small and
partly unverified — it needs a pharmacist's eye before anyone leans on it. The medication
matcher is much better than exact-string now, but live RxNorm resolution is still the right
long-term answer. And it only covers sleep; other goals are deliberately out of scope until
the safety story for each is built the same careful way.

## What I took away from it

The interesting engineering here wasn't the AI. It was deciding what the AI is *not allowed
to do*, and building the boring deterministic scaffolding around it so the smart part can't
cause harm. That constraint made the whole system easier to test, easier to reason about,
and easier to trust — which, for anything that touches someone's health, is the only thing
that matters.
