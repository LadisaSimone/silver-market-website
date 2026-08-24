"""Real (TIPS) 10-year yield — FRED series DFII10.

FRED publishes the market-derived real yield directly (10-Year Treasury
Inflation-Indexed Security, Constant Maturity), so no breakeven-inflation
subtraction is needed. Free, no API key.

NOTE: this endpoint could not be network-verified from the build
environment (egress there is allowlisted and fred.stlouisfed.org isn't
on it) or from the requesting Mac's sandboxed shell for this project.
It should work as documented, but the parsing below is written
defensively and the first real run (e.g. via the GitHub Action, which
has full internet access) is the actual verification — check its logs
after the first run and adjust `_parse` if the CSV shape differs from
what's assumed here.
"""
import requests

_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10"


def _parse(csv_text: str) -> dict:
    lines = [l for l in csv_text.strip().splitlines() if l.strip()]
    if len(lines) < 3:
        raise ValueError("Unexpected FRED response: too few rows")

    # Expected header: "DATE,DFII10" (or similar) — locate the value column
    # by position (second column) rather than assuming an exact header name.
    rows = [l.split(",") for l in lines[1:]]
    values = [(r[0], r[1]) for r in rows if len(r) >= 2 and r[1] not in ("", ".")]
    if len(values) < 2:
        raise ValueError("Not enough non-missing FRED observations")

    (latest_date, latest), (_, prev) = values[-1], values[-2]
    latest, prev = float(latest), float(prev)
    return {
        "value": round(latest, 2),
        "change": round(latest - prev, 2),
        "as_of": latest_date,
    }


def fetch_real_yield() -> dict:
    try:
        resp = requests.get(_FRED_CSV_URL, timeout=10)
        resp.raise_for_status()
        return _parse(resp.text)
    except Exception:
        return {"value": None, "change": None, "as_of": None}
