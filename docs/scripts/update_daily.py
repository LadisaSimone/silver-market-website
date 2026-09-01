"""Daily refresh for docs/data.json — outlook, drivers, metrics, stories, history.

Runs once/day (GitHub Actions cron, see .github/workflows/update-daily.yml).
Deliberately does NOT shell out to main.py — main.py is kept only as a
reference/manual-run CLI. This script imports the same pipeline pieces
directly and writes straight into the site's data.json, in the exact
shape script.js (docs/script.js) expects.

Read-modify-write: only the fields owned by this script are touched
(outlook, drivers, metrics, stories, history, updated_at). price/intraday
are owned by update_price.py's faster, roughly-hourly cadence and are left alone
here so the two schedules never clobber each other.

Requires ANTHROPIC_API_KEY and GOLD_API_KEY in the environment (GitHub
Actions secrets) — the latter for fetch_silver_history()'s spot XAG/USD
history calls, see src/fetchers/price.py and README.md.
"""
import json
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.fetchers.price import (  # noqa: E402
    fetch_silver_price,
    fetch_gold_price,
    fetch_dxy_price,
    fetch_us10y_price,
    fetch_silver_history,
)
from src.fetchers.news import fetch_articles  # noqa: E402
from src.fetchers.real_yield import fetch_real_yield  # noqa: E402
from src.fetchers.cot import fetch_silver_cot  # noqa: E402
from src.fetchers.etf_holdings import fetch_slv_holdings  # noqa: E402
from src.analysis.signals import (  # noqa: E402
    compute_price_signals,
    compute_data_quality,
    format_signals_for_prompt,
)
from src.agents.summarizer import summarize  # noqa: E402
from src.render_static import render_index_html  # noqa: E402

DATA_JSON = REPO_ROOT / "docs" / "data.json"
METRICS_HISTORY_JSON = REPO_ROOT / "docs" / "metrics_history.json"

_CATEGORY_ICON = {
    "macro": "bank",
    "technicals": "trend",
    "sentiment": "people",
    "etf_flows": "flows",
    "industrial_demand": "industry",
}
_CATEGORY_LABEL = {
    "macro": "Macro Backdrop",
    "technicals": "Technical Setup",
    "sentiment": "News Sentiment",
    "etf_flows": "ETF Flow Signal",
    "industrial_demand": "Industrial Demand",
}


def _status_for_score(score) -> str:
    if score is None:
        return "neutral"
    if score >= 6:
        return "supportive"
    if score <= 4:
        return "risk"
    return "neutral"


def _display_name(name: str) -> str:
    # Claude is prompted to return driver names as free text; titlecase
    # anything that came back fully uppercase so it doesn't look shouty
    # next to the category-derived fallback labels.
    return name.title() if name.isupper() else name


def build_drivers(final_scores: dict) -> list[dict]:
    drivers = []
    seen_categories = set()
    score_reasoning = final_scores.get("score_reasoning") or {}

    for d in (final_scores.get("ranked_drivers") or [])[:3]:
        category = d.get("category", "")
        score = final_scores.get(category)
        drivers.append({
            "label": _display_name(d.get("name", category or "Driver")),
            "status": _status_for_score(score),
            "icon": _CATEGORY_ICON.get(category, "flows"),
            # Ranked drivers always carry their own AI-written reasoning
            # (prompts/scoring.txt ranked_drivers[].reasoning) — this covers
            # the "data"-category case too (e.g. Gold/Silver Ratio), which
            # has no numeric score but does have its own reasoning sentence.
            "reason": d.get("reasoning", ""),
        })
        if category:
            seen_categories.add(category)

    # Fill in any of the 5 scoring categories not already represented by
    # a ranked driver, so all dimensions stay visible on the site.
    for category, label in _CATEGORY_LABEL.items():
        if category in seen_categories:
            continue
        drivers.append({
            "label": label,
            "status": _status_for_score(final_scores.get(category)),
            "icon": _CATEGORY_ICON[category],
            # From score_reasoning (prompts/scoring.txt) — one grounded
            # sentence per category, tied to that category's own score.
            "reason": score_reasoning.get(category, ""),
        })

    return drivers


