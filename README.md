# TeaGuard Provenance API

TeaGuard Provenance API is a backend trust and safety system for anonymous dating-review platforms. It analyzes user-submitted text reviews for privacy risk, defamation risk, and AI-generated writing patterns, then returns confidence scores, transparency labels, recommended moderation actions, and an auditable decision record.

The system does not determine whether a claim is legally true or false. Instead, it identifies reviews that may need additional context, privacy protection, or human review.

---

## Features

* `POST /submit`: submit a text review for analysis
* Multi-signal detection pipeline
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
| LLM classifier        | Groq / Llama                     |
| Rule-based detector   | Python regex and keyword rules   |
| AI-writing heuristic  | Pure Python stylometric analysis |
| Storage               | SQLite                           |
| Rate limiting         | Flask-Limiter                    |
| Environment variables | python-dotenv                    |

---

## Installation

```bash
git clone YOUR_REPO_URL
cd teaguard-provenance-api
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

Example `requirements.txt`:

```text
flask>=3.0.0
flask-limiter>=3.5.0
groq==0.15.0
python-dotenv==1.0.1
```

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

Example response:

```json
{
  "content_id": "content_abc123",
  "creator_id": "test-user-1",
  "attribution": "uncertain",
  "confidence": 0.86,
  "overall_risk": "high",
  "status": "under_review",
  "labels": [
    {
      "type": "privacy_risk",
      "confidence": 0.74,
      "action": "hold_for_review"
    },
    {
      "type": "defamation_risk",
      "confidence": 0.86,
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
    "content_id": "content_abc123",
    "creator_reasoning": "I wrote this review based on my own experience and did not intend to expose private information."
  }' | python -m json.tool
```

Example response:

```json
{
  "content_id": "content_abc123",
  "status": "under_review",
  "message": "Your appeal has been received and logged for review."
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

Example response:

```json
{
  "entries": [
    {
      "event_type": "submission",
      "content_id": "content_001",
      "creator_id": "test-user-1",
      "timestamp": "2026-07-05T21:00:00Z",
      "attribution": "likely_human",
      "confidence": 0.28,
      "privacy_risk_score": 0.12,
      "defamation_risk_score": 0.18,
      "ai_generated_score": 0.28,
      "overall_risk": "low",
      "recommended_action": "allow",
      "status": "classified",
      "signals_used": [
        "llm_classifier",
        "rule_based_detector",
        "stylometric_ai_heuristic"
      ],
      "appeal_filed": false
    },
    {
      "event_type": "submission",
      "content_id": "content_002",
      "creator_id": "test-user-2",
      "timestamp": "2026-07-05T21:01:00Z",
      "attribution": "uncertain",
      "confidence": 0.91,
      "privacy_risk_score": 0.91,
      "defamation_risk_score": 0.32,
      "ai_generated_score": 0.44,
      "overall_risk": "high",
      "recommended_action": "hold_for_review",
      "status": "under_review",
      "signals_used": [
        "llm_classifier",
        "rule_based_detector",
        "stylometric_ai_heuristic"
      ],
      "appeal_filed": false
    },
    {
      "event_type": "appeal",
      "content_id": "content_002",
      "creator_id": "test-user-2",
      "timestamp": "2026-07-05T21:02:00Z",
      "previous_status": "under_review",
      "new_status": "under_review",
      "creator_reasoning": "I wrote this from personal experience and want a human reviewer to consider the context."
    }
  ]
}
```

---

## Architecture

A submitted review enters through `POST /submit`. The API validates the request, preprocesses the text, and runs three detection signals: an LLM classifier, a rule-based detector, and a stylometric AI-writing heuristic. The confidence scorer combines the signals into privacy, defamation, and AI-generated scores. The label generator returns a plain-language transparency label, and the full decision is stored in the audit log.

```text
Client Platform
    |
    | POST /submit
    v
Request Validator
    |
    v
Text Preprocessor
    |
    +-----------------------------+
    |                             |
    v                             v
LLM Risk Classifier        Rule-Based Detector
    |                             |
    v                             v
    +-------------+---------------+
                  |
                  v
       Stylometric AI-Writing Signal
                  |
                  v
          Confidence Scorer
                  |
                  v
       Transparency Label Generator
                  |
                  v
       SQLite Audit Log
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
Find Original Decision
    |
    v
Update Status to under_review
    |
    v
Store Appeal Reasoning
    |
    v
Write Audit Log Entry
    |
    v
Return Confirmation
```

---

## Detection Signals

TeaGuard uses three signals.

### 1. LLM Classifier

The LLM classifier analyzes the meaning of the review and returns scores for:

* AI-generated likelihood
* Privacy risk
* Defamation risk
* Severe attack risk
* Need for human review

This signal is useful because it can detect indirect meaning.

Example:

```text
Let’s just say the police know him well.
```

A keyword detector might miss this, but an LLM may recognize that it implies a serious accusation.

Limitation: the LLM can be inconsistent and should not be treated as a factual or legal authority.

---

### 2. Rule-Based Detector

The rule-based detector uses regex and keyword rules to detect explicit risks.

Privacy patterns include:

* Phone numbers
* Email addresses
* Street addresses
* Social media handles
* Workplace references
* School references

Defamation-risk keywords include:

* criminal
* abuser
* assault
* stalker
* scammer
* STD
* drug dealer
* violent
* dangerous
* cheater

This signal is useful because explicit patterns like phone numbers are often easier to detect with rules.

Limitation: rule-based detection can miss indirect language and may create false positives.

---

### 3. Stylometric AI-Writing Heuristic

The stylometric signal estimates whether a review looks AI-generated or template-like.

It checks:

* Sentence length variance
* Type-token ratio
* Repetition ratio
* Generic phrase count
* First-person detail count

Limitation: very short reviews and non-native English writing are difficult to score fairly.

---

## Confidence Scoring

TeaGuard calculates separate scores for each category.

### Privacy Risk Score

```text
privacy_risk_score =
0.45 * llm_privacy_score
+ 0.55 * rule_privacy_score
```

Privacy risk relies more heavily on rule-based detection because personally identifying information often has recognizable patterns.

### Defamation Risk Score

```text
defamation_risk_score =
0.65 * llm_defamation_score
+ 0.35 * rule_defamation_score
```

Defamation risk relies more heavily on the LLM because serious accusations often depend on meaning and context.

### AI-Generated Score

```text
ai_generated_score =
0.60 * llm_ai_score
+ 0.40 * stylometric_ai_score
```

AI-generated detection combines semantic judgment with writing-style analysis.

### Main Confidence Score

```text
confidence = max(
  privacy_risk_score,
  defamation_risk_score,
  ai_generated_score
)
```

The main confidence score reflects the strongest signal that affected the final decision.

---

## Thresholds

| Score Range | Risk Level |
| ----------- | ---------- |
| `>= 0.80`   | high       |
| `0.55–0.79` | medium     |
| `< 0.55`    | low        |

AI attribution:

| Condition                                            | Attribution    |
| ---------------------------------------------------- | -------------- |
| `ai_generated_score >= 0.75`                         | `likely_ai`    |
| `ai_generated_score <= 0.35` and no high-risk labels | `likely_human` |
| otherwise                                            | `uncertain`    |

Recommended actions:

| Condition                                         | Action               |
| ------------------------------------------------- | -------------------- |
| High privacy risk                                 | `hold_for_review`    |
| High defamation risk                              | `needs_human_review` |
| Medium risk                                       | `show_warning`       |
| Low risk                                          | `allow`              |
| Uncertain AI attribution with no high safety risk | `allow_with_context` |

---

## Transparency Labels

The system returns exact user-facing label text.

### High-Confidence AI

> “This review may include AI-generated or AI-assisted writing. This label is based on automated signals and may not be definitive.”

### High-Confidence Human / Low-Risk

> “No high-risk trust or safety signals were detected. This review appears safe for standard posting.”

### Uncertain

> “Our system could not confidently classify this review. It may require additional context or human review before broader visibility.”

### Privacy Risk

> “This review may include personally identifying information and has been held for review.”

### Defamation Risk

> “This review includes a serious personal claim that may require additional context or evidence before publication.”

### Combined High Risk

> “This review includes serious personal claims or identifying details and may require additional context before publication.”

---

## Example Results

### Low-Risk Review

Input:

```text
I went on two dates with him. He was polite, but we did not really click. I would not go out again, but nothing unsafe happened.
```

Example result:

```json
{
  "attribution": "likely_human",
  "confidence": 0.28,
  "overall_risk": "low",
  "status": "classified",
  "transparency_label": "No high-risk trust or safety signals were detected. This review appears safe for standard posting."
}
```

---

### Privacy-Risk Review

Input:

```text
He works at ABC Bank on 57th Street and his phone number is 212-555-0198.
```

Example result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.91,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review may include personally identifying information and has been held for review."
}
```

---

### Defamation-Risk Review

Input:

```text
He is definitely a criminal and abuses every woman he dates. Everyone should avoid him.
```

Example result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.88,
  "overall_risk": "high",
  "status": "under_review",
  "transparency_label": "This review includes a serious personal claim that may require additional context or evidence before publication."
}
```

---

### AI-Like Review

Input:

```text
This individual demonstrates numerous red flags that should be carefully considered before engaging in a romantic relationship. It is important to prioritize personal safety and evaluate behavioral patterns objectively.
```

Example result:

```json
{
  "attribution": "likely_ai",
  "confidence": 0.78,
  "overall_risk": "medium",
  "status": "classified",
  "transparency_label": "This review may include AI-generated or AI-assisted writing. This label is based on automated signals and may not be definitive."
}
```

---

## Rate Limiting

The `POST /submit` endpoint uses Flask-Limiter.

Configured limit:

```text
10 per minute;100 per day
```

Reasoning:

A normal creator or small platform integration should not need more than 10 review submissions per minute during testing. The per-minute limit helps prevent scripts from flooding the endpoint. The daily limit prevents repeated abuse while still allowing enough requests for local development.

Rate limit test:

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Expected result:

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

---

## Appeals Workflow

Creators can appeal a classification through `POST /appeal`.

The appeal must include:

* `content_id`
* `creator_reasoning`

When an appeal is submitted:

1. The system finds the original decision.
2. The content status is updated to `under_review`.
3. The creator’s reasoning is stored.
4. The appeal is logged alongside the original decision.
5. The API returns a confirmation response.

The system does not automatically reclassify the content after an appeal. The appeal creates a human-review path and preserves an audit trail.

---

## Known Limitations

### The system does not verify truth

TeaGuard does not determine whether a serious claim is true. It only detects that the review contains a serious claim that may require additional context or human review.

### Indirect privacy leakage is difficult

A review can identify someone without including a phone number or address.

Example:

```text
He is the only bartender at the rooftop bar on 57th Street.
```

This may identify a real person, but a simple rule-based detector may not catch it.

### Short reviews are hard to classify

Stylometric analysis is unreliable on very short reviews.

Example:

```text
He lied. Stay away.
```

The system should avoid high-confidence AI attribution for very short text.

### Non-native English may be misclassified

Formal or generic writing from a non-native English speaker may look AI-generated. This is why the AI label uses cautious language and the system includes an appeal workflow.

---

## Spec Reflection

Writing the specification before implementation helped define the system’s boundaries. The most important design decision was separating `privacy_risk`, `defamation_risk`, and `ai_generated` into different scores instead of returning one generic moderation score.

The implementation may diverge slightly from the original thresholds after testing. For example, if the rule-based detector over-flags harmless workplace mentions, the privacy-risk threshold may need adjustment.

---

## AI Usage

AI tools were used to support development, but the system design and final decisions were reviewed manually.

### Instance 1: Flask API skeleton

I directed the AI tool to generate a Flask app skeleton with:

* `POST /submit`
* `POST /appeal`
* `GET /log`
* SQLite setup
* Basic request validation

I revised the output to make sure each endpoint matched the API contract and returned the required fields.

### Instance 2: Detection and scoring functions

I directed the AI tool to generate:

* Rule-based privacy detector
* Rule-based defamation-risk detector
* Stylometric AI-writing heuristic
* Confidence scoring function

I revised the scoring logic to match the planned formulas and tested it on low-risk, privacy-risk, defamation-risk, AI-like, and uncertain examples.

### Instance 3: Label and appeal logic

I directed the AI tool to generate label mapping logic and the appeal endpoint. I revised the labels to use cautious, non-accusatory language and verified that appeals update the status to `under_review`.

---

## Walkthrough Video Plan

The walkthrough video will show:

1. The Flask server running locally.
2. A low-risk review submitted through `POST /submit`.
3. A privacy-risk review.
4. A defamation-risk review.
5. The `GET /log` output.
6. A creator appeal through `POST /appeal`.
7. The updated audit log showing the appeal.

Short explanation:

```text
TeaGuard is a backend trust and safety API for anonymous dating-review platforms. It uses three signals: an LLM classifier, rule-based privacy and claim detection, and stylometric AI-writing heuristics. The system does not try to prove whether a claim is true. Instead, it identifies reviews that may need privacy protection, additional context, or human review. I designed the labels to communicate uncertainty and added an appeal workflow so creators have a path to contest automated classifications.
```
