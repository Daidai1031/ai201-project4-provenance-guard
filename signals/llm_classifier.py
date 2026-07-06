"""
LLM-based classifier signal (Groq / Llama).

Sends the review text to an LLM and asks it to assess three things at once:
  - ai_generated_score: does this read like AI-generated / AI-assisted writing?
  - privacy_risk_score: does this expose information that could identify the
    person being reviewed, even indirectly?
  - defamation_risk_score: does this make a serious, reputation-damaging
    accusation the platform cannot verify?

This signal is useful because it can reason about *meaning*, not just
surface patterns - e.g. "Let's just say the police know him well." implies
a serious accusation without using any of the literal keywords a rule-based
detector looks for. Its weakness is the flip side of that strength: it can
be inconsistent between runs, and it should never be treated as a factual
or legal authority.

If no GROQ_API_KEY is configured, or the API call fails for any reason
(network, rate limit, malformed response), this module falls back to a
conservative offline heuristic so the rest of the pipeline keeps working.
The fallback is intentionally simple and is not a substitute for the real
model - it exists so the app is demoable without a live API key.
"""

import json
import os
import re

try:
    from groq import Groq
except ImportError:  # library not installed yet / offline dev environment
    Groq = None

MODEL_NAME = "llama-3.3-70b-versatile"

_client = None
_client_checked = False


def get_client():
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or Groq is None:
        _client = None
        return None
    try:
        _client = Groq(api_key=api_key)
    except Exception:
        _client = None
    return _client


SYSTEM_PROMPT = """You are a trust-and-safety classifier for an anonymous dating-review \
platform. You are given a single user-submitted review of a person the \
reviewer dated. Assess the text along three dimensions and respond with \
ONLY a JSON object - no prose, no markdown fences - with exactly these keys:

"ai_generated_score": float 0-1. How likely the text was written or heavily \
assisted by an AI language model rather than typed directly by a human in \
the moment. Generic corporate-sounding hedging, uniform sentence structure, \
and absence of specific personal detail all raise this score. Casual, \
specific, first-person detail lowers it.

"privacy_risk_score": float 0-1. How likely the text exposes information \
that could identify the person being reviewed - workplace, neighborhood, \
employer, school, phone number, social handle, or a distinctive detail tied \
to a specific place (e.g. "the only bartender at X") - even if no single \
detail alone is identifying.

"defamation_risk_score": float 0-1. How likely the text makes a serious, \
potentially reputation-damaging factual accusation (crime, violence, \
disease, abuse, fraud) that the platform has no way to verify, including \
indirect implications of such an accusation.

Use the full 0-1 range and avoid defaulting every score to 0.5. Base every \
score only on the text given, not on assumptions about the person."""


def classify_with_llm(text: str) -> dict:
    """Returns dict with ai_generated_score, privacy_risk_score,
    defamation_risk_score, and source (for audit-log transparency about
    which path produced the score)."""
    client = get_client()
    if client is None:
        return _fallback(text, reason="no_api_key_or_client")

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=250,
        )
        raw = response.choices[0].message.content.strip()
        data = _parse_json(raw)
        return {
            "ai_generated_score": _clamp(data.get("ai_generated_score", 0.5)),
            "privacy_risk_score": _clamp(data.get("privacy_risk_score", 0.0)),
            "defamation_risk_score": _clamp(data.get("defamation_risk_score", 0.0)),
            "source": f"groq:{MODEL_NAME}",
        }
    except Exception as exc:  # network error, malformed response, rate limit, etc.
        return _fallback(text, reason=f"llm_error:{exc.__class__.__name__}")


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _clamp(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


# --- Offline fallback -------------------------------------------------
# Only used when Groq is unavailable. Deliberately conservative: it should
# not be the reason a review gets held for review, only the reason the app
# keeps functioning end-to-end without a live API key.

_AI_MARKERS = [
    "it is important to note",
    "furthermore",
    "in conclusion",
    "paradigm",
    "delve into",
    "it is crucial",
    "it is essential",
    "numerous red flags",
    "carefully considered",
    "objectively",
    "stakeholders",
    "genuine tradeoffs",
    "studies show",
]

_PRIVACY_HINTS = [
    r"\bworks?\s+at\b",
    r"\bstreet\b",
    r"\bavenue\b",
    r"@\w{3,}",
    r"\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b",
]

_DEFAMATION_HINTS = [
    "criminal", "abus", "assault", "stalker", "scammer", "std",
    "drug dealer", "violent", "dangerous", "cheater", "police know him",
    "police know her",
]


def _fallback(text: str, reason: str) -> dict:
    lowered = text.lower()

    ai_hits = sum(marker in lowered for marker in _AI_MARKERS)
    ai_score = min(1.0, 0.18 * ai_hits)

    privacy_hits = sum(1 for pattern in _PRIVACY_HINTS if re.search(pattern, lowered))
    privacy_score = min(1.0, 0.4 * privacy_hits)

    defamation_hits = sum(1 for hint in _DEFAMATION_HINTS if hint in lowered)
    defamation_score = min(1.0, 0.45 * defamation_hits)

    return {
        "ai_generated_score": ai_score,
        "privacy_risk_score": privacy_score,
        "defamation_risk_score": defamation_score,
        "source": f"fallback:{reason}",
    }