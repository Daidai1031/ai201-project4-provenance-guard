"""
Rule-based detector.

Uses regex and keyword matching to catch *explicit* privacy and defamation
risk patterns. This signal is deliberately simple and literal: it is strong
on things that have a recognizable surface pattern (phone numbers, "works
at ..."), and weak on anything that requires understanding meaning (see
llm_classifier.py for that).
"""

import re

PHONE_RE = re.compile(r"(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{3,}")
STREET_RE = re.compile(
    r"\b\d{1,5}\s+\w+(\s\w+){0,3}\s(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln)\b",
    re.IGNORECASE,
)
ORDINAL_STREET_RE = re.compile(r"\b\d{1,3}(st|nd|rd|th)\s+(street|st|avenue|ave)\b", re.IGNORECASE)
WORKPLACE_RE = re.compile(r"\b(works?\s+at|employed\s+at|works?\s+for)\b", re.IGNORECASE)
SCHOOL_RE = re.compile(r"\b(goes\s+to|attends|studies\s+at|student\s+at)\b", re.IGNORECASE)

PRIVACY_PATTERNS = [
    PHONE_RE,
    EMAIL_RE,
    HANDLE_RE,
    STREET_RE,
    ORDINAL_STREET_RE,
    WORKPLACE_RE,
    SCHOOL_RE,
]

# Explicit, serious accusation keywords. Kept lowercase; matching is done on
# lowercased text. Word-boundary matching avoids matching inside unrelated words.
DEFAMATION_KEYWORDS = [
    "criminal",
    "abuser",
    "abuses",
    "abusive",
    "assault",
    "stalker",
    "scammer",
    "std",
    "drug dealer",
    "violent",
    "dangerous",
    "cheater",
    "rapist",
    "predator",
    "fraud",
]


def detect_privacy_risk(text: str) -> float:
    """Returns a 0-1 score. Each distinct pattern family that fires adds a
    fixed amount; one strong hit (e.g. a phone number) is already meaningful,
    so we do not require multiple hits to reach a high score."""
    hits = sum(1 for pattern in PRIVACY_PATTERNS if pattern.search(text))
    if hits == 0:
        return 0.0
    return min(1.0, 0.5 + (hits - 1) * 0.25)


def detect_defamation_risk(text: str) -> float:
    lowered = text.lower()
    hits = 0
    for kw in DEFAMATION_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
            hits += 1
    if hits == 0:
        return 0.0
    return min(1.0, 0.55 + (hits - 1) * 0.2)


def classify_with_rules(text: str) -> dict:
    return {
        "rule_privacy_score": detect_privacy_risk(text),
        "rule_defamation_score": detect_defamation_risk(text),
    }