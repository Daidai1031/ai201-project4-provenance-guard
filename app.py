"""
TeaGuard Provenance API - Flask app.

MILESTONE 3 SCOPE:
  - GET  /health
  - POST /submit  (wired to the FIRST signal only - the Groq LLM classifier)
  - GET  /log     (structured audit log)

`confidence` and `attribution` below are PLACEHOLDER logic based on the LLM
signal alone. In Milestone 4 this gets replaced by scoring.py, which
combines all three signals (LLM + rule-based + stylometric) into the real
confidence formula from planning.md. Do not read too much into the
attribution thresholds here yet - they exist just so the endpoint returns
something meaningful while we verify signal 1 end-to-end.
"""

import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request

import database
from signals.llm_classifier import classify_with_llm

app = Flask(__name__)
database.init_db()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def placeholder_attribution(ai_generated_score: float) -> str:
    """Temporary M3 logic - the real thresholds live in scoring.py from M4 on."""
    if ai_generated_score >= 0.75:
        return "likely_ai"
    if ai_generated_score <= 0.35:
        return "likely_human"
    return "uncertain"


def placeholder_label(attribution: str) -> str:
    """Temporary M3 text - replaced by labels.py in Milestone 5."""
    if attribution == "likely_ai":
        return "This review may include AI-generated or AI-assisted writing."
    if attribution == "likely_human":
        return "No high-risk signals detected in this early-stage check."
    return "Our system could not confidently classify this review yet."


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/submit", methods=["POST"])
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
    ai_score = llm_result["ai_generated_score"]

    attribution = placeholder_attribution(ai_score)
    confidence = ai_score
    label = placeholder_label(attribution)

    log_entry = {
        "event_type": "submission",
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "llm_ai_score": ai_score,
        "llm_privacy_score": llm_result["privacy_risk_score"],
        "llm_defamation_score": llm_result["defamation_risk_score"],
        "llm_source": llm_result["source"],
        "status": "classified",
    }
    database.append_log_entry("submission", content_id, creator_id, timestamp, log_entry)

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
    }), 200


@app.route("/log", methods=["GET"])
def get_log():
    entries = database.get_log_entries(limit=200)
    return jsonify({"entries": entries})


if __name__ == "__main__":
    app.run(debug=True, port=5000)