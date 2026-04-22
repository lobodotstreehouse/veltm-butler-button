"""
Butler Button — Zoho Flow Webhook Receiver
Receives POST requests from Zoho Flow and routes them to the right agent.
Run: python webhook_server.py  (default port 8080)
Expose via ngrok or deploy to a VPS/Railway for production.

Zoho Flow setup for each trigger:
  1. Create a Flow with the relevant CRM trigger
  2. Add a Webhook action pointing to: http://YOUR_SERVER:8080/webhook/<route>
  3. Pass the record ID in the JSON body

Routes:
  POST /webhook/lead-intake    — body: {"lead_id": "..."}
  POST /webhook/deal-won       — body: {"deal_id": "..."}
  GET  /health                 — returns 200 OK
"""

import os
import json
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import sys
sys.path.insert(0, os.path.dirname(__file__))

from agents.agent_lead_intake import run as run_lead_intake
from agents.agent_deal_won import run as run_deal_won

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "butler-button-secret-change-me")


def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    def _send(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "butler-button-webhooks"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return

        try:
            if path == "/webhook/lead-intake":
                lead_id = payload.get("lead_id")
                if not lead_id:
                    self._send(400, {"error": "missing lead_id"})
                    return
                result = run_lead_intake(lead_id)
                self._send(200, result)

            elif path == "/webhook/deal-won":
                deal_id = payload.get("deal_id")
                if not deal_id:
                    self._send(400, {"error": "missing deal_id"})
                    return
                result = run_deal_won(deal_id)
                self._send(200, result)

            else:
                self._send(404, {"error": f"unknown route: {path}"})

        except Exception as e:
            print(f"ERROR on {path}: {e}")
            self._send(500, {"error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"Butler Button webhook server running on port {port}")
    print(f"Routes: POST /webhook/lead-intake  |  POST /webhook/deal-won  |  GET /health")
    server.serve_forever()
