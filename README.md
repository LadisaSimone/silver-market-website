# Silver Market Intelligence — Website

A standalone website for Silver Market Intelligence, independent from the
`commodity-agent-silver` repo (which stays untouched, running the existing
Streamlit app). This repo started as a copy of the pieces it needs from
that project — the price/news fetchers, the scoring/summarizer logic, the
prompt files — plus new fetchers for data the original app doesn't pull
yet (real yield, COT positioning), and the website itself.

## Structure

- `main.py`, `config/`, `src/`, `prompts/` — the data pipeline (fetch
  prices/news, score with Claude, generate the daily briefing).
- `web/` — the site itself (added in the next step).

## Status

Backend pieces copied and fixed (2026-08-24):
- `src/agents/summarizer.py` — now persists `overall_label`, `ranked_drivers`,
  `dominant_category`, `weighted_explanation` (previously computed but discarded).
- `src/fetchers/price.py` — history fetch now supports up to a year (was
  capped at 40 days); added `fetch_silver_intraday()` for the 1D chart.
- `src/fetchers/real_yield.py`, `src/fetchers/cot.py` — new. Not yet
  network-verified (see their docstrings) — first real test is via the
  GitHub Action once it's wired up.

Not yet added: the `web/` site code itself, GitHub Actions workflows,
GitHub Pages setup.
