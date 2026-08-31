"""Fast refresh for docs/data.json — price + intraday chart only.

Runs hourly, best-effort (GitHub Actions cron, see .github/workflows/update-price.yml —
that file explains why this is hourly rather than the every-30-min it used to be).
Read-modify-write: only price/intraday/updated_at are touched, so this
never clobbers the once-daily outlook/drivers/metrics/stories written
by update_daily.py.

Requires GOLD_API_KEY in the environment (GitHub Actions secret) — see
src/fetchers/price.py and README.md. (The live price call itself needs no
key; fetch_silver_price() also fetches yesterday's close to compute
change/change_pct, and that call is key-gated.)

Intraday (1D chart) bars are self-recorded here rather than fetched from a
separate endpoint: gold-api.com's free tier only exposes hourly-grouped
history on its paid plan, so each hourly run appends its own live-price
reading as one bar (see _update_intraday()). This also means the 1D chart
is now genuinely spot XAG/USD, consistent with the headline price — it
just starts sparse after a fresh deploy and fills in over the first few
runs of the day.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.fetchers.price import fetch_silver_price  # noqa: E402
from src.render_static import render_index_html  # noqa: E402

DATA_JSON = REPO_ROOT / "docs" / "data.json"

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None


def _as_of_string(quote_time=None, intraday: list[dict] | None = None) -> str:
    # Preference order, most trustworthy first:
    #   1. quote_time — the real timestamp gold-api.com returned with the
    #      quote itself (fetch_silver_price()'s "quote_time"). This is the
    #      actual answer to "when was this price quoted," not a proxy.
    #   2. The most recent intraday bar's time — a fallback for when the
    #      API didn't return a timestamp; still real market data, just one
    #      step removed from the quote endpoint itself.
    #   3. Our own wall-clock time — last resort, and the least honest one
    #      (it says when *we* ran, not when the price was actually true).
    # Whichever is used, the point is the same as before: a stuck feed
    # must show up as a stale "As of" on the page, not a falsely-fresh one.
    if quote_time is not None:
        try:
            local = quote_time.astimezone(_ET) if _ET else quote_time
            try:
                return local.strftime("%-I:%M %p ET" if _ET else "%H:%M UTC")
            except ValueError:
                return local.strftime("%I:%M %p ET" if _ET else "%H:%M UTC")
        except Exception:
            pass  # fall through

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


def _update_intraday(existing: dict, price: float, quote_time) -> list[dict]:
    """Append today's live price as one more intraday bar, resetting the
    series when the calendar day (ET) rolls over. This is how the 1D chart
    gets real spot XAG/USD bars without a second, key-gated API call —
    see the module docstring."""
    now_et = quote_time.astimezone(_ET) if (_ET and quote_time) else datetime.now(_ET or timezone.utc)
    today_str = now_et.strftime("%Y-%m-%d")

    intraday = list(existing.get("intraday") or []) if existing.get("intraday_date") == today_str else []
    t_label = now_et.strftime("%H:%M")
    point = {"t": t_label, "p": round(price, 2)}
    if intraday and intraday[-1].get("t") == t_label:
        intraday[-1] = point
    else:
        intraday.append(point)

    existing["intraday_date"] = today_str
    return intraday


def main() -> None:
    existing = {}
    if DATA_JSON.exists():
        existing = json.loads(DATA_JSON.read_text())

    try:
        print("Fetching live silver price...")
        silver = fetch_silver_price()
    except Exception as exc:
        # A transient gold-api.com failure (rate limit, network blip, bad/
        # missing key) must NOT crash before any write (which would just leave the
        # existing file untouched anyway) and must NOT overwrite good data
        # with zeros. Leave docs/data.json exactly as-is and exit non-zero
        # so this shows up as a FAILED run in the GitHub Actions tab —
        # previously an exception here looked identical to "nothing
        # changed," so a broken feed could go stale for hours with an
        # all-green run history and no visible signal.
        print(f"ERROR: price fetch failed, leaving existing price data untouched: {exc}")
        sys.exit(1)

    intraday = _update_intraday(existing, silver["price"], silver.get("quote_time"))

    existing["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing["price"] = {
        "value": round(silver["price"], 2),
        "change": round(silver.get("change", 0.0), 2),
        "change_pct": round(silver.get("change_pct", 0.0), 2),
        "as_of": _as_of_string(silver.get("quote_time"), intraday),
    }
    existing["intraday"] = intraday

    DATA_JSON.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"Wrote {DATA_JSON}")

    render_index_html(existing, REPO_ROOT)


if __name__ == "__main__":
    main()
