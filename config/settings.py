MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4000
SCORING_MAX_TOKENS = 1000
NARRATIVE_MAX_TOKENS = 3000  # narrative-only now that scoring is a separate stage
# TICKER (silver): back to SI=F/yfinance (COMEX futures) on 2026-08-31,
# 2nd revert — "XAGUSD=X" failed live in production with a 404 from
# Yahoo's own backend ("Quote not found for symbol: XAGUSD=X"), a
# different failure than the Twelve Data plan-restriction one before it.
# Two attempts at a free spot XAG/USD source have now failed in
# production; see claude/website-roadmap.md for the status before trying
# a third. The page labels this as "Silver (COMEX Futures)", not spot —
# see src/fetchers/price.py's fetch_silver_price().
TICKER = "SI=F"
GOLD_TICKER = "GC=F"
DXY_TICKER = "DX-Y.NYB"
US10Y_TICKER = "^TNX"
MAX_ARTICLES = 20
OUTPUTS_DIR = "outputs"
