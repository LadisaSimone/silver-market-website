"""Fast refresh for docs/data.json — price + intraday chart only.

Runs hourly, best-effort (GitHub Actions cron, see .github/workflows/update-price.yml —
that file explains why this is hourly rather than the every-30-min it used to be).
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
from src.render_static import render_index_html  # noqa: E402

DATA_JSON = REPO_ROOT / "docs" / "data.json"

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None


def _as_of_string(intraday: list[dict] | None = None) -> str:
    # Prefer the timestamp of the most recent actual traded bar (from the
    # exchange data we already fetched, at zero extra API cost) over our
    # own script wall-clock time. If the exchange feed is delayed or the
    # fetch itself is the thing lagging, wall-clock time would falsely
    # read as "just refreshed" — the last real bar's time shows the true
    # data freshness instead, so a stuck feed is visible on the page
    # rather than hidden behind a script-run timestamp.
    if intraday:
        last_t = intraday[-1].get("t", "")
        try:
            hh, mm = last_t.split(":")
            hour = int(hh) % 24
            suffix = "AM" if hour < 12 else "PM"
            hour12 = hour % 12 or 12
            return f"{hour12}:{mm} {suffix} ET"
        except (ValueError, AttributeError):
            pass  # fall through to wall-clock time below

    now = datetime.now(_ET) if _ET else datetime.now(timezone.utc)
    try:
        return now.strftime("%-I:%M %p ET" if _ET else "%H:%M UTC")
    except ValueError:
        # %-I isn't supported on every platform; fall back to zero-padded.
        return now.strftime("%I:%M %p ET" if _ET else "%H:%M UTC")


def main() -> None:
    existing = {}
    if DATA_JSON.exists():
        existing = json.loads(DATA_JSON.read_text())

    try:
        print("Fetching live silver price...")
        silver = fetch_silver_price()

        print("Fetching intraday bars...")
        intraday = fetch_silver_intraday()
    except Exception as exc:
        # A transient yfinance/Yahoo failure must NOT crash before any
        # write (which would just leave yesterday's file untouched anyway)
        # and must NOT overwrite good data with zeros. Leave docs/data.json
        # exactly as-is and exit non-zero so this shows up as a FAILED run
        # in the GitHub Actions tab — previously an exception here looked
        # identical to "nothing changed," so a broken feed could go stale
        # for hours with an all-green run history and no visible signal.
        print(f"ERROR: price fetch failed, leaving existing price data untouched: {exc}")
        sys.exit(1)

    existing["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing["price"] = {
        "value": round(silver["price"], 2),
        "change": round(silver.get("change", 0.0), 2),
        "change_pct": round(silver.get("change_pct", 0.0), 2),
        "as_of": _as_of_string(intraday),
    }
    if intraday:
        # Empty means markets are closed / yfinance has no bars yet today —
        # keep whatever intraday series is already on disk rather than
        # wiping the chart to nothing.
        existing["intraday"] = intraday

    DATA_JSON.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"Wrote {DATA_JSON}")

    render_index_html(existing, REPO_ROOT)


if __name__ == "__main__":
    main()
