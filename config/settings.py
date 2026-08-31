MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4000
SCORING_MAX_TOKENS = 1000
NARRATIVE_MAX_TOKENS = 3000  # narrative-only now that scoring is a separate stage
# TICKER (silver): trying yfinance's "XAGUSD=X" — Yahoo's own spot silver
# quote (currency-cross style, distinct from the "SI=F" futures contract
# used before) — as of 2026-08-31, after a Twelve Data spot XAG/USD
# attempt failed in production (their free tier doesn't include
# commodities). This reuses the same fetch_price()/fetch_silver_history()/
# fetch_silver_intraday() code as SI=F did, just a different ticker
# string, so it's cheap to try and cheap to revert — but like SI=F, it's
# still Yahoo's undocumented, no-SLA quote feed, not a source with
# published terms. If fast_info doesn't populate cleanly for this ticker
# (untestable without a live run — see claude/website-roadmap.md), revert
# TICKER to "SI=F" and the page's "Silver (XAG/USD)" label back to
# "Silver (COMEX Futures)" (docs/index.template.html, src/render_static.py).
TICKER = "XAGUSD=X"
GOLD_TICKER = "GC=F"
DXY_TICKER = "DX-Y.NYB"
US10Y_TICKER = "^TNX"
MAX_ARTICLES = 20
OUTPUTS_DIR = "outputs"
