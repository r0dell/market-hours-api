"""HTTP-API für Börsen-Handelszeiten.

Start:  uvicorn app:app --port 8000
Doku:   http://localhost:8000/docs
"""
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

import engine

app = FastAPI(
    title="Market Hours API",
    version="0.1.0",
    description=(
        "Is an exchange open right now? When does it open or close next? "
        "Which days are holidays or early closes? Answers are computed by code "
        "from open-source exchange calendars plus own futures session tables. "
        "Every response names its timezone and data source."
    ),
)


def _run(fn, *args):
    try:
        return fn(*args)
    except engine.UnknownMarket as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/markets", summary="List supported markets")
def markets():
    return engine.list_markets()


@app.get("/v1/is-open", summary="Is the market open at a given time (default: now)?")
def is_open(
    market: str = Query(..., examples=["XNYS", "CME_EQUITY"]),
    at: Optional[datetime] = Query(None, description="ISO time with offset, e.g. 2026-11-27T15:00:00Z"),
):
    return _run(engine.status, market, at)


@app.get("/v1/next", summary="Next open and next close after a given time (default: now)")
def next_events(market: str, at: Optional[datetime] = None):
    m = _run(engine.get_market, market)
    res = _run(engine.next_events, market, at)
    return {"market": m.code, "timezone": m.tz, **res, "source": engine.source(m)}


@app.get("/v1/holidays", summary="Closed weekdays and early closes in a date range")
def holidays(market: str, start: str = Query(..., examples=["2026-11-01"]),
             end: str = Query(..., examples=["2026-12-31"])):
    return _run(engine.holidays, market, start, end)


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True, "data": engine.DATA_VERSION}
