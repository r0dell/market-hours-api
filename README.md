# Market Hours API (v0.1)

Beantwortet für 11 Handelsplätze: Ist die Börse jetzt offen? Wann öffnet oder schliesst sie als Nächstes? Welche Tage sind Feiertage oder verkürzt?

## Starten (Windows, Mac oder Linux)

```
pip install -r requirements.txt
uvicorn app:app --port 8000
```

Danach im Browser: http://localhost:8000/docs (interaktive Doku zum Ausprobieren)

## Endpunkte

| Endpunkt | Beispiel |
|---|---|
| `/v1/markets` | Liste aller Märkte |
| `/v1/is-open` | `/v1/is-open?market=CME_EQUITY&at=2026-11-26T18:30:00Z` |
| `/v1/next` | `/v1/next?market=XSWX` |
| `/v1/holidays` | `/v1/holidays?market=XNYS&start=2026-11-01&end=2026-12-31` |

Ohne `at` gilt die aktuelle Zeit. Zeitangaben brauchen einen Offset (`Z` oder `+01:00`).

## Märkte

Aktien: XNYS, XNAS, XLON, XETR, XSWX, XTKS, XHKG, XSHG, XASX (nur reguläre Session).
Futures: `CME_EQUITY` (ES, NQ, MES, MNQ …), `EUREX_INDEX` (FDAX, FESX, FSMI).

## Datenbasis

- Handelstage und Feiertage: Open-Source-Bibliothek `exchange_calendars`.
- Futures-Sessionzeiten: eigene Tabellen in `engine.py` (`FUTURES_HOURS`), weil die Bibliothek
  Globex mit 17:00–17:00 CT ohne Tagespause und Eurex ohne Asian Hours abbildet.
- Verkürzte Futures-Tage (z. B. Thanksgiving) übernehmen die Schlusszeit der Bibliothek
  und sollten mit dem offiziellen CME-Feiertagskalender abgeglichen werden.

## Bezahlte Version (x402)

`paid_app.py` legt eine x402-Bezahlschranke vor die API:

| Endpunkt | Preis |
|---|---|
| `/v1/is-open`, `/v1/next` | 0.01 USDC |
| `/v1/holidays` | 0.02 USDC |
| `/v1/markets`, `/health`, `/docs` | gratis |

Ohne Zahlung antworten die bezahlten Endpunkte mit HTTP 402 und den Zahlungsdetails.
Agenten mit x402-Client zahlen automatisch und erhalten dann die Antwort.

Umgebungsvariablen:

- `PAY_TO`: deine Wallet-Adresse (0x…), Pflicht
- `X402_NETWORK`: `testnet` (Base Sepolia, Spielgeld) oder `mainnet` (Base, echtes USDC)
- `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`: Coinbase-Developer-Platform-Key, nötig für mainnet und Bazaar-Listing

Lokal: `PAY_TO=0x… uvicorn paid_app:app --port 8000`

## Online stellen (Render)

1. Dateien in ein GitHub-Repository hochladen.
2. Auf render.com: New → Blueprint → Repository wählen. `render.yaml` wird erkannt.
3. `PAY_TO` eintragen, `X402_NETWORK` auf `testnet` lassen, deployen.
4. Testen, dann auf `mainnet` umstellen und die CDP-Keys eintragen.
5. Erster echter bezahlter Aufruf → Endpunkte werden im x402 Bazaar gelistet (bis 15 Minuten).

## Tests

```
python -m pytest -q
```
