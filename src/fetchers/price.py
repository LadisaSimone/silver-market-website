import os
from datetime import datetime, timezone

import requests
import yfinance as yf

from config.settings import GOLD_TICKER, DXY_TICKER, US10Y_TICKER, TWELVEDATA_SILVER_SYMBOL

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None

_TWELVEDATA_BASE_URL = "https://api.twelvedata.com"


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


def _twelvedata_api_key() -> str:
    key = os.environ.get("TWELVEDATA_API_KEY")
    if not key:
        raise RuntimeError(
            "TWELVEDATA_API_KEY is not set — required for spot silver "
            "(XAG/USD) pricing. Add it as a GitHub Actions secret; see "
            "README.md for setup."
        )
    return key


def _twelvedata_get(endpoint: str, params: dict) -> dict:
    """GET against the Twelve Data REST API, raising on any failure.

    Twelve Data can return HTTP 200 with an error payload
    (e.g. {"status": "error", "message": "..."}) rather than a non-2xx
    status code, so both failure modes are checked explicitly — relying
    on response.raise_for_status() alone would silently accept an error
    body as if it were real price data.
    """
    full_params = {**params, "apikey": _twelvedata_api_key()}
    resp = requests.get(f"{_TWELVEDATA_BASE_URL}/{endpoint}", params=full_params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error on /{endpoint}: {data.get('message', data)}")
    return data


def fetch_silver_price() -> dict:
    """Spot silver (XAG/USD) via Twelve Data's /quote endpoint.

    Returns the same {ticker, price, change, change_pct} shape the rest of
    the pipeline (src/analysis/signals.py, docs/scripts/*.py) already
    expects from fetch_price(), plus "quote_time": a tz-aware UTC datetime
    for when this quote was actually taken (or None if Twelve Data didn't
    return one) — this is the true source for the site's "As of" text,
    better than the wall-clock/intraday-bar approximations used before a
    real API timestamp was available.
    """
    data = _twelvedata_get("quote", {"symbol": TWELVEDATA_SILVER_SYMBOL})
    price = float(data["close"])
    prev_close = float(data["previous_close"])
    change = float(data["change"]) if data.get("change") is not None else (price - prev_close)
    if data.get("percent_change") is not None:
        change_pct = float(data["percent_change"])
    else:
        change_pct = (change / prev_close) * 100 if prev_close else 0.0

    quote_time = None
    ts = data.get("timestamp")
    if ts is not None:
        try:
            quote_time = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            quote_time = None

    return {
        "ticker": TWELVEDATA_SILVER_SYMBOL,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "quote_time": quote_time,
    }


def fetch_gold_price() -> dict:
    return fetch_price(GOLD_TICKER)


def fetch_dxy_price() -> dict:
    return _fetch_price_safe(DXY_TICKER)


def fetch_us10y_price() -> dict:
    return _fetch_price_safe(US10Y_TICKER)


def _twelvedata_series(interval: str, outputsize: int) -> list[dict]:
    # timezone=America/New_York so every "datetime" comes back already in
    # ET — the site labels every timestamp "ET" (price-asof, as_of, chart
    # axes); XAG/USD has no single home exchange the way SI=F did, so this
    # has to be requested explicitly rather than assumed.
    data = _twelvedata_get(
        "time_series",
        {
            "symbol": TWELVEDATA_SILVER_SYMBOL,
            "interval": interval,
            "outputsize": outputsize,
            "order": "asc",
            "timezone": "America/New_York",
        },
    )
    values = data.get("values") or []
    return [{"datetime": v["datetime"], "close": float(v["close"])} for v in values]


def fetch_silver_history(days: int = 30) -> list[dict]:
    bars = _twelvedata_series("1day", days)
    return [{"date": b["datetime"][:10], "close": b["close"]} for b in bars]


def fetch_silver_intraday(interval: str = "15min") -> list[dict]:
    """Today's intraday spot silver bars (ET), for the 1D chart view.

    Twelve Data has no "period=1d" shortcut the way yfinance did, so this
    pulls a rolling window of recent bars (enough to comfortably cover a
    full trading day at 15-min resolution) and keeps only bars whose ET
    calendar date matches today. Returns [] when nothing from today is in
    the window yet (e.g. right after midnight ET) — same contract as
    before, so update_price.py's "keep the existing chart" fallback still
    applies unchanged.
    """
    bars = _twelvedata_series(interval, 100)
    now_et = datetime.now(_ET) if _ET else datetime.now(timezone.utc)
    today = now_et.strftime("%Y-%m-%d")
    todays_bars = [b for b in bars if b["datetime"].startswith(today)]
    return [{"t": b["datetime"][11:16], "p": b["close"]} for b in todays_bars]
