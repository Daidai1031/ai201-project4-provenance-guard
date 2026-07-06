# TeaGuard Provenance API

TeaGuard Provenance API is a backend trust and safety system for anonymous dating-review platforms. It analyzes user-submitted text reviews for privacy risk, defamation risk, and AI-generated writing patterns, then returns confidence scores, transparency labels, recommended moderation actions, and an auditable decision record.

The system does not determine whether a claim is legally true or false. Instead, it identifies reviews that may need additional context, privacy protection, or human review.

This project is an implementation of the "Provenance Guard" assignment brief, adapted from a general creative-content platform to a dating-review platform. In addition to the required AI-authorship attribution, it also screens for privacy risk and defamation risk, since those matter at least as much as AI authorship on this kind of platform. See `planning.md` for the full pre-implementation spec this was built from.

---

## Features

* `POST /submit`: submit a text review for analysis
* Multi-signal detection pipeline (3 signals - see Detection Signals below)
* Confidence scoring with uncertainty
* Transparency labels for AI-generated, human/low-risk, and uncertain content
* Privacy-risk and defamation-risk labels
* `POST /appeal`: creator appeal workflow
* `GET /log`: structured audit log
* Rate limiting with Flask-Limiter
* SQLite storage

---

## Tech Stack

| Component             | Tool                             |
| --------------------- | -------------------------------- |
| API framework         | Flask                            |
| LLM classifier        | Groq / Llama (`llama-3.3-70b-versatile`) |
| Rule-based detector   | Python regex and keyword rules   |
| AI-writing heuristic  | Pure Python stylometric analysis |
| Storage               | SQLite                           |
| Rate limiting         | Flask-Limiter                    |
| Environment variables | python-dotenv                    |

---

## Installation

```bash
git clone YOUR_REPO_URL
cd ai201-project4-provenance-guard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Windows Git Bash:

```bash
source .venv/Scripts/activate
```

Create a `.env` file:

```bash
GROQ_API_KEY=your_key_here
```

Do not commit `.env`.

Run the app:

```bash
python app.py
```

Health check:

```bash
curl -s http://localhost:5000/health | python -m json.tool
```

Expected response:

```json
{
  "status": "ok"
}
```

If `GROQ_API_KEY` is not set (or the Groq call fails for any reason), the LLM signal automatically falls back to a conservative offline heuristic (see `signals/llm_classifier.py`) so the rest of the pipeline still runs end-to-end. Every audit-log entry records which path produced the LLM score (`llm_scores` will reflect fallback behavior when a real key isn't present), but for real usage a valid `GROQ_API_KEY` is required for accurate results.

---

## API Usage

## 1. Submit a Review

Endpoint:

```text
POST /submit
```

Example request:

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "test-user-1",
    "text": "He works at ABC Bank on 57th Street and I heard he has an STD. Everyone should avoid him."
  }' | python -m json.tool
```

Actual response (captured against the live Groq-backed system):

```json
{
  "content_id": "content_b8c6095b9f93",
  "creator_id": "test-user-1",
  "attribution": "uncertain",
  "confidence": 0.8175,
  "overall_risk": "high",
  "status": "under_review",
  "labels": [
    {
      "type": "privacy_risk",
      "confidence": 0.8175,
      "action": "hold_for_review"
    },
    {
      "type": "defamation_risk",
      "confidence": 0.81,
      "action": "needs_human_review"
    }
  ],
  "transparency_label": "This review includes serious personal claims or identifying details and may require additional context before publication."
}
```

---

## 2. Submit an Appeal

Endpoint:

```text
POST /appeal
```

Example request:

```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "content_2d1d1058003b",
    "creator_reasoning": "I wrote this from personal experience and want a human reviewer to consider the context."
  }' | python -m json.tool
```

Actual response:

```json
{
  "content_id": "content_2d1d1058003b",
  "status": "under_review",
  "message": "Your appeal has been received and logged for review."
}
```

Appealing a `content_id` that does not exist returns a `404`:

```json
{
  "error": "No content found with content_id 'content_doesnotexist'"
}
```

---

## 3. View Audit Log

Endpoint:

```text
GET /log
```

Example request:

```bash
curl -s http://localhost:5000/log | python -m json.tool
```

Actual response (trimmed to the relevant submission + appeal pair; the running system logs every request):

