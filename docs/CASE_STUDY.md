# Building SleepWise: making an AI health tool that won't hurt anyone

Most "AI for health" demos work like this: take a user's question, hand it to a language
model, and print whatever comes back. That is fine for a toy. It is dangerous the moment
the answer touches medication. A model that confidently tells someone their sleep
supplement is safe to take with their blood thinner - when it isn't - has done real harm,
and "the model said it, not me" is not a defense I wanted to rely on.

SleepWise is my attempt to build the opposite: a tool for the sleep domain where the
language model is never the thing deciding what is safe.

## The one rule everything else follows

**Safety is decided by deterministic code, before any model runs.** Whether two things can
be combined is answered by a plain Python rule engine reading a curated interaction table.
The model's only job is to rewrite the facts that engine already approved into friendlier
prose - and it is given nothing else to work with. If a medication maps to a drug class
that conflicts with a supplement, the engine flags it, full stop. No amount of clever
prompting can talk it out of that.

This isn't only an ethics decision. It is also what makes the thing testable. You cannot
unit-test a vibe. You can absolutely unit-test "valerian plus a benzodiazepine is
withheld," and that test fails loudly if anyone ever weakens it.

## Two engines, same principle

**The interaction checker** maps medications to drug classes, evaluates them against the
rule table, applies global hard gates, and checks additive sedation against what the
person already takes.

**The symptom organizer** turns fixed cards into unranked topics to raise with a
clinician. It never ranks, scores, or gives a likelihood; never asserts or excludes a
condition; and evaluates red flags *before* topics, because someone who is falling asleep
at the wheel needs escalation, not a tidy list. "Not sure" deliberately does not count as
a match - hesitation should not manufacture a topic.

Building the second engine was the moment the architecture proved it wasn't a one-off: the
same pattern (fixed data, deterministic rules, no model near a safety call, tests that
encode the requirement) transferred to a completely different problem shape.

## Getting audited, and what it found

I had the project reviewed by a hostile external reviewer with instructions to verify
everything against the live service rather than take my word for it. It found four real
safety defects. I want to name them, because the fixes are the most interesting part:

1. **Two medications typed into one field resolved to the first match.** Entering
   "warfarin lorazepam" silently discarded lorazepam and returned a confident personalized
   result that missed a benzodiazepine interaction entirely. This is the exact failure
   mode I had spent the whole project trying to prevent, and I had shipped it anyway. The
   matcher now returns every match and refuses to guess when more than one drug class is
   present.
2. **Kidney disease wasn't a hard gate**, only a rule on one supplement, so everything
   else came back clean.
3. **The "supplements you already take" field was accepted and then ignored**, so unknown
   entries still produced personalized output.
4. **Sedation stacking was computed across the candidate options** rather than the user's
   actual stack, inventing warnings unrelated to their situation.

It also checked my citations properly and found that only about 12 of 27 sampled claims
were directly supported by the page they cited. A link is not substantiation.

## What I changed, and one thing I refused to

Everything above is fixed, each with a regression test. Two responses are worth
explaining:

**Unconfirmed claims are now withheld.** Every claim records whether it was confirmed
against its source. Unconfirmed ones are not rendered and never enter the structured data.
Three supplements ended up with no displayable evidence at all - so their cards say that,
rather than filling the space with something I can't stand behind.

**But unconfirmed *warnings* still show, labelled.** The reviewer's rule was "don't publish
unverified claims." Applied to a safety warning, that would have deleted valerian +
opioids and melatonin + benzodiazepines - removing protection from exactly the person at
risk, to reduce my citation exposure. That trade runs the wrong way. Warnings are labelled
precautionary, not hidden.

I also removed commerce from the product entirely. A buying prompt does not belong next to
guidance that no clinician has validated.

## Knowing what not to ship

The honest limit of this project is that the data needs a licensed pharmacist, and I don't
have one. So rather than pretend otherwise - or fabricate a reviewer byline, which would
have been trivial and is exactly the kind of fake credential that makes health content
untrustworthy - I did two things.

I prepared a [clinical review packet](CLINICAL_REVIEW_PACKET.md) that sorts every rule by
how doubtful its citation is, so a pharmacist can spend twenty useful minutes on it and
sign off only on what they actually reviewed.

And I made the product structurally a demonstration. The checker takes no free-text health
input at all; it runs fixed scenarios. Nobody can look up their own medications, so there
is nothing to clinically validate. That is a real constraint enforced by the code, not a
disclaimer asking to be trusted.

## How I keep myself honest

An evaluation harness scores retrieval (recall@k, MRR), safety-rule accuracy, and
explanation faithfulness - including a check that no invented dose or definitive-claim
phrasing ever reaches output. It fails CI on regression. On top of that: linting, type
checking, tests across four Python versions with a coverage floor, dependency auditing,
CodeQL, and a weekly citation-reachability check.

The tests encode requirements, not implementation. A purchase link appearing anywhere
fails the build. So does the organizer emitting a percentage.

## What I took away from it

The interesting engineering here wasn't the AI. It was deciding what the AI is *not
allowed to do*, and building the boring deterministic scaffolding around it so the smart
part can't cause harm.

The harder lesson came from the audit. I had written extensively about failing closed, and
still shipped a bug that silently dropped a medication. Believing you have built something
safe is not the same as verifying it, and the only reason I found out was that I asked
someone to try to break it and did not argue with the answer.
