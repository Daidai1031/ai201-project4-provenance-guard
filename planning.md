# TeaGuard Provenance Guard — Planning

This document is written before implementation, per the assignment brief.
It answers the five required questions, then lays out the architecture and
the AI-tool plan for each implementation milestone.

TeaGuard adapts the general "Provenance Guard" brief (attribution +
confidence + transparency label + appeals, for a creative-content platform)
to a more concrete and higher-stakes surface: an anonymous dating-review
platform. In addition to AI-authorship attribution, the system also screens
for privacy risk and defamation risk, because on this kind of platform those
two risks matter at least as much as whether a review was AI-written. All
three are kept as **separate scores** rather than one blended "risk" number
— see Question 1 below for why.

---

## 1. Detection Signals

TeaGuard uses **three** signals (the required minimum is two; this is the
stretch "Ensemble Detection" feature).

| Signal | What it measures | Output shape |
|---|---|---|
| LLM classifier (Groq, `llama-3.3-70b-versatile`) | Semantic judgment: does the text *mean* something identifying or accusatory, and does it *read* as AI-written? | Three floats 0-1: `ai_generated_score`, `privacy_risk_score`, `defamation_risk_score` |
| Rule-based detector | Explicit surface patterns: phone numbers, emails, street addresses, "works at X", social handles; explicit accusation keywords (criminal, abuser, STD, etc.) | Two floats 0-1: `rule_privacy_score`, `rule_defamation_score` |
| Stylometric heuristic | Structural writing properties: sentence-length variability, vocabulary diversity, repetition, generic/hedging phrases, first-person/casual markers | One float 0-1: `stylometric_ai_score` |

**Why these three, and why they're genuinely distinct:**

- The LLM signal is *semantic*. It can catch things with no fixed surface
  form, e.g. "Let's just say the police know him well." implies a serious
  accusation without using any of the rule-based detector's keywords.
- The rule-based signal is *lexical/pattern-based*. It is precise and cheap
  on things with a fixed surface form (a phone number is a phone number),
  and it doesn't depend on an external API being up.
- The stylometric signal is *structural*, not semantic at all - it doesn't
  know what the text is about, only how uniform the sentences are, how
  repetitive the vocabulary is, and whether it leans on generic transitions
  ("furthermore", "it is important to note") versus casual first-person
  detail. This is the signal most likely to disagree with the LLM, and that
  disagreement is informative (see Question 5).

**Combining into one score per category:** privacy and defamation each
combine the LLM signal with the rule-based signal (weighted, see Question 2
for exact formula); AI-generated combines the LLM signal with the
stylometric signal. We do **not** collapse all three categories into one
generic "risk" score - a review can be privacy-risky without being
AI-generated, and a human reviewer needs to see *which* concern was
flagged, not just "flagged."

---

## 2. Uncertainty Representation

**What does `confidence = 0.6` mean?** It means: the strongest individual
risk category (privacy, defamation, or AI-generated) landed just inside the
"medium" band. It does **not** mean "60% likely to be true" - TeaGuard never
claims to verify truth (see Known Limitations in README). It means "one of
our three signals-in-combination produced a moderate score for one
category, worth a warning but not worth blocking."

**Combining raw signal outputs into a calibrated score** (weights chosen so
the more semantically-dependent category leans more on the LLM, and the
more pattern-dependent category leans more on rules):

```
privacy_risk_score     = 0.45 * llm_privacy_score     + 0.55 * rule_privacy_score
defamation_risk_score  = 0.65 * llm_defamation_score  + 0.35 * rule_defamation_score
ai_generated_score     = 0.60 * llm_ai_score           + 0.40 * stylometric_ai_score

confidence = max(privacy_risk_score, defamation_risk_score, ai_generated_score)
```

**Thresholds:**

| Score range | Risk level |
|---|---|
| `>= 0.80` | high |
| `0.55 - 0.79` | medium |
| `< 0.55` | low |

**AI attribution** (a separate axis from risk level, since a review can be
low-risk and still get an AI-authorship verdict):

