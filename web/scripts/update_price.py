"""Fast refresh for web/data.json — price + intraday chart only.

Runs every ~15-30 min (GitHub Actions cron, see .github/workflows/update-price.yml).
Read-modify-write: only price/intraday/updated_at are touched, so this
never clobbers the once-daily outlook/drivers/metrics/stories written
by update_daily.py.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.fetchers.price import fetch_silver_price, fetch_silver_intraday  # noqa: E402

DATA_JSON = REPO_ROOT / "web" / "data.json"

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None


def _as_of_string() -> str:
    now = datetime.now(_ET) if _ET else datetime.now(timezone.utc)
    try:
        return now.strftime("%-I:%M %p ET" if _ET else "%H:%M UTC")
    except ValueError:
        # %-I isn't supported on every platform; fall back to zero-padded.
        return now.strftime("%I:%M %p ET" if _ET else "%H:%M UTC")


def main() -> None:
    print("Fetching live silver price...")
    silver = fetch_silver_price()

    print("Fetching intraday bars...")
    intraday = fetch_silver_intraday()

    existing = {}
    if DATA_JSON.exists():
        existing = json.loads(DATA_JSON.read_text())

    existing["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing["price"] = {
        "value": round(silver["price"], 2),
        "change": round(silver.get("change", 0.0), 2),
        "change_pct": round(silver.get("change_pct", 0.0), 2),
        "as_of": _as_of_string(),
    }
    if intraday:
        # Empty means markets are closed / yfinance has no bars yet today —
        # keep whatever intraday series is already on disk rather than
        # wiping the chart to nothing.
        existing["intraday"] = intraday

    DATA_JSON.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"Wrote {DATA_JSON}")


if __name__ == "__main__":
    main()