```json
{
  "entries": [
    {
      "event_type": "submission",
      "content_id": "content_228361dadd33",
      "creator_id": "evidence-1",
      "timestamp": "2026-07-06T06:43:03.858Z",
      "attribution": "likely_human",
      "confidence": 0.156,
      "privacy_risk_score": 0.0,
      "defamation_risk_score": 0.0,
      "ai_generated_score": 0.156,
      "llm_scores": { "ai_generated": 0.2, "privacy_risk": 0.0, "defamation_risk": 0.0 },
      "rule_scores": { "privacy_risk": 0.0, "defamation_risk": 0.0 },
      "stylometric_ai_score": 0.09,
      "overall_risk": "low",
      "recommended_action": "allow",
      "status": "classified",
      "signals_used": ["llm_classifier", "rule_based_detector", "stylometric_ai_heuristic"],
      "appeal_filed": false
    },
    {
      "event_type": "submission",
      "content_id": "content_2d1d1058003b",
      "creator_id": "evidence-3",
      "timestamp": "2026-07-06T06:43:04.824Z",
      "attribution": "uncertain",
      "confidence": 0.8475,
      "privacy_risk_score": 0.09,
      "defamation_risk_score": 0.8475,
      "ai_generated_score": 0.492,
      "llm_scores": { "ai_generated": 0.7, "privacy_risk": 0.2, "defamation_risk": 0.9 },
      "rule_scores": { "privacy_risk": 0.0, "defamation_risk": 0.75 },
      "stylometric_ai_score": 0.18,
      "overall_risk": "high",
      "recommended_action": "needs_human_review",
      "status": "under_review",
      "signals_used": ["llm_classifier", "rule_based_detector", "stylometric_ai_heuristic"],
      "appeal_filed": false
    },
    {
      "event_type": "appeal",
      "content_id": "content_2d1d1058003b",
      "creator_id": "evidence-3",
      "timestamp": "2026-07-06T06:43:53.841Z",
      "previous_status": "under_review",
      "new_status": "under_review",
      "creator_reasoning": "I wrote this from personal experience and want a human reviewer to consider the context."
    }
  ]
}
```

---

## Architecture

A submitted review enters through `POST /submit`. The API validates the request, then runs three detection signals against the raw text: an LLM classifier (Groq), a rule-based detector, and a stylometric AI-writing heuristic. The confidence scorer combines the three signals' outputs into three separate scores - `privacy_risk_score`, `defamation_risk_score`, `ai_generated_score` - plus a top-line `confidence`. The label generator maps that decision to one of six exact transparency-label strings, and the full decision is written to both a `decisions` record (for later appeal lookups) and an append-only audit log.

```text
Client Platform
    |
    | POST /submit
    v
Request Validator
    |
    v
    +-----------------------------+-----------------------------+
    |                             |                             |
    v                             v                             v
LLM Risk Classifier         Rule-Based Detector         Stylometric AI-Writing Signal
    |                             |                             |
    +-----------------------------+-----------------------------+
                  |
                  v
          Confidence Scorer
                  |
                  v
       Transparency Label Generator
                  |
                  v
     SQLite: decisions + audit_log
                  |
                  v
          JSON Response
```

Appeal flow:

```text
Creator
    |
    | POST /appeal
    v
Find Original Decision (by content_id)
    |
    v
Update Status to under_review
    |
    v
Store Appeal Reasoning
    |
    v
Write Audit Log Entry (linked to original content_id)
    |
    v
Return Confirmation
```

---

## Detection Signals

TeaGuard uses **three** signals - one more than the required minimum of two, implementing the "Ensemble Detection" stretch feature.

### 1. LLM Classifier (Groq, `llama-3.3-70b-versatile`)

**What it measures:** meaning. The LLM is asked to assess, in one call, whether the text reads as AI-written, whether it exposes identifying information, and whether it makes a serious unverifiable accusation.

**Why it was chosen:** it can catch things with no fixed surface form. `"Let's just say the police know him well."` implies a serious accusation without using any of the rule-based detector's literal keywords - only a signal that understands meaning can catch that.

**What it misses:** consistency. The same input can score differently across calls, and it is not a factual or legal authority - a high `defamation_risk_score` means "this reads like an unverifiable serious accusation," not "this accusation is false."

### 2. Rule-Based Detector

**What it measures:** explicit surface patterns - phone numbers, emails, street addresses, "works at X" / "attends X" phrasing, and a fixed keyword list for serious accusations (criminal, abuser, assault, stalker, STD, etc.).

**Why it was chosen:** it is precise and cheap on anything with a fixed surface form, and it doesn't depend on an external API being available - it's the signal that keeps working if Groq is down.

