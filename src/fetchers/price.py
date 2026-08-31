import os
from datetime import datetime, timedelta, timezone

import requests
import yfinance as yf

from config.settings import GOLD_TICKER, DXY_TICKER, US10Y_TICKER

# Silver is priced from gold-api.com — true spot XAG/USD, not a futures
# contract (see claude/website-roadmap.md for why: SI=F/yfinance and two
# other free sources were tried and rejected/failed before this one was
# verified with real live API calls on 2026-08-31). Gold/DXY/US10Y stay on
# yfinance — only silver's instrument mismatch was ever in question.
_GOLD_API_BASE = "https://api.gold-api.com"


def _gold_api_key() -> str:
    key = os.environ.get("GOLD_API_KEY")
    if not key:
        raise RuntimeError(
            "GOLD_API_KEY is not set — required for spot XAG/USD previous-close "
            "and history (the live price itself needs no key). See README.md."
        )
    return key


def _parse_updated_at(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fetch_ohlc(symbol: str, start_ts: int, end_ts: int) -> dict:
    resp = requests.get(
        f"{_GOLD_API_BASE}/ohlc/{symbol}",
        params={"startTimestamp": start_ts, "endTimestamp": end_ts},
        headers={"x-api-key": _gold_api_key()},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _previous_close(symbol: str) -> float | None:
    """Yesterday's (UTC calendar day) close, via gold-api.com's /ohlc endpoint —
    used only to compute change/change_pct for the live price, since the
    free real-time endpoint returns a price with no change attached."""
    now = datetime.now(timezone.utc)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    data = _fetch_ohlc(symbol, int(start.timestamp()), int(end.timestamp()))
    close = data.get("close")
    return float(close) if close is not None else None


def fetch_silver_price() -> dict:
    """True spot XAG/USD. Live price: gold-api.com's free, no-auth,
    unrate-limited real-time endpoint. Change/change_pct: derived from a
    separate, key-gated call to yesterday's OHLC close (10 req/hour on the
    free tier — comfortably covers our ~hourly cadence)."""
    resp = requests.get(f"{_GOLD_API_BASE}/price/XAG", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    price = float(data["price"])
    quote_time = _parse_updated_at(data.get("updatedAt"))

    prev_close = _previous_close("XAG")
    if prev_close:
        change = price - prev_close
        change_pct = (change / prev_close) * 100
    else:
        change = 0.0
        change_pct = 0.0

    return {
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "quote_time": quote_time,
    }


def fetch_price(ticker: str) -> dict:
    fi = yf.Ticker(ticker).fast_info
    price = fi.last_price
    prev_close = fi.previous_close
    change = price - prev_close
    change_pct = (change / prev_close) * 100
    return {"ticker": ticker, "price": price, "change": change, "change_pct": change_pct}


def _fetch_price_safe(ticker: str) -> dict:
    try:
        return fetch_price(ticker)
    except Exception:
        return {"ticker": ticker, "price": 0.0, "change": 0.0, "change_pct": 0.0}


def fetch_gold_price() -> dict:
    return fetch_price(GOLD_TICKER)


def fetch_dxy_price() -> dict:
    return _fetch_price_safe(DXY_TICKER)


def fetch_us10y_price() -> dict:
    return _fetch_price_safe(US10Y_TICKER)


def fetch_silver_history(days: int = 30) -> list[dict]:
    """Daily spot XAG/USD series via gold-api.com's /history endpoint
    (key-gated, 10 req/hour free tier — one call per range, called at most
    once/day by update_daily.py, so nowhere near the cap).

    Returns the same [{"date": ..., "close": ...}] shape callers already
    expect (src/analysis/signals.py, build_metrics(), etc.) regardless of
    which aggregation field name gold-api.com's response actually uses —
    their docs show "max_price" for aggregation=max, so "avg_price" is the
    documented-but-not-live-verified name for aggregation=avg; this parses
    defensively across the plausible variants rather than hard-coding one.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days + 3)  # small buffer for weekends/holidays
    resp = requests.get(
        f"{_GOLD_API_BASE}/history",
        params={
            "symbol": "XAG",
            "startTimestamp": int(start.timestamp()),
            "endTimestamp": int(end.timestamp()),
            "groupBy": "day",
            "aggregation": "avg",
            "orderBy": "asc",
        },
        headers={"x-api-key": _gold_api_key()},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()

    _PRICE_KEYS = ("avg_price", "avgPrice", "price", "close", "max_price", "min_price")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_str = row.get("day") or row.get("date")
        price_val = None
        for key in _PRICE_KEYS:
            if row.get(key) is not None:
                price_val = row[key]
                break
        if date_str is None or price_val is None:
            continue
        out.append({"date": str(date_str)[:10], "close": float(price_val)})

    return out[-days:] if len(out) > days else out
