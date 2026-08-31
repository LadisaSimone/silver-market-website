MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4000
SCORING_MAX_TOKENS = 1000
NARRATIVE_MAX_TOKENS = 3000  # narrative-only now that scoring is a separate stage
GOLD_TICKER = "GC=F"
DXY_TICKER = "DX-Y.NYB"
US10Y_TICKER = "^TNX"
# Spot silver (XAG/USD) via Twelve Data — see src/fetchers/price.py and the
# "Setup" section of README.md for the TWELVEDATA_API_KEY secret this needs.
# Replaced the previous SI=F/yfinance COMEX-futures source: the site was
# labeling that as spot XAG/USD (false), and retail visitors reading "the
# silver price" mean spot, not the futures curve. Gold/DXY/US10Y stay on
# yfinance futures/indices — only the headline silver number needed a true
# spot source (see src/analysis/signals.py for the resulting gold-futures
# vs. silver-spot basis note on the Gold/Silver ratio).
TWELVEDATA_SILVER_SYMBOL = "XAG/USD"
MAX_ARTICLES = 20
OUTPUTS_DIR = "outputs"
