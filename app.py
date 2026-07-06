"""
TeaGuard Provenance API - Flask app.

MILESTONE 5 SCOPE (final production layer):
  - GET  /health
  - POST /submit   full 3-signal pipeline + scoring.py + labels.py (exact
                    wording from planning.md) + rate limiting (10/min;100/day)
  - POST /appeal   creator appeal workflow
  - GET  /log      structured audit log, now including appeal events

See README.md for the full architecture narrative, scoring formulas, label
text, and rate-limit reasoning. See planning.md for the pre-implementation
spec this app was built from.
"""

import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import database
from signals.llm_classifier import classify_with_llm
from signals.rule_based import classify_with_rules
from signals.stylometric import stylometric_ai_score
from scoring import compute_scores, build_category_labels
from labels import build_transparency_label

SIGNALS_USED = ["llm_classifier", "rule_based_detector", "stylometric_ai_heuristic"]

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

database.init_db()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")
    creator_id = payload.get("creator_id")

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' is required and must be a non-empty string"}), 400
    if not creator_id or not isinstance(creator_id, str):
        return jsonify({"error": "'creator_id' is required and must be a string"}), 400

    content_id = f"content_{uuid.uuid4().hex[:12]}"
    timestamp = now_iso()

    llm_result = classify_with_llm(text)
    rule_result = classify_with_rules(text)
    stylometric_score = stylometric_ai_score(text)

    scores = compute_scores(llm_result, rule_result, stylometric_score)
    transparency_label = build_transparency_label(scores)
    category_labels = build_category_labels(scores)

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "text": text,
        "timestamp": timestamp,
        "attribution": scores["attribution"],
        "confidence": scores["confidence"],
        "privacy_risk_score": scores["privacy_risk_score"],
        "defamation_risk_score": scores["defamation_risk_score"],
        "ai_generated_score": scores["ai_generated_score"],
        "overall_risk": scores["overall_risk"],
        "recommended_action": scores["recommended_action"],
        "status": scores["status"],
        "transparency_label": transparency_label,
        "signals_used": SIGNALS_USED,
        "appeal_filed": False,
    }
    database.save_decision(record)

    log_entry = {
        "event_type": "submission",
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": scores["attribution"],
        "confidence": scores["confidence"],
        "privacy_risk_score": scores["privacy_risk_score"],
        "defamation_risk_score": scores["defamation_risk_score"],
        "ai_generated_score": scores["ai_generated_score"],
        "llm_scores": {
            "ai_generated": scores["llm_ai_score"],
            "privacy_risk": scores["llm_privacy_score"],
            "defamation_risk": scores["llm_defamation_score"],
        },
        "rule_scores": {
            "privacy_risk": scores["rule_privacy_score"],
            "defamation_risk": scores["rule_defamation_score"],
        },
        "stylometric_ai_score": scores["stylometric_ai_score"],
        "overall_risk": scores["overall_risk"],
        "recommended_action": scores["recommended_action"],
        "status": scores["status"],
        "signals_used": SIGNALS_USED,
        "appeal_filed": False,
    }
    database.append_log_entry("submission", content_id, creator_id, timestamp, log_entry)

    response = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": scores["attribution"],
        "confidence": scores["confidence"],
        "overall_risk": scores["overall_risk"],
        "status": scores["status"],
        "labels": category_labels,
        "transparency_label": transparency_label,
    }
    return jsonify(response), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    payload = request.get_json(silent=True) or {}
    content_id = payload.get("content_id")
    creator_reasoning = payload.get("creator_reasoning")

    if not content_id or not isinstance(content_id, str):
        return jsonify({"error": "'content_id' is required and must be a string"}), 400
    if not creator_reasoning or not isinstance(creator_reasoning, str):
        return jsonify({"error": "'creator_reasoning' is required and must be a string"}), 400

    decision = database.get_decision(content_id)
    if decision is None:
        return jsonify({"error": f"No content found with content_id '{content_id}'"}), 404

    previous_status = decision["status"]
    database.mark_under_review(content_id)
    timestamp = now_iso()

    log_entry = {
        "event_type": "appeal",
        "content_id": content_id,
        "creator_id": decision["creator_id"],
        "timestamp": timestamp,
        "previous_status": previous_status,
        "new_status": "under_review",
        "creator_reasoning": creator_reasoning,
    }
    database.append_log_entry("appeal", content_id, decision["creator_id"], timestamp, log_entry)

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Your appeal has been received and logged for review.",
    }), 200


@app.route("/log", methods=["GET"])
def get_log():
    entries = database.get_log_entries(limit=200)
    return jsonify({"entries": entries})


if __name__ == "__main__":
    app.run(debug=True, port=5000)