MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4000
SCORING_MAX_TOKENS = 1000
NARRATIVE_MAX_TOKENS = 3000  # narrative-only now that scoring is a separate stage
# TICKER (silver): reverted to SI=F/yfinance (COMEX futures) on 2026-08-31
# after a Twelve Data spot XAG/USD attempt failed in production — their
# free tier doesn't include commodities (needs the paid "Grow" plan). The
# site labels this as "Silver (COMEX Futures)", not spot — see
# src/fetchers/price.py's fetch_silver_price() for the full history and
# claude/website-roadmap.md for the status of finding a genuinely free
# spot source.
TICKER = "SI=F"
GOLD_TICKER = "GC=F"
DXY_TICKER = "DX-Y.NYB"
US10Y_TICKER = "^TNX"
MAX_ARTICLES = 20
OUTPUTS_DIR = "outputs"
