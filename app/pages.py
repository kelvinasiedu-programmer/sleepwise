"""Server-rendered content pages (supplement and interaction guides).

These are generated from the same curated, sourced data the checker uses
(data/supplements.json, data/interaction_rules.json, data/evidence_corpus.json), so the
wording stays cautious and every claim keeps its citation. They exist mainly for search
discovery and to route readers into the checker. No free-form medical claims are written
here - everything comes from the vetted data.
"""

from __future__ import annotations

import json
from html import escape

from .models import InteractionRule, Supplement
from .retrieval import CorpusChunk

# When the content was last checked against its cited sources. Shown on every content
# page and carried into the MedicalWebPage schema. There is no clinician "reviewedBy"
# on purpose: no clinician has reviewed this yet, and the schema must not claim one.
LAST_REVIEWED = "2026-06-24"

DRUG_CLASS_TERMS = {
    "benzodiazepine": "benzodiazepines (e.g. lorazepam, Xanax)",
    "anticoagulant": "blood thinners (anticoagulants such as warfarin)",
    "antiplatelet": "antiplatelet medicines (e.g. aspirin, clopidogrel)",
    "sedative_hypnotic": "sedative sleep medicines (e.g. zolpidem)",
    "opioid": "opioid pain medicines",
    "antihypertensive": "blood-pressure medicines",
    "antidiabetic": "diabetes medicines",
    "ssri": "SSRI antidepressants",
    "quinolone_antibiotic": "quinolone antibiotics (e.g. ciprofloxacin)",
    "tetracycline_antibiotic": "tetracycline antibiotics (e.g. doxycycline)",
    "immunosuppressant": "immunosuppressant medicines",
    "bisphosphonate": "bisphosphonates (bone medicines)",
    "thyroid_hormone": "thyroid medication (e.g. levothyroxine)",
    "antipsychotic_clozapine": "clozapine",
}
CONDITION_TERMS = {
    "pregnancy": "pregnancy",
    "breastfeeding": "breastfeeding",
    "kidney_disease": "kidney disease",
    "under_18": "being under 18",
}

_NAV = (
    '<nav class="site-nav" aria-label="Primary">'
    '<a href="/">Checker</a><a href="/supplements">Supplements</a>'
    '<a href="/interactions">Interactions</a><a href="/methodology">Methodology</a>'
    '<a href="/about">About</a></nav>'
)
_FOOTER = (
    '<footer class="site-footer"><p>Educational tool · not medical advice · '
    'data from NIH ODS, MedlinePlus &amp; openFDA.</p><nav aria-label="Footer">'
    '<a href="/about">About</a> · <a href="/methodology">Methodology</a> · '
    '<a href="/sources">Sources</a> · <a href="/supplements">Supplements</a> · '
    '<a href="/interactions">Interactions</a> · '
    '<a href="/editorial-policy">Editorial policy</a> · <a href="/privacy">Privacy</a> · '
    '<a href="/medical-disclaimer">Medical disclaimer</a> · <a href="/contact">Contact</a>'
    "</nav></footer>"
)

_PROVENANCE = (
    '<p class="updated">Compiled from the cited public medical sources · '
    "last source-reviewed June 2026 · not yet independently reviewed by a clinician "
    '(<a href="/editorial-policy">editorial policy</a>)</p>'
)
_DISCLAIMER = (
    '<p class="disclaimer">Educational information from public NIH/FDA databases - '
    "<strong>not medical advice</strong>. Always talk to a doctor or pharmacist before "
    "starting, stopping, or combining any supplement or medication.</p>"
)


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def humanize_target(rule: InteractionRule) -> str:
    if rule.target_type == "drug_class":
        return DRUG_CLASS_TERMS.get(rule.target, rule.target.replace("_", " "))
    if rule.target_type == "condition":
        return CONDITION_TERMS.get(rule.target, rule.target.replace("_", " "))
    return rule.target.replace("_", " ")


def interaction_slug(rule: InteractionRule) -> str:
    return f"{rule.supplement_id}-and-{rule.target}".replace("_", "-")


def _shell(title: str, description: str, canonical: str, body: str, head_extra: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        f"<title>{escape(title)}</title>"
        f'<meta name="description" content="{escape(description)}"/>'
        f'<link rel="canonical" href="{escape(canonical)}"/>'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml"/>'
        '<meta name="theme-color" content="#534ab7"/>'
        f'<link rel="stylesheet" href="/site.css?v=3"/>{head_extra}</head><body>'
        '<a class="skip-link" href="#main">Skip to main content</a>'
        '<header class="site-header"><a class="brand" href="/">SleepWise</a>'
        f'{_NAV}</header><main id="main" class="wrap prose">{body}{_DISCLAIMER}</main>{_FOOTER}'
        "</body></html>"
    )


def _jsonld(payload: dict) -> str:
    return f'<script type="application/ld+json">{json.dumps(payload)}</script>'


def _supplement_schema(supplement: Supplement, chunks: list[CorpusChunk], canonical: str) -> str:
    """MedicalWebPage + DietarySupplement markup with truthful fields only.

    Deliberately absent: reviewedBy / medical credentials, and recommendedIntake -
    machine-readable dose guidance stays out of structured data until the dataset has
    independent clinical review. Adding either without a real reviewer would be
    fabricated structured data.
    """
    return _jsonld(
        {
            "@context": "https://schema.org",
            "@type": "MedicalWebPage",
            "name": f"{supplement.name} for sleep: evidence, dose, and interactions",
            "url": canonical,
            "lastReviewed": LAST_REVIEWED,
            "about": {
                "@type": "DietarySupplement",
                "name": supplement.name,
            },
            "citation": sorted({c.source_url for c in chunks}),
            "publisher": {"@type": "Organization", "name": "SleepWise"},
        }
    )


