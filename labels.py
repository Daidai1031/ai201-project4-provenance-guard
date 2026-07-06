"""
Transparency label generation.

Maps a decision (attribution + per-category risk levels) to the exact
user-facing label text. The text itself is the product of a design
decision documented in README.md and planning.md: labels are worded
cautiously ("may include", "may require additional context") because none
of our signals are certain, and a false positive - telling a real person
their own writing looks AI-generated, or accusing a review of defamation
risk when it was a fair account - is worse than a false negative here.
"""

from scoring import risk_level

LABEL_AI = (
    "This review may include AI-generated or AI-assisted writing. "
    "This label is based on automated signals and may not be definitive."
)

LABEL_HUMAN_LOW_RISK = (
    "No high-risk trust or safety signals were detected. "
    "This review appears safe for standard posting."
)

LABEL_UNCERTAIN = (
    "Our system could not confidently classify this review. "
    "It may require additional context or human review before broader visibility."
)

LABEL_PRIVACY_RISK = (
    "This review may include personally identifying information and has been held for review."
)

LABEL_DEFAMATION_RISK = (
    "This review includes a serious personal claim that may require additional "
    "context or evidence before publication."
)

LABEL_COMBINED_HIGH_RISK = (
    "This review includes serious personal claims or identifying details and may "
    "require additional context before publication."
)


def build_transparency_label(scores: dict) -> str:
    privacy_high = risk_level(scores["privacy_risk_score"]) == "high"
    defamation_high = risk_level(scores["defamation_risk_score"]) == "high"

    if privacy_high and defamation_high:
        return LABEL_COMBINED_HIGH_RISK
    if privacy_high:
        return LABEL_PRIVACY_RISK
    if defamation_high:
        return LABEL_DEFAMATION_RISK

    attribution = scores["attribution"]
    if attribution == "likely_ai":
        return LABEL_AI
    if attribution == "likely_human":
        return LABEL_HUMAN_LOW_RISK
    return LABEL_UNCERTAIN