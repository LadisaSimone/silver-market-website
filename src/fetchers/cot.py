"""CFTC Commitments of Traders — COMEX Silver non-commercial (speculative)
net-long positioning, from the Legacy Futures-Only report.

Downloads CFTC's own published single-year zip directly (no third-party
package — the well-known `cot_reports` PyPI package wraps this same
download in ~15 lines, but it also failed to build in this project's
sandbox environment on a setuptools incompatibility, so it's inlined
here instead for one less fragile dependency).

Published weekly (Fridays, for the prior Tuesday's positioning) — this
will lag the rest of the dashboard, which refreshes daily. Label it
accordingly wherever it's displayed.

NOTE: cftc.gov could not be network-verified from the build environment
or the requesting Mac's sandboxed shell (both are on an allowlisted
egress with cftc.gov not on it). Column names below are CFTC's
well-documented Legacy report field names, matched with flexible
substring search rather than an exact hardcoded name, specifically so a
minor naming difference doesn't hard-fail. The GitHub Action (full
internet access) is the real first test — check its logs after the
first scheduled/manual run.
"""
import io
import zipfile
from datetime import date

import pandas as pd
import requests

_MARKET_NAME_HINT = "SILVER"
_EXCHANGE_HINT = "COMMODITY EXCHANGE"  # COMEX's legal name in CFTC's data


def _cot_zip_url(year: int) -> str:
    return f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"


def _find_col(columns, must_contain: list[str]) -> str | None:
    for col in columns:
        lowered = col.lower().replace(" ", "_")
        if all(term in lowered for term in must_contain):
            return col
    return None


def _load_year(year: int) -> pd.DataFrame:
    resp = requests.get(_cot_zip_url(year), timeout=20)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # annual.txt is the standard filename cftc.gov uses for the
        # single-year Legacy Futures-Only extract.
        name = next((n for n in z.namelist() if n.lower().endswith(".txt")), None)
        if name is None:
            raise ValueError("No .txt file found in CFTC zip")
        with z.open(name) as f:
            return pd.read_csv(f, low_memory=False)


def fetch_silver_cot() -> dict:
    try:
        year = date.today().year
        df = _load_year(year)

        name_col = _find_col(df.columns, ["market_and_exchange"]) or _find_col(df.columns, ["market"])
        date_col = _find_col(df.columns, ["report_date"]) or _find_col(df.columns, ["as_of_date"])
        long_col = _find_col(df.columns, ["noncommercial", "long"]) or _find_col(df.columns, ["non", "comm", "long"])
        short_col = _find_col(df.columns, ["noncommercial", "short"]) or _find_col(df.columns, ["non", "comm", "short"])
        if not all([name_col, date_col, long_col, short_col]):
            raise ValueError(f"Could not locate expected columns in CFTC data: {list(df.columns)[:10]}...")

        mask = df[name_col].astype(str).str.upper().str.contains(_MARKET_NAME_HINT) & \
            df[name_col].astype(str).str.upper().str.contains(_EXCHANGE_HINT)
        silver = df[mask].sort_values(date_col)
        if len(silver) < 1:
            raise ValueError("No COMEX Silver rows found in CFTC data")

        latest = silver.iloc[-1]
        net_long = int(latest[long_col]) - int(latest[short_col])

        change = None
        if len(silver) >= 2:
            prev = silver.iloc[-2]
            prev_net = int(prev[long_col]) - int(prev[short_col])
            change = net_long - prev_net

        return {
            "net_long": net_long,
            "change": change,
            "as_of": str(latest[date_col])[:10],
        }
    except Exception:
        return {"net_long": None, "change": None, "as_of": None}