| Condition | Attribution |
|---|---|
| `ai_generated_score >= 0.75` | `likely_ai` |
| `ai_generated_score <= 0.35` AND neither privacy nor defamation is `high` | `likely_human` |
| otherwise | `uncertain` |

This is intentionally **not a binary flip at 0.5**. There is a dead zone
between 0.35 and 0.75 that always resolves to `uncertain` rather than
forcing a guess, and `likely_human` is additionally gated on there being no
high-risk label - we did not want a review that makes a serious accusation
to get a clean "likely human, all good" verdict just because it wasn't
AI-like.

---

## 3. Transparency Label Design

Exact text, decided before implementation (see README for the same table
with worked examples):

| Case | Label text |
|---|---|
| High-confidence AI | "This review may include AI-generated or AI-assisted writing. This label is based on automated signals and may not be definitive." |
| High-confidence human / low risk | "No high-risk trust or safety signals were detected. This review appears safe for standard posting." |
| Uncertain | "Our system could not confidently classify this review. It may require additional context or human review before broader visibility." |
| Privacy risk (high) | "This review may include personally identifying information and has been held for review." |
| Defamation risk (high) | "This review includes a serious personal claim that may require additional context or evidence before publication." |
| Combined high risk (privacy + defamation both high) | "This review includes serious personal claims or identifying details and may require additional context before publication." |

Design principle: every label is worded as a *possibility*, never a
verdict ("may include", "could not confidently classify"), because a false
positive here - telling a real person their own writing looks AI-generated,
or flagging a fair account as defamatory - is worse than a false negative.
That asymmetry is a deliberate design choice, not an omission.

---

## 4. Appeals Workflow

- **Who:** the original creator (identified by `creator_id`, matched against
  the stored decision for the given `content_id`).
- **What they provide:** `content_id` and free-text `creator_reasoning`.
- **What the system does on receipt:**
  1. Look up the original decision by `content_id`. 404 if not found.
  2. Update that content's status to `under_review` (if it was already
     `under_review` because of a high-risk flag, it stays `under_review` -
     an appeal never *downgrades* review status).
  3. Store the appeal reasoning and a `previous_status -> new_status`
     transition in the audit log as its own event, linked to the original
     `content_id`.
  4. Return a confirmation to the creator.
- **No automated reclassification.** The appeal creates a human-review path;
  it does not re-run the detection pipeline. This matches the assignment
  spec and avoids an obvious gaming vector (submit, get flagged, appeal,
  get auto-cleared).
- **What a human reviewer would see in the appeal queue:** the original
  submission text, all three category scores, which signals contributed,
  the transparency label shown to the reader, and the creator's appeal
  reasoning - everything needed to make a judgment call without re-running
  any code. `GET /log` is the stand-in for that queue in this project.

---

## 5. Anticipated Edge Cases

1. **A short, blunt, true warning reads as "uncertain" or gets penalized by
   the stylometric heuristic.** e.g. `"He lied. Stay away."` is only 4
   words. The stylometric signal cannot compute stable sentence-length or
   vocabulary statistics on that little text, so it returns a neutral
   score (0.4) rather than confidently calling it human - which is safer
   than false-confidently calling 4 words "AI-generated," but it does mean
   short, high-signal reviews don't get the full benefit of the doubt a
   longer casual review would.
2. **Formal, correct English from a non-native speaker looks AI-like to the
   stylometric signal.** Consistent sentence length and low use of casual
   contractions/first-person hedging are exactly the structural properties
   our heuristic associates with AI writing, but they're also just what
   careful, formal human writing looks like. This is the single most
   important documented limitation (see README Known Limitations) and is
   the direct motivation for the appeal workflow's cautious label wording.
3. **Indirect identification without any regex-matchable pattern.**
   `"He is the only bartender at the rooftop bar on 57th Street."` contains
   no phone number, email, or "works at" phrase, so the rule-based detector
   scores it low on privacy risk. The LLM signal is the only one with a
   chance of catching this, and if the LLM under-scores it too, the system
   will under-flag a genuinely identifying review.

---

## Architecture

### Submission Flow

