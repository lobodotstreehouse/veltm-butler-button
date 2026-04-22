"""
Butler Button — Webhook Server
Receives Zoho Flow → Form submission events and routes to agents.
Port: 5055 (chosen to avoid conflicts)

Option-A routes (/webhook/asset-request, /webhook/asset-decision) are
registered from flow_webhook_handler.py (zero-login advisor experience).
"""
from flask import Flask, request, jsonify, redirect
import importlib.util
import logging, threading, importlib, os, sys
from pathlib import Path

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

@app.route("/approve/<asset_id>", methods=["GET"])
def approve_asset(asset_id):
    """
    One-click approve/reject link from the advisor email.
    GET /approve/<asset_id>?decision=Approve&email=advisor@...
    Updates the Generated_Asset in the local queue and shows a confirmation page.
    """
    decision      = request.args.get("decision", "Approve")
    advisor_email = request.args.get("email", "")
    new_status    = "approved" if decision == "Approve" else "changes_requested"
    label         = "✅ Approved" if decision == "Approve" else "✏️ Changes Requested"
    color         = "#4f46e5" if decision == "Approve" else "#f59e0b"

    try:
        _BIN = Path("/Users/openclaw/.openclaw/bin/local_queue_api.py")
        spec = importlib.util.spec_from_file_location("local_queue_api", _BIN)
        q    = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
        q.update_record("Generated_Asset", asset_id, {
            "Status":        new_status,
            "Revision_Notes": "",
        })
        logging.info("Asset %s → %s (advisor: %s)", asset_id, new_status, advisor_email)
        msg = f"<b>{label}</b> — your asset has been updated."
    except Exception as exc:
        logging.error("Approve route error: %s", exc)
        msg = f"Error updating asset: {exc}"

    html = f"""<!doctype html>
<html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Butler Button</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f9fafb}}
.card{{background:#fff;border-radius:16px;padding:3rem;max-width:480px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
.badge{{display:inline-block;background:{color};color:#fff;padding:.5rem 1.5rem;border-radius:99px;font-weight:700;font-size:1.1rem;margin-bottom:1.5rem}}
h1{{color:#1a1a1a;font-size:1.5rem;margin:0 0 .75rem}}
p{{color:#6b7280;margin:0 0 2rem}}
a{{color:{color};font-weight:600;text-decoration:none}}</style>
</head><body><div class=card>
<div class=badge>{label}</div>
<h1>You're all set.</h1>
<p>{msg}</p>
<p style="font-size:.85rem;color:#9ca3af">Asset ID: {asset_id}</p>
<a href="https://butlerbutton.co">← Back to Butler Button</a>
</div></body></html>"""

    return html, 200, {"Content-Type": "text/html"}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "butler-button-webhook-server"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", 5055))
    app.run(host="0.0.0.0", port=port, debug=False)
