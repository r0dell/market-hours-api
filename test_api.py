"""Prüft die API gegen bekannte Handelszeiten. Start: python3 -m pytest -q"""
from fastapi.testclient import TestClient

from app import app

c = TestClient(app)


def get(path, **params):
    r = c.get(path, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_markets_list():
    codes = {m["code"] for m in get("/v1/markets")}
    assert {"XNYS", "XSWX", "CME_EQUITY", "EUREX_INDEX"} <= codes


def test_nyse_thanksgiving_closed_and_early_close_next_day():
    r = get("/v1/is-open", market="XNYS", at="2026-11-26T15:00:00Z")
    assert r["state"] == "closed"
    assert r["next_open"]["local"].startswith("2026-11-27T09:30")
    assert r["next_close"]["local"].startswith("2026-11-27T13:00")  # early close


def test_nyse_open_normal_day():
    r = get("/v1/is-open", market="XNYS", at="2026-10-20T15:00:00Z")  # 11:00 ET
    assert r["is_open"] and not r["session"]["early_close"]


def test_tokyo_lunch_break():
    r = get("/v1/is-open", market="XTKS", at="2026-10-20T03:00:00Z")  # 12:00 JST
    assert r["state"] == "break" and r["is_open"] is False
    assert r["next_open"]["local"].startswith("2026-10-20T12:30")


def test_cme_sunday_evening_open_for_monday_session():
    r = get("/v1/is-open", market="CME_EQUITY", at="2026-10-18T22:30:00Z")  # So 17:30 CT
    assert r["is_open"]
    assert r["session"]["trading_day"] == "2026-10-19"


def test_cme_daily_halt():
    r = get("/v1/is-open", market="CME_EQUITY", at="2026-10-19T21:30:00Z")  # Mo 16:30 CT
    assert r["state"] == "closed"
    assert r["next_open"]["local"].startswith("2026-10-19T17:00")


def test_cme_saturday_closed():
    r = get("/v1/is-open", market="CME_EQUITY", at="2026-10-17T15:00:00Z")
    assert r["state"] == "closed"
    assert r["next_open"]["local"].startswith("2026-10-18T17:00")


def test_eurex_asian_hours():
    r = get("/v1/is-open", market="EUREX_INDEX", at="2026-10-20T00:30:00Z")  # 02:30 CEST
    assert r["is_open"]


def test_six_closed_christmas_eve_and_new_years_eve():
    r = get("/v1/holidays", market="XSWX", start="2026-12-20", end="2027-01-05")
    closed = {d["date"] for d in r["closed_days"]}
    assert {"2026-12-24", "2026-12-25", "2026-12-31", "2027-01-01"} <= closed


def test_errors():
    assert c.get("/v1/is-open", params={"market": "FOO"}).status_code == 404
    assert c.get("/v1/is-open", params={"market": "XNYS", "at": "2026-10-20T15:00:00"}).status_code == 400