```text
Client Platform
    |
    | POST /submit  { creator_id, text }
    v
Request Validator  (text/creator_id present and non-empty)
    |
    v
Text Preprocessor  (none required beyond validation; raw text passed through)
    |
    +---------------------------+---------------------------+
    |                           |                           |
    v                           v                           v
LLM Classifier (Groq)   Rule-Based Detector        Stylometric Heuristic
 ai/privacy/defam.         privacy/defam.               ai_generated
 scores 0-1 each           scores 0-1 each              score 0-1
    |                           |                           |
    +---------------------------+---------------------------+
                                |
                                v
                     Confidence Scorer (scoring.py)
              privacy_risk_score, defamation_risk_score,
                  ai_generated_score, confidence,
              overall_risk, attribution, recommended_action
                                |
                                v
                Transparency Label Generator (labels.py)
                                |
                                v
                 SQLite: decisions table (current state)
                 SQLite: audit_log table (append-only event)
                                |
                                v
                          JSON Response
```

### Appeal Flow

```text
Creator
    |
    | POST /appeal  { content_id, creator_reasoning }
    v
Find Original Decision  (404 if content_id unknown)
    |
    v
Update status -> "under_review"  (decisions table)
    |
    v
Write appeal event to audit_log
   { content_id, previous_status, new_status, creator_reasoning }
    |
    v
Return confirmation { content_id, status, message }
```

**Narrative:** a submission enters through `/submit`, is validated, then run
through all three signals in parallel (conceptually - implemented as three
sequential function calls). Their outputs are combined by the scorer into
three category scores and one top-line confidence, which drives both the
attribution verdict and the transparency label text. Every submission is
written to the audit log and to a `decisions` row keyed by `content_id`,
which is what the appeal flow looks up. An appeal never re-runs detection;
it only changes status and adds a linked audit-log event, preserving a full
trail from original decision to appeal to (eventual, human) resolution.

---

## AI Tool Plan

### M3: Submission Endpoint + First Signal

- **Spec sections provided to the AI tool:** Detection Signals (Question 1)
  + the Submission Flow diagram above.
- **What was requested:** a Flask app skeleton with a `POST /submit` stub
  returning a hardcoded response, plus the first signal function
  (`classify_with_llm` in `signals/llm_classifier.py`) calling the Groq
  chat completions API with a system prompt asking for the three scores as
  JSON.
- **Verification:** called `classify_with_llm` directly (outside Flask)
  on a few test strings and inspected the returned dict before wiring it
  into the route. Added an offline fallback path so the endpoint doesn't
  hard-fail when no `GROQ_API_KEY` is set.

### M4: Second/Third Signal + Confidence Scoring

- **Spec sections provided:** Detection Signals + Uncertainty Representation
  (Question 2) + the Submission Flow diagram.
- **What was requested:** the rule-based detector (`signals/rule_based.py`),
  the stylometric heuristic (`signals/stylometric.py`), and the scoring
  function (`scoring.py`) implementing the exact weighted formulas above.
- **Verification:** ran the four calibration inputs specified in the
  project guide (clearly AI, clearly human, two borderline cases) and
  confirmed the combined score moved in the expected direction between
  them; adjusted the stylometric heuristic's variance metric from raw
  variance to coefficient of variation after the first pass produced
  counter-intuitive results on short paragraphs (see README AI Usage
  section, Instance 2, for the specific fix).

### M5: Production Layer

- **Spec sections provided:** Transparency Label Design (Question 3) +
  Appeals Workflow (Question 4) + both diagrams.
- **What was requested:** the label-generation function (`labels.py`), the
  `POST /appeal` route, Flask-Limiter configuration on `/submit`, and the
  SQLite-backed audit log (`database.py`).
- **Verification:** submitted inputs designed to hit all three label
  variants and confirmed the exact text matched this document; ran the
  12-request rate-limit test and confirmed the 429 cutoff; ran a full
  submit -> appeal -> `/log` cycle and confirmed the appeal event appears
  linked to the original `content_id` with `status: under_review`.

---

## Stretch Features Attempted

- **Ensemble Detection:** implemented from the start - three signals (LLM,
  rule-based, stylometric) combined with the documented weighted formulas
  above, rather than adding this after the fact.