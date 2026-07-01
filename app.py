"""Flask web application for GitCSTV — live HLTV-style card generation."""

import base64
import os
import sys
import traceback

from flask import Flask, jsonify, render_template, request

# Add the project root to the module search path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github_client import fetch_github_data
from scoring import build_stats, overall_rank
from card_generator import generate_card_to_bytes, STAT_DESCRIPTIONS

app = Flask(__name__)


@app.route("/")
def index():
    """Serve the main web interface."""
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """POST endpoint: accept a GitHub username, return the card + metadata.

    Request body:  {"username": "torvalds"}
    Response: {
      "image":  "data:image/png;base64,...",  // base64-encoded card PNG
      "stats":  { firepower, starpower, ... },
      "stat_descriptions": { ... },           // tooltip text per stat
      "awards": { mvp, evp },
      "events": [...],
      "rank":   6,
      "name":   "Linus Torvalds",
      ...
    }
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "Username is required"}), 400

    token = os.environ.get("GITHUB_TOKEN")

    try:
        raw = fetch_github_data(username, token)
    except Exception as e:
        return jsonify({"error": f"GitHub API error: {e}"}), 500

    try:
        stats = build_stats(raw)
        rank = overall_rank(stats["rating"])
        img_bytes = generate_card_to_bytes(raw, stats, rank)
        b64 = base64.b64encode(img_bytes).decode("utf-8")
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Card generation failed"}), 500

    return jsonify({
        "image": f"data:image/png;base64,{b64}",
        "stats": {
            "firepower": stats["firepower"],
            "starpower": stats["starpower"],
            "longevity": stats["longevity"],
            "impact": stats["impact_score"],
            "collaboration": stats["collaboration"],
            "versatility": stats["versatility"],
            "rating": stats["rating"],
        },
        "stat_descriptions": STAT_DESCRIPTIONS,
        "awards": stats["awards"],
        "events": stats["events"],
        "rank": rank,
        "name": raw.get("name", username),
        "total_stars": raw["repos"]["total_stars"],
        "followers": raw["followers"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5090, debug=False)
