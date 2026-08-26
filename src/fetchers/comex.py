"""COMEX Silver registered warehouse stocks — CME Group's own daily report.

Downloads CME Group's own "Daily Metal Stocks Report" for silver directly
from the exchange (no third-party aggregator, no API key).

NOTE: cmegroup.com could not be network-verified from the build environment
(egress there is allowlisted and cmegroup.com isn't on it) or from the
requesting Mac's sandboxed shell for this project — same situation as
real_yield.py and cot.py before their first live run. The report's exact
column layout is based on CME Group's publicly documented "Daily Metal
Stocks Report" format (one row per licensed depository, with
Registered/Eligible/Total ounce columns, plus a grand-total row), but this
has NOT been visually confirmed against a real downloaded copy of the file.
Parsing below is written defensively (locates the header row and the total
row by text content, not fixed positions) so a minor layout difference
doesn't hard-fail — but a real layout mismatch could still cause
fetch_comex_inventory() to return None. That's the intended failure mode:
update_daily.py must treat None as "no data" and show "—", never guess a
number. The first real run (GitHub Action, full internet access) is the
actual verification — check its logs after the first run and adjust
`_parse` below if the report shape differs from what's assumed here.
"""
import io

import requests

_COMEX_STOCKS_URL = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"


def _num(v) -> float | None:
    try:
        s = str(v).replace(",", "").strip()
        if not s or s.upper() == "NAN":
            return None
        return float(s)
    except (TypeError, ValueError):
        return None


def _parse(xls_bytes: bytes) -> dict:
    import pandas as pd

    # Read raw, no assumed header row — CME's report has a title/date
    # block above the real header, so header position isn't fixed.
    df = pd.read_excel(io.BytesIO(xls_bytes), engine="xlrd", header=None)

    def _row_text(i: int) -> str:
        return " ".join(str(v) for v in df.iloc[i].tolist() if str(v) != "nan").upper()

    total_row = None
    for i in range(len(df)):
        if "TOTAL" in _row_text(i):
            total_row = i  # keep the LAST "TOTAL" row — the grand total,
            # not a per-depository subtotal that happens to also say total.

    if total_row is None:
        raise ValueError("Could not locate a TOTAL row in COMEX stocks report")

    header_row = None
    for i in range(max(0, total_row - 20), total_row):
        text = _row_text(i)
        if "REGISTERED" in text or "ELIGIBLE" in text:
            header_row = i

    if header_row is None:
        raise ValueError("Could not locate a header row (REGISTERED/ELIGIBLE) in COMEX stocks report")

    headers = [str(v).strip().upper() for v in df.iloc[header_row].tolist()]

    def _find_col(name: str):
        for idx, h in enumerate(headers):
            if name in h:
                return idx
        return None

    registered_col = _find_col("REGISTERED")
    eligible_col = _find_col("ELIGIBLE")
    total_col = _find_col("TOTAL")

    total_row_vals = df.iloc[total_row].tolist()
    registered = _num(total_row_vals[registered_col]) if registered_col is not None else None
    eligible = _num(total_row_vals[eligible_col]) if eligible_col is not None else None
    total = _num(total_row_vals[total_col]) if total_col is not None else None

    # Prefer Registered ounces (the figure most commonly quoted as "COMEX
    # Inventory" / deliverable supply) but fall back to Total if that
    # specific column isn't found.
    value = registered if registered is not None else total
    if value is None:
        raise ValueError("Could not extract a numeric total from COMEX stocks report")

    return {"registered_oz": registered, "eligible_oz": eligible, "total_oz": total, "value_oz": value}


def fetch_comex_inventory() -> dict | None:
    """Registered COMEX silver warehouse stocks, in troy ounces.

    Returns {"registered_oz", "eligible_oz", "total_oz", "value_oz"}, or
    None if the report could not be fetched or parsed. Callers MUST treat
    None as "no data available" (display "—") — never fabricate a value.
    """
    try:
        resp = requests.get(
            _COMEX_STOCKS_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        return _parse(resp.content)
    except Exception as e:
        print(f"COMEX inventory fetch/parse failed, leaving as unavailable: {e}")
        return None
