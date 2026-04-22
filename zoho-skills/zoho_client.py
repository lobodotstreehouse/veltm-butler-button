"""
Zoho REST API client for Butler Button CSMO agent.
Targets the India DC (.in) Zoho One tenant.
Token refresh via OAuth2 — store credentials in .env.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

ZOHO_DC = "in"
CRM_BASE = f"https://www.zohoapis.{ZOHO_DC}/crm/v2"
BOOKS_BASE = f"https://www.zohoapis.{ZOHO_DC}/books/v3"
MAIL_BASE = f"https://mail.zoho.{ZOHO_DC}/api"
ACCOUNTS_BASE = f"https://accounts.zoho.{ZOHO_DC}/oauth/v2/token"


class ZohoClient:
    """Thin OAuth2 client for Zoho One APIs (India DC)."""

    def __init__(self):
        self.client_id = os.environ["ZOHO_CLIENT_ID"]
        self.client_secret = os.environ["ZOHO_CLIENT_SECRET"]
        self.refresh_token = os.environ["ZOHO_REFRESH_TOKEN"]
        self.org_id = os.environ.get("ZOHO_BOOKS_ORG_ID", "")
        self._access_token: str | None = None
        self._token_expiry: float = 0

    def _refresh(self):
        r = requests.post(ACCOUNTS_BASE, params={
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        data = r.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60

    @property
    def token(self) -> str:
        if not self._access_token or time.time() >= self._token_expiry:
            self._refresh()
        return self._access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self.token}"}

    def crm_get(self, path: str, params: dict = None) -> dict:
        r = requests.get(f"{CRM_BASE}/{path}", headers=self._headers(), params=params or {})
        r.raise_for_status()
        return r.json()

    def crm_post(self, path: str, payload: dict) -> dict:
        r = requests.post(f"{CRM_BASE}/{path}", headers=self._headers(), json=payload)
        r.raise_for_status()
        return r.json()

    def crm_put(self, path: str, payload: dict) -> dict:
        r = requests.put(f"{CRM_BASE}/{path}", headers=self._headers(), json=payload)
        r.raise_for_status()
        return r.json()

    def books_get(self, path: str, params: dict = None) -> dict:
        p = {"organization_id": self.org_id, **(params or {})}
        r = requests.get(f"{BOOKS_BASE}/{path}", headers=self._headers(), params=p)
        r.raise_for_status()
        return r.json()


# Shared singleton — all skills import this
zoho = ZohoClient()