def build_outlook(final_scores: dict) -> dict:
    overall = final_scores.get("overall", 5)
    label_raw = (final_scores.get("overall_label") or "NEUTRAL").upper()

    if label_raw == "BULLISH":
        sentiment = "bullish"
        label = f"{'Strongly' if overall >= 8 else 'Moderately'} Bullish"
    elif label_raw == "BEARISH":
        sentiment = "bearish"
        label = f"{'Strongly' if overall <= 3 else 'Moderately'} Bearish"
    else:
        sentiment = "neutral"
        label = "Neutral"

    return {
        "score": overall,
        "label": label,
        "sentiment": sentiment,
        "summary": final_scores.get("verdict", "No briefing available yet."),
        "watch": final_scores.get("verdict_watch", ""),
        # Explicit "snapshot" framing + the caveat, not just a timestamp —
        # this sits right next to the live price card, which updates far
        # more often, so without this it reads as describing the same
        # instant. See docs/styles.css .outlook-updated for the badge
        # styling that also sets this apart visually.
        "updated_at": "Snapshot from 9:00 AM ET — may differ from live price",
    }


def _time_ago(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if secs < 0:
            secs = 0
        if secs < 3600:
            return f"{max(1, int(secs // 60))}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    except Exception:
        return ""


def build_stories(articles: list[dict], limit: int = 5) -> list[dict]:
    stories = []
    for a in articles[:limit]:
        summary = (a.get("description") or "").strip()
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "..."
        stories.append({
            "title": a.get("title", ""),
            "summary": summary,
            "time_ago": _time_ago(a.get("date", "")),
            "url": a.get("url") or "#",
        })
    return stories


_RSI_SIGNAL_LABEL = {
    "oversold": "Oversold",
    "overbought": "Overbought",
    "neutral": "Neutral",
}


def build_metrics(
    signals: dict,
    history: list[dict],
    real_yield: dict,
    cot: dict,
    etf: dict | None = None,
) -> list[dict]:
    dxy = signals["dxy"]
    us10y = signals["us10y"]
    ratio = signals["ratio"]
    silver = signals["silver"]

    etf_oz = etf.get("value_oz") if etf else None
    etf_as_of = etf.get("as_of") if etf else None

    metrics = [
        {
            "label": "DXY (USD)",
            "value": f"{dxy['value']:.2f}",
            "change": f"{dxy['change_pct']:+.2f}%",
            "direction": dxy["direction"],
        },
        {
            "label": "US 10Y Yield",
            "value": f"{us10y['value']:.2f}%",
            "change": f"{us10y['change_bps'] / 100:+.2f}",
            "direction": us10y["direction"],
        },
        {
            "label": "Real Yield",
            "value": f"{real_yield['value']:.2f}%" if real_yield.get("value") is not None else "—",
            "change": f"{real_yield['change']:+.2f}" if real_yield.get("change") is not None else "",
            "direction": "down" if (real_yield.get("change") or 0) < 0 else "up",
        },
        {
            "label": "Gold/Silver",
            "value": f"{ratio['value']}",
            "change": "",
            "direction": "up",
        },
        {
            "label": "RSI (14)",
            "value": f"{silver['rsi_14']:.0f}" if silver.get("rsi_14") is not None else "—",
            "change": "",
            "direction": "up" if (silver.get("rsi_14") or 50) >= 50 else "down",
            "note": _RSI_SIGNAL_LABEL.get(silver.get("signal"), ""),
        },
        {
            "label": "COT Net-Long",
            "value": f"{cot['net_long']:,}" if cot.get("net_long") is not None else "—",
            "change": f"{cot['change']:+,}" if cot.get("change") is not None else "",
            "direction": "down" if (cot.get("change") or 0) < 0 else "up",
            "note": "Weekly (CFTC)",
        },
        {
            "label": "ETF Holdings",
            "value": f"{etf_oz / 1_000_000:.1f}M oz" if etf_oz is not None else "—",
            "change": "",
            "direction": "up",
            "note": (f"SLV, as of {etf_as_of}" if etf_as_of else "SLV") if etf_oz is not None else "",
        },
    ]

    pct_1m = None
    if len(history) >= 2 and history[0].get("close"):
        pct_1m = (history[-1]["close"] / history[0]["close"] - 1) * 100
    metrics.append({
        "label": "1M % Change",
        "value": f"{pct_1m:+.2f}%" if pct_1m is not None else "—",
        "change": "",
        "direction": "down" if (pct_1m or 0) < 0 else "up",
    })

    return metrics


def append_metrics_history(date_str: str, metrics: list[dict], path: Path) -> None:
    """Append today's Key Metrics snapshot to a running JSON array so past
    values can be pulled later (e.g. for a trend chart), rather than being
    overwritten every day the way docs/data.json's "metrics" field is.

    Keyed by date: if this function runs twice for the same date (e.g. a
    manual re-run), that day's entry is replaced, not duplicated. Each
    entry stores exactly what build_metrics() produced, including any "—"
    placeholders — so a gap in history is visible as a gap, not silently
    smoothed over.
    """
    history = []
    if path.exists():
        try:
            history = json.loads(path.read_text())
        except (json.JSONDecodeError, ValueError):
            history = []

    history = [h for h in history if h.get("date") != date_str]
    history.append({"date": date_str, "metrics": metrics})
    history.sort(key=lambda h: h["date"])

    path.write_text(json.dumps(history, indent=2) + "\n")
    print(f"Wrote {path} ({len(history)} day(s) of history)")


def main() -> None:
    try:
        print("Fetching prices...")
        silver = fetch_silver_price()
        gold = fetch_gold_price()
        dxy = fetch_dxy_price()
        us10y = fetch_us10y_price()

        print("Fetching price history (1W/1M/3M/1Y)...")
        history = fetch_silver_history(30)
        history_1w = fetch_silver_history(5)
        history_3m = fetch_silver_history(65)
        history_1y = fetch_silver_history(252)
    except Exception as exc:
        # Same reasoning as update_price.py: a gold-api.com failure here
        # (bad/missing GOLD_API_KEY, rate limit, network blip) must
        # not proceed into a Claude API call (real cost) with bad silver
        # data, and must not touch docs/data.json — this runs before the
        # file is even loaded, so nothing to leave untouched yet, but exit
        # clearly rather than crashing on some later line with a
        # confusing traceback about a downstream symptom.
        print(f"ERROR: price/history fetch failed, aborting before any Claude API call: {exc}")
        sys.exit(1)

    print("Fetching news...")
    articles = fetch_articles()

    print("Computing signals...")
    signals = compute_price_signals(silver, gold, dxy, us10y, history)
    data_quality = compute_data_quality(silver, gold, dxy, us10y)
    signals_text = format_signals_for_prompt(signals, data_quality)

    print(f"Scoring + generating briefing from {len(articles)} articles...")
    _briefing, final_scores = summarize(
        articles, silver, gold, dxy, us10y,
        signals_text=signals_text, data_quality=data_quality,
    )

    print("Fetching real yield + COT positioning...")
    real_yield = fetch_real_yield()
    cot = fetch_silver_cot()

    print("Fetching ETF holdings...")
    etf = fetch_slv_holdings()

    existing = {}
    if DATA_JSON.exists():
        existing = json.loads(DATA_JSON.read_text())

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing["history"] = {
        "1W": history_1w,
        "1M": history,
        "3M": history_3m,
        "1Y": history_1y,
    }
    existing["outlook"] = build_outlook(final_scores)
    existing["drivers"] = build_drivers(final_scores)
    existing["stories"] = build_stories(articles)
    existing["metrics"] = build_metrics(signals, history, real_yield, cot, etf)
    # price/intraday are intentionally left untouched — update_price.py owns them.

    append_metrics_history(today_str, existing["metrics"], METRICS_HISTORY_JSON)

    DATA_JSON.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"Wrote {DATA_JSON}")

    render_index_html(existing, REPO_ROOT)


if __name__ == "__main__":
    main()
