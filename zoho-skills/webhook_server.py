"""
Butler Button — Webhook Server
Receives Zoho Flow → Form submission events and routes to agents.
Port: 5055 (chosen to avoid conflicts)

Option-A routes (/webhook/asset-request, /webhook/asset-decision) are
registered from flow_webhook_handler.py (zero-login advisor experience).
"""
from flask import Flask, request, jsonify
import logging, threading, importlib, os, sys

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Register Option-A zero-login advisor routes
try:
    sys.path.insert(0, "/Users/openclaw/.openclaw/zoho-creator/option_a")
    from flow_webhook_handler import register_routes as _register_option_a
    _register_option_a(app)
except Exception as _e:
    logging.warning("Could not register Option-A routes: %s", _e)

AGENTS = {
    "lead_intake": "agents.agent_lead_intake",
    "pipeline_velocity": "agents.agent_pipeline_velocity",
    "morning_brief": "agents.agent_morning_brief",
    "deal_won": "agents.agent_deal_won",
    "followup_drafter": "agents.agent_followup_drafter",
    "campaign_builder": "agents.agent_campaign_builder",
}

def run_agent(agent_key: str, payload: dict):
    try:
        mod = importlib.import_module(AGENTS[agent_key])
        mod.main(payload)
    except Exception as e:
        logging.error(f"Agent {agent_key} failed: {e}", exc_info=True)

@app.route("/webhook/lead", methods=["POST"])
def lead_webhook():
    payload = request.json or {}
    threading.Thread(target=run_agent, args=("lead_intake", payload), daemon=True).start()
    return jsonify({"status": "queued", "agent": "lead_intake"}), 202

@app.route("/webhook/followup", methods=["POST"])
def followup_webhook():
    payload = request.json or {}
    threading.Thread(target=run_agent, args=("followup_drafter", payload), daemon=True).start()
    return jsonify({"status": "queued", "agent": "followup_drafter"}), 202

@app.route("/webhook/campaign", methods=["POST"])
def campaign_webhook():
    payload = request.json or {}
    threading.Thread(target=run_agent, args=("campaign_builder", payload), daemon=True).start()
    return jsonify({"status": "queued", "agent": "campaign_builder"}), 202

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "butler-button-webhook-server"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", 5055))
    app.run(host="0.0.0.0", port=port, debug=False)
