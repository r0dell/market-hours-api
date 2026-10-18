"""Market Hours API mit x402-Bezahlung (USDC auf Base).

Umgebungsvariablen:
  PAY_TO              Deine Wallet-Adresse (0x...), hierhin gehen die Zahlungen. Pflicht.
  X402_NETWORK        "testnet" (Base Sepolia, Standard) oder "mainnet" (Base).
  CDP_API_KEY_ID      Coinbase-Developer-Platform-Key. Für mainnet und Bazaar-Listing nötig.
  CDP_API_KEY_SECRET  dazugehöriges Secret.
  PUBLIC_URL          Öffentliche https-Adresse des Dienstes (für die Bazaar-Beschreibung).

Start:  uvicorn paid_app:app --host 0.0.0.0 --port 8000
Gratis:  /v1/markets, /health, /docs
Bezahlt: /v1/is-open, /v1/next, /v1/holidays
"""
import os
import re

from x402 import x402ResourceServer
from x402.extensions.bazaar import (
    OutputConfig,
    bazaar_resource_server_extension,
    declare_discovery_extension,
)
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import PaymentOption, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from app import app

NETWORKS = {"testnet": "eip155:84532", "mainnet": "eip155:8453"}
TESTNET_FACILITATOR = os.environ.get("FACILITATOR_URL", "https://x402.org/facilitator")

PAY_TO = os.environ.get("PAY_TO", "").strip()
if not re.fullmatch(r"0x[0-9a-fA-F]{40}", PAY_TO):
    raise SystemExit("PAY_TO fehlt oder ist keine gültige Wallet-Adresse (0x + 40 Hex-Zeichen).")

MODE = os.environ.get("X402_NETWORK", "testnet").lower()
if MODE not in NETWORKS:
    raise SystemExit("X402_NETWORK muss 'testnet' oder 'mainnet' sein.")
NETWORK = NETWORKS[MODE]

CDP_ID = os.environ.get("CDP_API_KEY_ID", "").strip().strip('"\'').strip()
CDP_SECRET = os.environ.get("CDP_API_KEY_SECRET", "").strip().strip('"\'').strip()
if "BEGIN" in CDP_SECRET:
    CDP_SECRET = CDP_SECRET.replace("\\n", "\n")  # PEM aus einzeiligem Feld


def _describe_cdp_keys() -> str:
    """Format der Keys beschreiben, ohne Werte preiszugeben."""
    id_kind = ("uuid" if re.fullmatch(r"[0-9a-fA-F-]{36}", CDP_ID)
               else "organizations-path" if CDP_ID.startswith("organizations/") else "other")
    if "BEGIN EC PRIVATE KEY" in CDP_SECRET:
        sec_kind = "ec-pem"
    else:
        try:
            import base64
            sec_kind = f"base64-{len(base64.b64decode(CDP_SECRET, validate=True))}bytes"
        except Exception:
            sec_kind = "unparseable"
    return f"CDP key: id={id_kind} (len {len(CDP_ID)}), secret={sec_kind} (len {len(CDP_SECRET)})"


if CDP_ID and CDP_SECRET:
    from cdp.x402 import create_facilitator_config
    print(_describe_cdp_keys(), flush=True)
    facilitator_cfg = create_facilitator_config(CDP_ID, CDP_SECRET)
elif MODE == "mainnet":
    raise SystemExit("Für mainnet werden CDP_API_KEY_ID und CDP_API_KEY_SECRET benötigt.")
else:
    facilitator_cfg = FacilitatorConfig(url=TESTNET_FACILITATOR)

server = x402ResourceServer(HTTPFacilitatorClient(facilitator_cfg))
server.register(NETWORK, ExactEvmServerScheme())
server.register_extension(bazaar_resource_server_extension)

MARKET_SCHEMA = {
    "type": "string",
    "description": "Market code: XNYS, XNAS, XLON, XETR, XSWX, XTKS, XHKG, XSHG, XASX, "
                   "CME_EQUITY, EUREX_INDEX",
}
AT_SCHEMA = {"type": "string",
             "description": "Optional ISO 8601 time with offset, e.g. 2026-11-27T15:00:00Z. Default: now."}


def pay(price: str) -> PaymentOption:
    return PaymentOption(scheme="exact", pay_to=PAY_TO, price=price, network=NETWORK)


routes = {
    "GET /v1/is-open": RouteConfig(
        accepts=pay("$0.001"),
        description="Returns whether a stock exchange or futures market is open at a given "
                    "time, the session type (open, break, closed), and the next open and close "
                    "times in UTC and local time.",
        mime_type="application/json",
        service_name="Market Hours API",
        tags=["finance", "market-hours", "calendar", "trading"],
        extensions=declare_discovery_extension(
            input={"market": "XNYS", "at": "2026-11-27T15:00:00Z"},
            input_schema={"properties": {"market": MARKET_SCHEMA, "at": AT_SCHEMA},
                          "required": ["market"]},
            output=OutputConfig(example={
                "market": "XNYS", "is_open": True, "state": "open",
                "timezone": "America/New_York",
                "next_close": {"utc": "2026-11-27T18:00:00+00:00",
                               "local": "2026-11-27T13:00:00-05:00"}}),
        ),
    ),
    "GET /v1/next": RouteConfig(
        accepts=pay("$0.001"),
        description="Returns the next open and next close time of a stock exchange or "
                    "futures market after a given time.",
        mime_type="application/json",
        service_name="Market Hours API",
        tags=["finance", "market-hours", "calendar"],
        extensions=declare_discovery_extension(
            input={"market": "CME_EQUITY"},
            input_schema={"properties": {"market": MARKET_SCHEMA, "at": AT_SCHEMA},
                          "required": ["market"]},
            output=OutputConfig(example={
                "market": "CME_EQUITY", "timezone": "America/Chicago",
                "next_open": {"utc": "2026-10-19T22:00:00+00:00",
                              "local": "2026-10-19T17:00:00-05:00"},
                "next_close": {"utc": "2026-10-20T21:00:00+00:00",
                               "local": "2026-10-20T16:00:00-05:00"}}),
        ),
    ),
    "GET /v1/holidays": RouteConfig(
        accepts=pay("$0.002"),
        description="Returns closed weekdays (holidays) and early-close days of a stock "
                    "exchange or futures market within a date range of up to two years.",
        mime_type="application/json",
        service_name="Market Hours API",
        tags=["finance", "market-holidays", "calendar"],
        extensions=declare_discovery_extension(
            input={"market": "XSWX", "start": "2026-12-01", "end": "2026-12-31"},
            input_schema={"properties": {
                "market": MARKET_SCHEMA,
                "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end": {"type": "string", "description": "End date YYYY-MM-DD"}},
                "required": ["market", "start", "end"]},
            output=OutputConfig(example={
                "market": "XSWX", "closed_days": [{"date": "2026-12-24", "name": "Christmas Eve"}],
                "early_closes": []}),
        ),
    ),
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
app.title = f"Market Hours API ({MODE})"
