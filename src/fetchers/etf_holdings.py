"""SLV (iShares Silver Trust) total silver held — scraped from iShares' own
public product page, since no free official CSV/API endpoint was found for
this figure (unlike COMEX inventory, which has a direct exchange report).

NOTE: ishares.com could not be network-verified from the build environment
(egress there is allowlisted and ishares.com isn't on it). The scrape
target was confirmed by inspecting a real fetch of the live product page:
the "Key Facts" section contains a "Ounces in Trust" label immediately
followed by the figure (e.g. "Ounces in Trust ... 495,097,780.60 ... as of
Aug 24, 2026"), in plain HTML text — not JSON-LD, not a data-* attribute.
That makes this more fragile than comex.py or real_yield.py: it depends on
iShares' page copy staying "Ounces in Trust" and could break silently on a
page redesign. Parsing below fails safely (returns None) rather than
guessing, so a broken scrape shows "—" instead of a wrong number. The
first real run (GitHub Action, full internet access) is the actual
verification — check its logs and, if iShares changed the page, either
fix the regex or abandon this source rather than widen the pattern to
match something that isn't really the ounces figure.
"""
import re

import requests

_SLV_PRODUCT_URL = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"

# Matches "Ounces in Trust" followed (within a short window, across HTML
# tags/whitespace) by a comma-grouped number with 2 decimals, e.g.
# "495,097,780.60". Non-greedy + bounded window avoids accidentally
# matching a much later unrelated number on the page.
_OUNCES_RE = re.compile(
    r"Ounces\s+in\s+Trust.{0,200}?([\d,]{4,}\.\d{2})",
    re.IGNORECASE | re.DOTALL,
)
_ASOF_RE = re.compile(
    r"Ounces\s+in\s+Trust.{0,300}?as\s+of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE | re.DOTALL,
)


def fetch_slv_holdings() -> dict | None:
    """Total silver held by SLV, in troy ounces.

    Returns {"value_oz": float, "as_of": str | None}, or None if the page
    could not be fetched or the figure could not be located. Callers MUST
    treat None as "no data available" (display "—") — never fabricate a
    value.
    """
    try:
        resp = requests.get(
            _SLV_PRODUCT_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        html = resp.text

        match = _OUNCES_RE.search(html)
        if not match:
            raise ValueError('Could not locate "Ounces in Trust" figure on SLV product page')

        value = float(match.group(1).replace(",", ""))

        as_of_match = _ASOF_RE.search(html)
        as_of = as_of_match.group(1) if as_of_match else None

        return {"value_oz": value, "as_of": as_of}
    except Exception as e:
        print(f"SLV ETF holdings fetch/parse failed, leaving as unavailable: {e}")
        return None
