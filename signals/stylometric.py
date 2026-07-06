"""
Stylometric AI-writing heuristic.

Pure-Python, no external libraries. Estimates whether a piece of text reads
as AI-generated / template-like based on structural writing properties
rather than meaning. This signal is intentionally "dumb" about content -
it does not know what the text is about, only how it is put together.

Captures:
  - sentence length variability (coefficient of variation, so it is not
    biased by overall sentence length)
  - type-token ratio / vocabulary diversity
  - repetition ratio (word-level)
  - generic/hedging phrase count (AI text leans on stock transitions)
  - first-person, idiosyncratic / casual-language markers (human reviews
    tend to have these; template AI writing tends not to)

Blind spot: on very short text there isn't enough signal to compute stable
statistics, so we deliberately return a neutral (uncertain) score rather
than a confident one. This is also unreliable on formal, polished human
writing (e.g. non-native English speakers, academic style), which can look
uniform for reasons that have nothing to do with AI authorship. That
specific failure mode is called out in the README's Known Limitations
section.
"""

import re
from collections import Counter

GENERIC_PHRASES = [
    "it is important to note",
    "it is crucial",
    "it is essential",
    "in conclusion",
    "furthermore",
    "moreover",
    "overall,",
    "numerous",
    "carefully considered",
    "objectively",
    "prioritize",
    "behavioral patterns",
    "red flags",
    "paradigm",
    "stakeholders",
    "genuine tradeoffs",
    "studies show",
]

FIRST_PERSON_RE = re.compile(r"\b(i|we|my|our|me)\b", re.IGNORECASE)
WORD_RE = re.compile(r"[A-Za-z']+")
CONTRACTION_RE = re.compile(r"\b\w+'(t|re|ve|ll|d|s|m)\b", re.IGNORECASE)
CASUAL_MARKER_RE = re.compile(r"\.\.\.|\bok\b|\blol\b|\bhonestly\b|\bwtf\b|\?", re.IGNORECASE)

SHORT_TEXT_WORD_THRESHOLD = 12
NEUTRAL_SCORE_FOR_SHORT_TEXT = 0.4


def _sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _words(text: str):
    return WORD_RE.findall(text.lower())


def sentence_length_cv(sentences) -> float:
    """Coefficient of variation (std / mean) of sentence length in words.
    Scale-invariant, unlike raw variance, so it is comparable across texts
    of different lengths."""
    lengths = [len(_words(s)) for s in sentences if _words(s)]
    if len(lengths) < 2:
        return 0.5  # not enough sentences to say anything; treat as neutral
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.5
    variance = sum((length - mean) ** 2 for length in lengths) / len(lengths)
    std = variance ** 0.5
    return std / mean


def type_token_ratio(words) -> float:
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def repetition_ratio(words) -> float:
    if not words:
        return 0.0
    counts = Counter(words)
    repeated = sum(c for c in counts.values() if c > 1)
    return repeated / len(words)


def generic_phrase_count(lowered_text: str) -> int:
    return sum(1 for phrase in GENERIC_PHRASES if phrase in lowered_text)


def first_person_detail_count(text: str) -> int:
    return len(FIRST_PERSON_RE.findall(text))


def casual_marker_count(text: str) -> int:
    """Contractions and informal punctuation/slang. AI-generated marketing or
    formal prose rarely uses these; casual human writing often does."""
    return len(CONTRACTION_RE.findall(text)) + len(CASUAL_MARKER_RE.findall(text))


def stylometric_ai_score(text: str) -> float:
    words = _words(text)

    if len(words) < SHORT_TEXT_WORD_THRESHOLD:
        return NEUTRAL_SCORE_FOR_SHORT_TEXT

    sentences = _sentences(text)
    lowered = text.lower()

    cv = sentence_length_cv(sentences)
    ttr = type_token_ratio(words)
    repetition = repetition_ratio(words)
    generic_hits = generic_phrase_count(lowered)
    first_person_hits = first_person_detail_count(text)
    casual_hits = casual_marker_count(text)

    # Low sentence-length variability (relative to mean) reads as AI-like;
    # human writing tends to mix short punchy sentences with longer ones.
    if cv < 0.25:
        variability_score = 1.0
    elif cv < 0.5:
        variability_score = 0.5
    else:
        variability_score = 0.1

    # High vocabulary diversity with almost no repetition is a mild AI-like
    # signal on its own (careful, this is also true of good formal human
    # writing - that overlap is a known limitation, not a bug).
    diversity_score = 0.5 if (ttr > 0.75 and repetition < 0.10) else 0.15

    generic_score = min(1.0, generic_hits * 0.3)
    human_penalty = min(0.6, first_person_hits * 0.08 + casual_hits * 0.12)

    raw = (0.30 * variability_score) + (0.20 * diversity_score) + (0.50 * generic_score)
    raw = max(0.0, raw - human_penalty)
    return round(max(0.0, min(1.0, raw)), 4)


def stylometric_features(text: str) -> dict:
    """Exposes the raw intermediate metrics, useful for debugging/calibration."""
    words = _words(text)
    sentences = _sentences(text)
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "sentence_length_cv": round(sentence_length_cv(sentences), 4),
        "type_token_ratio": round(type_token_ratio(words), 4),
        "repetition_ratio": round(repetition_ratio(words), 4),
        "generic_phrase_count": generic_phrase_count(text.lower()),
        "first_person_count": first_person_detail_count(text),
        "casual_marker_count": casual_marker_count(text),
        "score": stylometric_ai_score(text),
    }