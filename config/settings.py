MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4000
SCORING_MAX_TOKENS = 1000
NARRATIVE_MAX_TOKENS = 3000  # narrative-only now that scoring is a separate stage
# Silver is no longer priced via yfinance/SI=F (COMEX futures). As of
# 2026-08-31 it's sourced from gold-api.com's true spot XAG/USD endpoints
# (verified live, free tier — see src/fetchers/price.py's fetch_silver_price()
# and fetch_silver_history()). That's the 3rd attempt at a free spot source;
# the first two (Twelve Data, Yahoo's XAGUSD=X) failed live in production —
# see claude/website-roadmap.md for the full history. Requires a
# GOLD_API_KEY secret (see README.md) for previous-close and history calls;
# the live headline price itself needs no key.
GOLD_TICKER = "GC=F"
DXY_TICKER = "DX-Y.NYB"
US10Y_TICKER = "^TNX"
MAX_ARTICLES = 20
OUTPUTS_DIR = "outputs"
