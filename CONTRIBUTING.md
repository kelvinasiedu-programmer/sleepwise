# Contributing to SleepWise

Thanks for taking a look. This project has one non-negotiable rule; everything else is
ordinary Python.

## The safety invariant (read this first)

**A language model must never decide whether something is safe.** Every
ALLOW / WARN / BLOCK decision lives in `app/safety.py` and runs *before* any model. The
explanation layer (`app/explain.py`) may only restate already-vetted output and must
cite its sources. Any change that lets a model introduce or override a safety decision
will be rejected.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install      # optional: run ruff on every commit
pytest                  # tests + coverage
uvicorn app.main:app --reload
```

## Project layout

| Path | Responsibility |
|---|---|
| `app/safety.py` | Deterministic rule engine (the heart) |
| `app/normalize.py` | Medication name → drug class |
| `app/recommend.py` | Orchestration (input → safety → evidence → explanation) |
| `app/explain.py` | Explanation layer, citation-locked |
| `app/models.py` | Pydantic data contracts |
| `data/*.json` | Curated supplements + interaction rules |
| `tests/` | Rule-engine, normalize, explain, and HTTP tests |

## Adding a supplement

1. Add an entry to `data/supplements.json`: `id`, `name`, dose range, `unit`, `summary`,
   and at least one `evidence` item with a real `source_url`.
2. Set `verified: true` only after you have personally confirmed each claim against its
   cited source.

## Adding an interaction rule

1. Add a row to `data/interaction_rules.json`: `supplement_id`, `target_type`
   (`drug_class` | `condition` | `supplement`), `target`, `severity`, `message`, `source_url`.
2. If `target` is a drug class new to the project, map the relevant drug names to it in
   `app/normalize.py` (`LOCAL_DRUG_CLASSES`).
3. **Add a test** in `tests/test_safety.py` for the dangerous pair. A new BLOCK/WARN rule
   without a test will not be accepted — the test is how we stop a future change from
   silently re-allowing it.

## Before opening a PR

All of these run in CI and must pass:

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy app                # types (zero issues)
pytest --cov-fail-under=90   # tests + coverage gate
```

Also confirm: new data carries a real `source_url`, the `verified` flag is honest, and
no safety decision moved into the model layer.
