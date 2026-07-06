"""
Confidence scoring.

Combines the three detection signals (LLM classifier, rule-based detector,
stylometric heuristic) into three separate risk scores, then derives a
single top-line confidence, an overall risk level, an AI-attribution
verdict, and a recommended moderation action.

Design decision: we deliberately keep privacy_risk, defamation_risk, and
ai_generated as three separate scores instead of collapsing everything into
one generic "bad content" score. A review can be privacy-risky without being
AI-generated, or vice versa, and collapsing them would hide that from a
human reviewer.
"""

# --- Signal weights (see README "Confidence Scoring" for the reasoning) ---
PRIVACY_LLM_WEIGHT = 0.45
PRIVACY_RULE_WEIGHT = 0.55

DEFAMATION_LLM_WEIGHT = 0.65
DEFAMATION_RULE_WEIGHT = 0.35

AI_LLM_WEIGHT = 0.60
AI_STYLOMETRIC_WEIGHT = 0.40

# --- Thresholds -----------------------------------------------------------
HIGH_RISK_THRESHOLD = 0.80
MEDIUM_RISK_THRESHOLD = 0.55

AI_LIKELY_THRESHOLD = 0.75
HUMAN_LIKELY_THRESHOLD = 0.35


def risk_level(score: float) -> str:
    if score >= HIGH_RISK_THRESHOLD:
        return "high"
    if score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def compute_scores(llm_result: dict, rule_result: dict, stylometric_score: float) -> dict:
    """llm_result: dict from signals.llm_classifier.classify_with_llm
    rule_result: dict from signals.rule_based.classify_with_rules
    stylometric_score: float from signals.stylometric.stylometric_ai_score
    """
    llm_ai = llm_result["ai_generated_score"]
    llm_privacy = llm_result["privacy_risk_score"]
    llm_defamation = llm_result["defamation_risk_score"]

    rule_privacy = rule_result["rule_privacy_score"]
    rule_defamation = rule_result["rule_defamation_score"]

    privacy_risk_score = round(
        PRIVACY_LLM_WEIGHT * llm_privacy + PRIVACY_RULE_WEIGHT * rule_privacy, 4
    )
    defamation_risk_score = round(
        DEFAMATION_LLM_WEIGHT * llm_defamation + DEFAMATION_RULE_WEIGHT * rule_defamation, 4
    )
    ai_generated_score = round(
        AI_LLM_WEIGHT * llm_ai + AI_STYLOMETRIC_WEIGHT * stylometric_score, 4
    )

    confidence = round(max(privacy_risk_score, defamation_risk_score, ai_generated_score), 4)
    overall_risk = risk_level(confidence)

    attribution = determine_attribution(
        ai_generated_score, privacy_risk_score, defamation_risk_score
    )
    recommended_action = determine_action(
        privacy_risk_score, defamation_risk_score, attribution
    )
    status = "under_review" if overall_risk == "high" else "classified"

    return {
        "privacy_risk_score": privacy_risk_score,
        "defamation_risk_score": defamation_risk_score,
        "ai_generated_score": ai_generated_score,
        "confidence": confidence,
        "overall_risk": overall_risk,
        "attribution": attribution,
        "recommended_action": recommended_action,
        "status": status,
        "llm_ai_score": llm_ai,
        "llm_privacy_score": llm_privacy,
        "llm_defamation_score": llm_defamation,
        "rule_privacy_score": rule_privacy,
        "rule_defamation_score": rule_defamation,
        "stylometric_ai_score": stylometric_score,
    }


def determine_attribution(ai_generated_score: float, privacy_risk_score: float,
                           defamation_risk_score: float) -> str:
    if ai_generated_score >= AI_LIKELY_THRESHOLD:
        return "likely_ai"
    no_high_risk = (
        risk_level(privacy_risk_score) != "high"
        and risk_level(defamation_risk_score) != "high"
    )
    if ai_generated_score <= HUMAN_LIKELY_THRESHOLD and no_high_risk:
        return "likely_human"
    return "uncertain"


def determine_action(privacy_risk_score: float, defamation_risk_score: float,
                      attribution: str) -> str:
    privacy_level = risk_level(privacy_risk_score)
    defamation_level = risk_level(defamation_risk_score)

    if privacy_level == "high":
        return "hold_for_review"
    if defamation_level == "high":
        return "needs_human_review"
    if privacy_level == "medium" or defamation_level == "medium":
        return "show_warning"
    if attribution == "uncertain":
        return "allow_with_context"
    return "allow"


def build_category_labels(scores: dict) -> list:
    """Per-category label entries for the /submit response, matching the
    README's `labels` array. Only categories at medium risk or above are
    surfaced - a low-risk category is not worth showing to a reviewer."""
    labels = []
    privacy_level = risk_level(scores["privacy_risk_score"])
    if privacy_level != "low":
        labels.append({
            "type": "privacy_risk",
            "confidence": scores["privacy_risk_score"],
            "action": "hold_for_review" if privacy_level == "high" else "show_warning",
        })

    defamation_level = risk_level(scores["defamation_risk_score"])
    if defamation_level != "low":
        labels.append({
            "type": "defamation_risk",
            "confidence": scores["defamation_risk_score"],
            "action": "needs_human_review" if defamation_level == "high" else "show_warning",
        })

    return labels