**What it misses:** anything indirect. `"He is the only bartender at the rooftop bar on 57th Street."` identifies a specific person without matching any regex pattern in this detector.

### 3. Stylometric AI-Writing Heuristic

**What it measures:** structural writing properties, independent of meaning - sentence-length variability (coefficient of variation, not raw variance - see AI Usage below for why), vocabulary diversity, word repetition, count of generic/hedging phrases ("furthermore", "it is important to note"), and count of first-person/casual markers (contractions, "i", "we", question marks).

**Why it was chosen:** it is the signal most likely to *disagree* with the LLM, which is informative. It doesn't know what the text is about, so it can flag AI-like structure even when the content itself seems benign, or vice versa.

**What it misses:** short text (fewer than 12 words returns a neutral 0.4, since there isn't enough text to compute stable statistics) and formal, correct writing from non-native English speakers, which shares the same structural properties (uniform sentence length, low use of casual contractions) as AI-generated text for reasons that have nothing to do with authorship. This is TeaGuard's most important documented limitation - see Known Limitations.

---

## Confidence Scoring

TeaGuard calculates three separate scores instead of one blended "risk" number, because a review can be privacy-risky without being AI-generated, and a human reviewer needs to see *which* concern was flagged.

### Formulas

```text
privacy_risk_score     = 0.45 * llm_privacy_score     + 0.55 * rule_privacy_score
defamation_risk_score  = 0.65 * llm_defamation_score  + 0.35 * rule_defamation_score
ai_generated_score     = 0.60 * llm_ai_score          + 0.40 * stylometric_ai_score

confidence = max(privacy_risk_score, defamation_risk_score, ai_generated_score)
```

Privacy risk leans more on the rule-based detector because identifying information usually has a recognizable surface pattern. Defamation risk leans more on the LLM because serious accusations depend on meaning, not just keywords. AI-generated leans more on the LLM because it captures semantic/stylistic coherence holistically, with stylometry as a structural check.

`confidence` takes the **maximum** of the three category scores rather than an average, deliberately: the strongest individual concern is the one a human reviewer needs to see, and averaging it against two low, irrelevant scores would dilute a real signal.

### Thresholds

| Score Range | Risk Level |
| ----------- | ---------- |
| `>= 0.80`   | high       |
| `0.55-0.79` | medium     |
| `< 0.55`    | low        |

AI attribution:

| Condition                                             | Attribution    |
| ------------------------------------------------------ | -------------- |
| `ai_generated_score >= 0.75`                            | `likely_ai`    |
| `ai_generated_score <= 0.35` and no high-risk labels    | `likely_human` |
| otherwise                                               | `uncertain`    |

This is not a binary flip at 0.5 - there is a dead zone between 0.35 and 0.75 that always resolves to `uncertain`, and `likely_human` additionally requires that neither privacy nor defamation risk is `high`, so a serious accusation never gets a clean "likely human, all good" verdict just because it wasn't AI-like.

### How the scoring was validated

The scoring function was tested against the four calibration inputs specified in the project guide (clearly AI-generated, clearly human/casual, a borderline formal-human case, and a borderline lightly-edited-AI case), run against the live Groq-backed system:

| Input | confidence | overall_risk | attribution |
|---|---|---|---|
| Clearly AI-generated paragraph | 0.812 | high | likely_ai |
| Clearly human, casual review | 0.12 | low | likely_human |
| Borderline formal human writing | 0.612 | medium | uncertain |
| Borderline lightly-edited AI text | 0.64 | medium | uncertain |

Both borderline cases correctly landed in the `uncertain` middle band instead of being forced into a confident verdict, which is the behavior the thresholds were designed to produce.

### Two examples with noticeably different confidence

**High-confidence case** - a review with an explicit phone number and workplace reference:

> "He works at ABC Bank on 57th Street and his phone number is 212-555-0198."

```json
{
  "attribution": "uncertain",
  "confidence": 0.955,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review may include personally identifying information and has been held for review."
}
```

**Lower-confidence case** - an ordinary, low-risk review:

> "I went on two dates with him. He was polite, but we did not really click. I would not go out again, but nothing unsafe happened."

```json
{
  "attribution": "likely_human",
  "confidence": 0.156,
  "overall_risk": "low",
  "status": "classified",
  "transparency_label": "No high-risk trust or safety signals were detected. This review appears safe for standard posting."
}
```

`0.955` versus `0.156` is a substantial, meaningful spread produced by the same formula on genuinely different inputs - not a constant.

---

## Transparency Labels

The system returns exact user-facing label text. Every label is worded as a *possibility* ("may include", "could not confidently classify"), never a verdict, because a false positive here - telling a real person their own writing looks AI-generated, or flagging a fair account as defamatory - is worse than a false negative. That asymmetry is a deliberate design choice.

### High-Confidence AI

> "This review may include AI-generated or AI-assisted writing. This label is based on automated signals and may not be definitive."

### High-Confidence Human / Low-Risk

> "No high-risk trust or safety signals were detected. This review appears safe for standard posting."

### Uncertain

> "Our system could not confidently classify this review. It may require additional context or human review before broader visibility."

### Privacy Risk

> "This review may include personally identifying information and has been held for review."

### Defamation Risk

> "This review includes a serious personal claim that may require additional context or evidence before publication."

### Combined High Risk

> "This review includes serious personal claims or identifying details and may require additional context before publication."

---

## Example Results

All results below were captured against the running system with a live `GROQ_API_KEY` configured.

### Low-Risk Review

Input:

```text
I went on two dates with him. He was polite, but we did not really click. I would not go out again, but nothing unsafe happened.
```

Result:

```json
{
  "attribution": "likely_human",
  "confidence": 0.156,
  "overall_risk": "low",
  "status": "classified",
  "transparency_label": "No high-risk trust or safety signals were detected. This review appears safe for standard posting."
}
```

### Privacy-Risk Review

Input:

```text
He works at ABC Bank on 57th Street and his phone number is 212-555-0198.
```

Result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.955,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review may include personally identifying information and has been held for review."
}
```

### Defamation-Risk Review

Input:

```text
He is definitely a criminal and abuses every woman he dates. Everyone should avoid him.
```

Result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.8475,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review includes a serious personal claim that may require additional context or evidence before publication."
}
```

