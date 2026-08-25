"""Renders docs/index.html from docs/index.template.html + docs/data.json.

Called at the end of both update_daily.py and update_price.py, each time
they finish writing data.json, so the static HTML always reflects
whatever is currently in data.json — regardless of which of the two
scripts last ran.

Why this exists: docs/index.html's price/outlook values used to only
ever be filled in client-side by script.js after a fetch("data.json").
That meant search crawlers and any JS-less fetch of the page saw "—"
and "Loading today's briefing…" instead of real content. This module
pre-renders those same values into the HTML at build time; script.js
still overwrites them on page load for live-updating users, so the
JS-enabled experience is unchanged.

docs/index.html is now a GENERATED file — do not hand-edit it directly.
Structural/copy changes to the page go in docs/index.template.html.
"""
import html
import math
from pathlib import Path

RING_CIRCUMFERENCE = 2 * math.pi * 60  # r=60, matches docs/styles.css

_SENTIMENT_COLOR = {"bearish": "#ff4d5e", "neutral": "#f5a623"}
_SENTIMENT_CLASS = {"bearish": "is-bearish", "neutral": "is-neutral"}


def _fmt_signed(n, decimals: int = 2) -> str:
    if n is None:
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{n:.{decimals}f}"


def render_index_html(data: dict, repo_root: Path) -> None:
    template_path = repo_root / "docs" / "index.template.html"
    output_path = repo_root / "docs" / "index.html"
    page = template_path.read_text()

    price = data.get("price") or {}
    outlook = data.get("outlook") or {}

    if price.get("value") is not None:
        price_value = f"${price['value']:.2f}"
    else:
        price_value = "—"

    if price.get("change") is not None:
        price_change = f"{_fmt_signed(price['change'])} ({_fmt_signed(price.get('change_pct'))}%)"
        price_change_class = "price-change " + ("is-up" if (price.get("change") or 0) >= 0 else "is-down")
    else:
        price_change = "—"
        price_change_class = "price-change"

    price_asof = f"As of {price['as_of']}" if price.get("as_of") else ""

    score = outlook.get("score")
    has_score = isinstance(score, (int, float))
    score_number = str(score) if has_score else "—"
    score_clamped = max(0, min(10, score if has_score else 0))
    ring_offset = RING_CIRCUMFERENCE * (1 - score_clamped / 10)
    sentiment = outlook.get("sentiment", "")
    ring_color = _SENTIMENT_COLOR.get(sentiment, "#22c55e")
    outlook_label = outlook.get("label") or "—"
    outlook_label_class = "outlook-label " + _SENTIMENT_CLASS.get(sentiment, "")
    outlook_summary = outlook.get("summary") or "No briefing available yet."
    outlook_updated = outlook.get("updated_at") or ""

    replacements = {
        "{{PRICE_VALUE}}": price_value,
        "{{PRICE_CHANGE}}": price_change,
        "{{PRICE_CHANGE_CLASS}}": price_change_class,
        "{{PRICE_ASOF}}": price_asof,
        "{{SCORE_NUMBER}}": score_number,
        "{{RING_OFFSET}}": f"{ring_offset:.2f}",
        "{{RING_COLOR}}": ring_color,
        "{{OUTLOOK_LABEL}}": outlook_label,
        "{{OUTLOOK_LABEL_CLASS}}": outlook_label_class,
        "{{OUTLOOK_SUMMARY}}": outlook_summary,
        "{{OUTLOOK_UPDATED}}": outlook_updated,
    }
    for token, value in replacements.items():
        page = page.replace(token, html.escape(str(value), quote=True))

    output_path.write_text(page)
    print(f"Wrote {output_path}")