def _interaction_schema(title: str, rule: InteractionRule, canonical: str) -> str:
    return _jsonld(
        {
            "@context": "https://schema.org",
            "@type": "MedicalWebPage",
            "name": f"{title}: what to know",
            "url": canonical,
            "lastReviewed": LAST_REVIEWED,
            "citation": [rule.source_url],
            "publisher": {"@type": "Organization", "name": "SleepWise"},
        }
    )


def render_supplement_index(supplements: list[Supplement], canonical: str) -> str:
    items = "".join(
        f'<li><a href="/supplements/{escape(s.id)}">{escape(s.name)}</a> - {escape(s.summary)}</li>'
        for s in supplements
    )
    body = (
        "<h1>Sleep supplements</h1>"
        "<p>Plain-language, source-linked guides to common sleep supplements. Each page covers "
        "what the evidence says, typical doses, and interaction concerns. Educational only.</p>"
        f"<ul>{items}</ul>"
        '<p><a href="/">Check these against your medications and health flags.</a></p>'
    )
    return _shell(
        "Sleep supplements: evidence, doses, and interactions | SleepWise",
        "Source-linked guides to melatonin, magnesium, L-theanine, glycine, valerian, and "
        "ashwagandha for sleep.",
        canonical,
        body,
    )


def render_supplement(
    supplement: Supplement,
    chunks: list[CorpusChunk],
    rules: list[InteractionRule],
    canonical: str,
) -> str:
    evidence = "".join(
        f'<li>{escape(c.text)} <a href="{escape(c.source_url)}">{escape(c.source)}</a></li>'
        for c in chunks
    )
    supp_rules = [r for r in rules if r.supplement_id == supplement.id]
    interactions = ""
    if supp_rules:
        rows = "".join(
            f"<li><strong>{escape(humanize_target(r))}:</strong> {escape(r.message)} "
            f'(<a href="/interactions/{escape(interaction_slug(r))}">details</a>)</li>'
            for r in supp_rules
        )
        interactions = f"<h2>Interaction concerns</h2><ul>{rows}</ul>"
    dose = f"{_fmt(supplement.dose_low)}-{_fmt(supplement.dose_high)} {escape(supplement.unit)}"
    timing = f" ({escape(supplement.timing)})" if supplement.timing else ""
    body = (
        f"<h1>{escape(supplement.name)} for sleep</h1>"
        f"{_PROVENANCE}"
        f"<p>{escape(supplement.summary)}</p>"
        f"<h2>What the evidence says</h2><ul>{evidence}</ul>"
        f"<h2>Typical dose</h2><p>{dose}{timing}. Evidence grade: "
        f"{escape(supplement.evidence_grade)}. This is a general range, not a personal "
        "recommendation.</p>"
        f"{interactions}"
        "<h2>Questions to ask a pharmacist</h2><ul>"
        f"<li>Is {escape(supplement.name)} reasonable to try with my current medications?</li>"
        "<li>Could it add to drowsiness or affect anything I already take?</li>"
        "<li>What dose and timing would you suggest for me?</li></ul>"
        f'<p><a href="/">Check {escape(supplement.name)} against your full profile.</a></p>'
    )
    return _shell(
        f"{supplement.name} for sleep: evidence, dose, and interactions | SleepWise",
        f"{supplement.name} for sleep: what the evidence says, typical doses, and interaction "
        "concerns, from public medical sources.",
        canonical,
        body,
        head_extra=_supplement_schema(supplement, chunks, canonical),
    )


def render_interaction_index(entries: list[tuple[str, str]], canonical: str) -> str:
    items = "".join(
        f'<li><a href="/interactions/{escape(slug)}">{escape(title)}</a></li>'
        for slug, title in entries
    )
    body = (
        "<h1>Sleep supplement interactions</h1>"
        "<p>Plain-language guides to common sleep-supplement and medication or health-flag "
        "combinations. None of these call a combination safe; they explain what to check and "
        "what to ask a clinician.</p>"
        f"<ul>{items}</ul>"
        '<p><a href="/">Check your own combination.</a></p>'
    )
    return _shell(
        "Sleep supplement interactions | SleepWise",
        "Guides to common sleep-supplement interactions with medications and health flags, "
        "from public medical sources.",
        canonical,
        body,
    )


def render_interaction(rule: InteractionRule, supplement: Supplement, canonical: str) -> str:
    target = humanize_target(rule)
    if rule.severity == "BLOCK":
        answer = (
            f"Combining {supplement.name} with {target} is something to clear with a clinician "
            "or pharmacist before you try it."
        )
    else:
        answer = (
            f"Combining {supplement.name} with {target} may call for caution. It is not "
            "automatically unsafe, but it is worth checking before you combine them."
        )
    title = f"{supplement.name} and {target}"
    body = (
        f"<h1>{escape(supplement.name)} and {escape(target)}</h1>"
        f"{_PROVENANCE}"
        f"<p>{escape(answer)}</p>"
        "<h2>Why it may matter</h2>"
        f'<p>{escape(rule.message)} <a href="{escape(rule.source_url)}">Source</a>.</p>'
        "<h2>What to ask a pharmacist</h2><ul>"
        f"<li>Given my medicines, is {escape(supplement.name)} a reasonable option for me?</li>"
        "<li>If not, is there a safer alternative for sleep?</li>"
        "<li>What signs should make me stop and seek advice?</li></ul>"
        f'<p><a href="/">Check {escape(supplement.name)} against your full medication list.</a></p>'
    )
    return _shell(
        f"{title}: what to know | SleepWise",
        f"{title}: why the combination may matter and what to ask a pharmacist, from public "
        "medical sources.",
        canonical,
        body,
        head_extra=_interaction_schema(title, rule, canonical),
    )
