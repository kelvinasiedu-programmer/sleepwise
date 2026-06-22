# SleepWise

[![CI](https://github.com/<your-username>/sleepwise/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-username>/sleepwise/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A safety-first supplement guidance engine for sleep.** You enter your goal, your
current medications, and a few health flags; SleepWise returns evidence-backed
sleep supplements with doses, citations, **interaction warnings checked by a
deterministic rule engine**, and a clear "talk to a professional" signal when it
matters.

> ⚠️ **Not medical advice.** SleepWise surfaces general information from public
> NIH/FDA databases. It is not a diagnosis and not a substitute for a doctor or
> pharmacist. See [Safety & limitations](#safety--limitations).

---

## Why this project is interesting (the engineering, not the supplements)

Most "AI health" demos let a language model free-associate medical claims. That is
exactly how you hurt someone. SleepWise is built the opposite way:

- **Safety is deterministic, not generative.** Whether two things can be combined
  is decided by a hand-verified rule engine ([`app/safety.py`](app/safety.py)) —
  *before* any model runs. The LLM is only allowed to *explain* the vetted output,
  never to invent or override it.
- **Every claim is grounded and cited.** Doses and evidence come from the NIH
  Office of Dietary Supplements and MedlinePlus, carried through to the response.
- **It fails safe.** Unknown med? Pregnancy flag? Prescription sedative? The engine
  escalates to a warning or a hard block and routes you to a clinician.

This is a small, honest slice of a real problem — and the design choices are
written up in [`DECISIONS.md`](DECISIONS.md).

## Architecture

```
your input ─► normalize meds (RxNorm) ─► DETERMINISTIC SAFETY LAYER ─► evidence (RAG-ready) ─► LLM explanation ─► result
                                          ALLOW / WARN / BLOCK
                                          (runs first, no model)
                 curated knowledge base (doses + hand-verified interaction rules) feeds the safety + evidence steps
```

The safety layer is the gate: it can block a suggestion before the model ever
speaks. See the [request flow](#request-flow) diagram in `DECISIONS.md`.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic | Typed request/response, automatic docs at `/docs` |
| Safety | Pure-Python rule engine | Deterministic, unit-testable, no model in the loop |
| Data | Curated JSON from NIH ODS / DSLD / MedlinePlus | Authoritative, citable |
| Med normalization | NIH RxNorm (with offline fallback) | Reliable name → drug-class matching |
| Explanation | Structured-output LLM (templated fallback) | Friendly prose, citation-locked |

## Data sources

- [NIH Office of Dietary Supplements – Fact Sheets API](https://ods.od.nih.gov/api/)
- [Dietary Supplement Label Database (DSLD) API](https://dsld.od.nih.gov/api-guide)
- [MedlinePlus Herbs & Supplements](https://medlineplus.gov/druginfo/herb_All.html)
- [openFDA Drug Label API](https://open.fda.gov/apis/drug/label/)
- [NIH RxNorm (RxNav)](https://rxnav.nlm.nih.gov/)

## Quickstart

```bash
# 1. clone, then from the repo root:
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# 2. run the tests (the safety rules are covered)
pytest -q

# 3. start the API + minimal UI
uvicorn app.main:app --reload
# open http://127.0.0.1:8000  (UI)  or  http://127.0.0.1:8000/docs  (API)
```

### Example request

```bash
curl -X POST http://127.0.0.1:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"meds": ["lorazepam"], "conditions": []}'
```

Valerian comes back in `not_recommended` (BLOCK: additive CNS depression with a
benzodiazepine) with no purchase link, while safe options are returned with cited
rationale.

## Testing

`pytest` covers the rules that matter most — the dangerous pairs:

- valerian + benzodiazepine → **BLOCK**
- melatonin + anticoagulant → **WARN**
- magnesium + quinolone antibiotic → **WARN**
- ashwagandha in pregnancy → **BLOCK**
- clean profile → **ALLOW**

If a future change ever lets a known-dangerous pair through, a test fails.

## Safety & limitations

- This is an **educational tool**, not a clinician. It never diagnoses or prescribes.
- The interaction table is **hand-curated for six sleep supplements** against common
  drug classes. It is intentionally narrow and is **not** a complete interaction
  database. Absence of a warning is **not** proof of safety.
- Data entries are tagged with `verified`; unverified rows must be checked against
  their cited source before any real-world use.
- No personal health data is stored — requests are stateless by design.

## Roadmap

- [ ] Swap the evidence step for true RAG (embeddings over the full ODS + MedlinePlus corpus)
- [ ] Live RxNorm/RxClass drug-class resolution with caching
- [ ] Expand beyond sleep (one goal module at a time)
- [ ] Affiliate links with FTC-compliant disclosure

## License

MIT © Kelvin Asiedu
