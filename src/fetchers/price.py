import yfinance as yf
from config.settings import TICKER, GOLD_TICKER, DXY_TICKER, US10Y_TICKER


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


def fetch_silver_price() -> dict:
    return fetch_price(TICKER)


def fetch_gold_price() -> dict:
    return fetch_price(GOLD_TICKER)


def fetch_dxy_price() -> dict:
    return _fetch_price_safe(DXY_TICKER)


def fetch_us10y_price() -> dict:
    return _fetch_price_safe(US10Y_TICKER)


def fetch_silver_history(days: int = 30) -> list[dict]:
    # Period chosen to comfortably cover the requested `days`; existing
    # callers passing days=30 keep the exact same "40d" behavior as before.
    if days <= 40:
        period = "40d"
    elif days <= 185:
        period = "6mo"
    else:
        period = "1y"
    hist = yf.Ticker(TICKER).history(period=period)
    closes = hist["Close"].dropna().tail(days)
    return [
        {"date": idx.strftime("%Y-%m-%d"), "close": float(val)}
        for idx, val in zip(closes.index, closes.values)
    ]


def fetch_silver_intraday(interval: str = "15m") -> list[dict]:
    """Today's intraday silver price bars, for a 1D chart view.

    Returns [] outside market hours / on days yfinance has no intraday
    bars yet (e.g. right after a fresh trading session opens) — callers
    should fall back to the last daily close in that case.
    """
    hist = yf.Ticker(TICKER).history(period="1d", interval=interval)
    closes = hist["Close"].dropna()
    return [
        {"t": idx.strftime("%H:%M"), "p": float(val)}
        for idx, val in zip(closes.index, closes.values)
    ]
