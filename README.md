# Silver Market Intelligence — Website

A standalone website for Silver Market Intelligence, independent from the
`commodity-agent-silver` repo (which stays untouched, running the existing
Streamlit app). This repo started as a copy of the pieces it needs from
that project — the price/news fetchers, the scoring/summarizer logic, the
prompt files — plus new fetchers for data the original app doesn't pull
yet (real yield, COT positioning), and the website itself.

## Structure

- `main.py`, `config/`, `src/`, `prompts/` — the data pipeline (fetch
  prices/news, score with Claude, generate the daily briefing). `main.py`
  is a manual-run CLI kept for reference; the live site does **not** shell
  out to it (see `docs/scripts/`).
- `docs/` — the site itself: `index.html` + `styles.css` + `script.js`
  (one responsive page, mobile-first with a desktop breakpoint) reading
  `docs/data.json`, plus `docs/scripts/` (the two jobs that keep
  `data.json` fresh) and ad placeholder slots (leaderboard, in-content,
  160×600 desktop sidebar).
- `.github/workflows/` — the two schedules that run those scripts and
  commit `docs/data.json` back to the repo.

## How the site stays live

`docs/data.json` is the single source of truth `script.js` renders from.
Two scripts keep it current, each owning a different, non-overlapping
slice of the file so they never clobber each other:

- **`docs/scripts/update_price.py`** — every 30 min
  (`.github/workflows/update-price.yml`). Fetches the live silver price
  and today's intraday bars. Updates `price` + `intraday` only.
- **`docs/scripts/update_daily.py`** — once/day, ~9:30 AM ET
  (`.github/workflows/update-daily.yml`). Runs the full pipeline (prices,
  30-day history, news, quantitative signals, the two-stage Claude
  scoring + briefing call, real yield, COT positioning) and updates
  `outlook` + `drivers` + `metrics` + `stories` + `history`.

Both workflows commit straight to `main` with the `GITHUB_TOKEN` GitHub
Actions already provides — no extra setup needed for that part. They
share a `concurrency` group so they can never race each other on
`docs/data.json`.

## Setup still needed before this is fully live

1. **Add the `ANTHROPIC_API_KEY` secret** — Settings → Secrets and
   variables → Actions → New repository secret. Only `update-daily.yml`
   needs it (the Claude scoring/briefing call).
2. **Enable GitHub Pages** — Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, folder: `/docs`.
3. **First real run** — trigger both workflows manually once
   (Actions tab → select workflow → "Run workflow") and check the logs.
   `real_yield.py` (FRED) and `cot.py` (CFTC) were written defensively
   because their endpoints couldn't be network-verified from the build
   environment — this is the actual first test of both. If either fails,
   its function already degrades gracefully (returns `None`/`"—"`
   values rather than crashing the run) — see their docstrings for what
   to check in the logs.

## Status (2026-08-24)

Backend pieces copied and fixed:
- `src/agents/summarizer.py` — persists `overall_label`, `ranked_drivers`,
  `dominant_category`, `weighted_explanation` (previously computed but discarded).
- `src/fetchers/price.py` — history fetch supports up to a year; added
  `fetch_silver_intraday()` for the 1D chart.
- `src/fetchers/real_yield.py`, `src/fetchers/cot.py` — new, not yet
  network-verified (see above).

Site code, orchestration scripts, and GitHub Actions workflows are
written and locally tested (data flow verified with representative fake
data; layout verified at mobile and desktop widths). Not yet done: the
three setup steps above, and confirming the real yield/COT fetchers
against live data once a workflow actually runs with internet access.