### Combined High-Risk Review

Input:

```text
He works at ABC Bank on 57th Street and I heard he has an STD. Everyone should avoid him.
```

Result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.8175,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review includes serious personal claims or identifying details and may require additional context before publication."
}
```

### AI-Like Review

Input:

```text
This individual demonstrates numerous red flags that should be carefully considered before engaging in a romantic relationship. It is important to prioritize personal safety and evaluate behavioral patterns objectively.
```

Result:

```json
{
  "attribution": "likely_ai",
  "confidence": 0.84,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review may include AI-generated or AI-assisted writing. This label is based on automated signals and may not be definitive."
}
```

Note: this review's `recommended_action` came back as `allow` even though `overall_risk` is `high`, because privacy and defamation risk are both low here - the high risk level is driven entirely by `ai_generated_score`. `overall_risk`/`status` and `recommended_action` are answering two different questions (see Spec Reflection below): "does this need a human to look at it" versus "should it be blocked outright." A confidently AI-flagged review still goes to `under_review` so a moderator can decide on disclosure, even with nothing else wrong with it.

---

## Rate Limiting

The `POST /submit` endpoint uses Flask-Limiter.

Configured limit:

```text
10 per minute;100 per day
```

Reasoning:

A normal creator or small platform integration should not need more than 10 review submissions per minute during testing or real usage - nobody posts reviews that fast by hand. The per-minute limit is the one that actually stops a script from flooding the endpoint. The daily limit is a looser backstop against sustained abuse across a whole day, set high enough (100) that it never gets in the way of legitimate local development or testing, while still bounding worst-case load from a single client.

Rate limit test (12 rapid requests against the live server):

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Actual result:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

The first 10 requests succeed and the 11th/12th are correctly rejected.

---

## Appeals Workflow

Creators can appeal a classification through `POST /appeal`.

The appeal must include:

* `content_id`
* `creator_reasoning`

When an appeal is submitted:

1. The system finds the original decision by `content_id` (returns `404` if it doesn't exist).
2. The content status is updated to `under_review`.
3. The creator's reasoning is stored.
4. The appeal is logged alongside the original decision, linked by `content_id`.
5. The API returns a confirmation response.

The system does not automatically reclassify the content after an appeal - it does not re-run the detection pipeline. This creates a human-review path and preserves a full audit trail, and it avoids an obvious gaming vector (submit, get flagged, appeal, get auto-cleared by the same code that flagged it).

---

## Known Limitations

### The system does not verify truth

TeaGuard does not determine whether a serious claim is true. It only detects that the review contains a serious claim that may require additional context or human review.

### Formal, correct English from a non-native speaker looks AI-like

This is the single most specific and consequential limitation, tied directly to the stylometric signal: consistent sentence length and low use of casual contractions/first-person hedging are exactly the structural properties the heuristic associates with AI writing (see `signals/stylometric.py`), but they are also just what careful, formal human writing looks like. In testing, the borderline formal-human calibration text ("The relationship between monetary policy and asset price inflation...") scored `confidence: 0.612` - solidly in the `uncertain` band - specifically because it has low sentence-length variability and no casual markers, not because it was AI-written. The appeal workflow exists in large part because of this exact failure mode.

### Indirect privacy leakage is difficult

A review can identify someone without including a phone number or address. `"He is the only bartender at the rooftop bar on 57th Street."` would likely score low on the rule-based detector, since none of its regex patterns match, and would identify a real person only if the LLM signal happens to catch the implication.

### Short reviews are hard to classify

Stylometric analysis is unreliable on very short reviews - `"He lied. Stay away."` (4 words) falls below the 12-word threshold in `signals/stylometric.py` and returns a neutral 0.4 rather than a confident verdict in either direction. This is a deliberate design choice (better to abstain than to guess), but it does mean short, high-signal reviews don't get full credit for being obviously human.

---

## Spec Reflection

**How the spec helped:** deciding the exact confidence formula and thresholds in `planning.md` *before* writing `scoring.py` caught a design flaw early: an initial draft would have averaged the three category scores together into one number. Writing out "what does 0.6 mean to a user" first made it obvious that averaging would let a severe defamation risk get diluted by two irrelevant low scores, which is exactly the false-negative failure mode the hints section warns against. The final design takes the max instead, and that decision traces directly back to the planning question, not to a code review after the fact.

**Where the implementation diverged from the spec:** `planning.md` treats `overall_risk` and `recommended_action` as if they'd always point the same direction. In practice they can diverge - see the AI-Like Review example above, where `overall_risk: "high"` but `recommended_action: "allow"`, because the high risk level is driven by `ai_generated_score` rather than by privacy or defamation risk. This wasn't anticipated in planning because the spec's risk-level table was written with privacy/defamation in mind; once AI-generated content shares the same threshold scale, a confidently-AI review with no other issues legitimately produces this combination. If deploying this for real, I would either give `ai_generated_score` its own separate "requires disclosure review" status distinct from `overall_risk`, or exclude it from the `confidence`/`overall_risk` calculation entirely and treat AI-authorship as an orthogonal label rather than a risk level.

---

## AI Usage

AI tools were used to support development, but the system design and final decisions were reviewed and verified manually against `planning.md` at every milestone.

### Instance 1: Flask API skeleton and first signal (Milestone 3)

I directed the AI tool to generate a Flask app skeleton with a `POST /submit` stub and the first signal function (`classify_with_llm` in `signals/llm_classifier.py`), given the Detection Signals section of the spec and the architecture diagram. The generated Groq prompt originally asked for a single `ai_generated_score` only; I revised it to request all three scores (`ai_generated_score`, `privacy_risk_score`, `defamation_risk_score`) in one call, since the spec calls for those three categories from the start, and added the offline fallback path so the app doesn't hard-fail without a live API key.

### Instance 2: Stylometric heuristic and confidence scoring (Milestone 4)

I directed the AI tool to generate the stylometric signal and the `scoring.py` formulas from the Uncertainty Representation section of `planning.md`. The first version of the stylometric heuristic used raw sentence-length **variance** as its uniformity signal. When I ran it against the project guide's four calibration texts, the short clearly-AI-generated paragraph (only 3 sentences) produced a *higher* raw variance than the clearly-human paragraph, the opposite of what the metric was supposed to show, because raw variance scales with sentence length and the AI paragraph happened to have one much longer sentence. I revised the metric to use the coefficient of variation (std / mean) instead of raw variance, which is scale-invariant, and re-ran the calibration set to confirm the AI text now correctly showed the lowest relative variability.

### Instance 3: Label mapping and appeal endpoint (Milestone 5)

I directed the AI tool to generate the label-mapping function and the `POST /appeal` route from the Transparency Label Design and Appeals Workflow sections of `planning.md`. The initial appeal implementation re-ran the detection pipeline on appeal to "give the creator an updated score," which directly contradicts the spec ("Automated re-classification is not required" / avoids a gaming vector where flagging then appealing clears content automatically). I removed the re-classification call and kept the appeal endpoint to only updating status and logging the reasoning, matching the planning document.

