import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from config.settings import MODEL, OUTPUTS_DIR
from src.analysis.signals import compute_price_signals, compute_data_quality, format_signals_for_prompt
from src.agents.summarizer import summarize, reattach_links
from src.fetchers.news import fetch_articles
from src.fetchers.price import (
    fetch_silver_price,
    fetch_gold_price,
    fetch_dxy_price,
    fetch_us10y_price,
    fetch_silver_history,
)

load_dotenv()


def _metals_snapshot(silver: dict, gold: dict) -> str:
    def fmt(p):
        sign = "+" if p["change"] >= 0 else ""
        return f"${p['price']:.2f}  {sign}{p['change']:.2f}  ({sign}{p['change_pct']:.2f}%)"

    ratio = gold["price"] / silver["price"]
    return (
        f"  Silver  (SI=F)  {fmt(silver)}\n"
        f"  Gold    (GC=F)  {fmt(gold)}\n"
        f"  Gold/Silver Ratio: {ratio:.1f}"
    )


def save_outputs(
    briefing: str,
    scores: dict,
    signals: dict,
    data_quality: dict,
    articles: list[dict],
    history: list[dict],
    silver: dict,
    gold: dict,
    dxy: dict,
    us10y: dict,
    today: str,
) -> None:
    out_dir = Path(OUTPUTS_DIR)
    out_dir.mkdir(exist_ok=True)

    daily_dir = out_dir / "daily" / today
    raw_dir = daily_dir / "raw"
    briefing_dir = daily_dir / "briefing"
    raw_dir.mkdir(parents=True, exist_ok=True)
    briefing_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / "prices.json").write_text(
        json.dumps({
            "silver": silver,
            "gold": gold,
            "dxy": dxy,
            "us10y": us10y,
            "ratio": round(gold["price"] / silver["price"], 1),
        }, indent=2)
    )
    (raw_dir / "news.json").write_text(json.dumps({"articles": articles}, indent=2))
    (raw_dir / "history.json").write_text(json.dumps(history, indent=2))
    (raw_dir / "signals.json").write_text(json.dumps(signals, indent=2))

    (briefing_dir / "briefing.txt").write_text(briefing)
    (briefing_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    metadata = {
        "date": today,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": MODEL,
        "articles_fetched": len(articles),
        "significant_move": signals["silver"]["significant_move"],
        "silver_change_pct": signals["silver"]["change_pct"],
        "data_reliability": data_quality["reliability"],
    }
    (daily_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # Flat backward-compat files for the dashboard
    (out_dir / f"briefing_{today}.txt").write_text(briefing)
    (out_dir / f"scores_{today}.json").write_text(json.dumps(scores, indent=2))


def print_briefing(briefing: str, silver: dict, gold: dict) -> None:
    today = date.today().strftime("%B %d, %Y")
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  SILVER MARKET INTELLIGENCE BRIEFING")
    print(f"  {today}")
    print(f"{sep}")
    print(f"\n  METALS SNAPSHOT")
    print(_metals_snapshot(silver, gold))
    print(f"\n{sep}\n")
    print(briefing)
    print(f"\n{sep}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force re-fetch all data, bypassing cache")
    args = parser.parse_args()

    today = date.today().isoformat()
    raw_dir = Path(OUTPUTS_DIR) / "daily" / today / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # ── Prices ────────────────────────────────────────────────────────────────
    prices_cache = raw_dir / "prices.json"
    if not args.force and prices_cache.exists():
        print("Loading prices from cache...")
        cached = json.loads(prices_cache.read_text())
        silver, gold, dxy, us10y = cached["silver"], cached["gold"], cached["dxy"], cached["us10y"]
    else:
        print("Fetching live metals prices...")
        silver = fetch_silver_price()
        gold = fetch_gold_price()
        dxy = fetch_dxy_price()
        us10y = fetch_us10y_price()

    # ── History ───────────────────────────────────────────────────────────────
    history_cache = raw_dir / "history.json"
    if not args.force and history_cache.exists():
        print("Loading history from cache...")
        history = json.loads(history_cache.read_text())
    else:
        print("Fetching 30-day price history...")
        history = fetch_silver_history(30)

    # ── News ──────────────────────────────────────────────────────────────────
    news_cache = raw_dir / "news.json"
    if not args.force and news_cache.exists():
        print("Loading news from cache...")
        articles = json.loads(news_cache.read_text())["articles"]
    else:
        print("Fetching silver news...")
        articles = fetch_articles()

    # ── Signals (always recompute — fast and free) ────────────────────────────
    print("Computing quantitative signals...")
    signals = compute_price_signals(silver, gold, dxy, us10y, history)
    data_quality = compute_data_quality(silver, gold, dxy, us10y)
    signals_text = format_signals_for_prompt(signals, data_quality)

    print(f"Found {len(articles)} articles. Generating briefing...")
    briefing, scores = summarize(
        articles,
        silver,
        gold,
        dxy,
        us10y,
        signals_text=signals_text,
        data_quality=data_quality,
    )

    # Explicitly reattach links before saving so the disk file contains markdown links.
    # (reattach_links is also called inside summarize(), but this makes the save-path explicit.)
    briefing = reattach_links(briefing, articles)

    print_briefing(briefing, silver, gold)
    print("Scores:", scores)

    save_outputs(briefing, scores, signals, data_quality, articles, history, silver, gold, dxy, us10y, today)
    print(f"Outputs saved to {OUTPUTS_DIR}/daily/{today}/ (+ flat compat files)")


if __name__ == "__main__":
    main()
