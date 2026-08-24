import math

_RATIO_HISTORICAL_AVG = 65.0
_SIGNIFICANT_MOVE_THRESHOLD = 2.0


def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0.0) for c in changes]
    losses = [abs(min(c, 0.0)) for c in changes]

    # Seed with simple average over the first window
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing for the remainder
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _compute_volatility(closes: list[float]) -> float | None:
    if len(closes) < 2:
        return None
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    n = len(log_returns)
    mean = sum(log_returns) / n
    variance = sum((r - mean) ** 2 for r in log_returns) / (n - 1)
    return round(math.sqrt(variance) * math.sqrt(252) * 100, 1)


def _rsi_signal(rsi: float | None) -> str:
    if rsi is None:
        return "insufficient_data"
    if rsi < 30:
        return "oversold"
    if rsi > 70:
        return "overbought"
    return "neutral"


def _indicator_direction_signal(change_pct: float) -> tuple[str, str]:
    """Returns (direction, silver_signal) for DXY or US10Y.

    Both indicators move inverse to silver: rising → bearish, falling → bullish.
    Magnitude threshold: < 1% → mildly, >= 1% → strongly.
    """
    direction = "up" if change_pct >= 0 else "down"
    if change_pct == 0:
        return direction, "neutral"
    prefix = "strongly_" if abs(change_pct) >= 1.0 else "mildly_"
    bias = "bearish" if change_pct > 0 else "bullish"
    return direction, f"{prefix}{bias}_for_silver"


def _ratio_signal(ratio: float) -> str:
    if ratio > 67:
        return "silver_undervalued_vs_gold"
    if ratio < 63:
        return "silver_overvalued_vs_gold"
    return "neutral"


def compute_price_signals(
    silver: dict,
    gold: dict,
    dxy: dict,
    us10y: dict,
    history: list[dict],
) -> dict:
    """Pre-compute all quantitative signals from raw price dicts and 30-day history."""
    closes = [h["close"] for h in history]

    rsi = _compute_rsi(closes)
    volatility = _compute_volatility(closes)

    high_30d = max(closes) if closes else silver["price"]
    low_30d = min(closes) if closes else silver["price"]
    vs_30d_high_pct = round((silver["price"] / high_30d - 1) * 100, 1)
    vs_30d_low_pct = round((silver["price"] / low_30d - 1) * 100, 1)

    silver_change_pct = silver.get("change_pct", 0.0)
    significant_move = abs(silver_change_pct) >= _SIGNIFICANT_MOVE_THRESHOLD

    ratio_val = gold["price"] / silver["price"]

    dxy_change_pct = dxy.get("change_pct", 0.0)
    dxy_direction, dxy_signal = _indicator_direction_signal(dxy_change_pct)
    # DXY is an index — express bps as percentage × 100 (market convention)
    dxy_change_bps = round(dxy_change_pct * 100)

    us10y_change_pct = us10y.get("change_pct", 0.0)
    us10y_direction, us10y_signal = _indicator_direction_signal(us10y_change_pct)
    # US10Y is a yield — bps is the actual yield-point change × 100
    us10y_change_bps = round(us10y.get("change", 0.0) * 100)

    return {
        "silver": {
            "price": round(silver["price"], 2),
            "change": round(silver.get("change", 0.0), 2),
            "change_pct": round(silver_change_pct, 2),
            "direction": "up" if silver_change_pct >= 0 else "down",
            "significant_move": significant_move,
            "vs_30d_high_pct": vs_30d_high_pct,
            "vs_30d_low_pct": vs_30d_low_pct,
            "rsi_14": rsi,
            "signal": _rsi_signal(rsi),
            "volatility_30d": volatility,
        },
        "gold": {
            "price": round(gold["price"], 2),
            "change_pct": round(gold.get("change_pct", 0.0), 2),
            "direction": "up" if gold.get("change_pct", 0.0) >= 0 else "down",
        },
        "ratio": {
            "value": round(ratio_val, 1),
            "vs_historical_avg": round(ratio_val - _RATIO_HISTORICAL_AVG, 1),
            "signal": _ratio_signal(ratio_val),
        },
        "dxy": {
            "value": round(dxy.get("price", 0.0), 2),
            "change_pct": round(dxy_change_pct, 2),
            "change_bps": dxy_change_bps,
            "direction": dxy_direction,
            "signal": dxy_signal,
        },
        "us10y": {
            "value": round(us10y.get("price", 0.0), 2),
            "change_pct": round(us10y_change_pct, 2),
            "change_bps": us10y_change_bps,
            "direction": us10y_direction,
            "signal": us10y_signal,
        },
    }


def compute_data_quality(
    silver: dict,
    gold: dict,
    dxy: dict,
    us10y: dict,
) -> dict:
    """Classify available, partial, and missing data sources."""
    available = ["silver_price", "gold_price", "ratio"]
    if dxy and dxy.get("price", 0.0):
        available.append("dxy")
    if us10y and us10y.get("price", 0.0):
        available.append("us10y")
    available += ["rsi_14", "volatility"]

    partial = ["etf_flows_proxy"]
    missing = [
        "slv_actual_flows",
        "comex_inventory",
        "cot_positioning",
        "open_interest",
        "real_yields",
    ]

    core = {"silver_price", "gold_price", "dxy", "us10y"}
    core_present = len(core & set(available))
    if core_present >= 4:
        reliability = "MEDIUM"
        reliability_reason = "Core price data available, flow and positioning data absent"
    elif core_present >= 2:
        reliability = "LOW"
        reliability_reason = "Partial price data available, macro and positioning data absent"
    else:
        reliability = "LOW"
        reliability_reason = "Minimal data available"

    return {
        "available": available,
        "partial": partial,
        "missing": missing,
        "reliability": reliability,
        "reliability_reason": reliability_reason,
    }


def format_signals_for_prompt(signals: dict, data_quality: dict) -> str:
    """Return a pre-formatted text block for injection as {quantitative_signals}."""
    s = signals["silver"]
    g = signals["gold"]
    r = signals["ratio"]
    d = signals["dxy"]
    u = signals["us10y"]

    # Silver
    s_sign = "+" if s["change_pct"] >= 0 else ""
    rsi_str = ""
    if s["rsi_14"] is not None:
        rsi_str = f" | RSI {s['rsi_14']} ({s['signal'].upper()})"
    silver_line = (
        f"Silver: ${s['price']:,.2f} | {s_sign}{s['change_pct']:.2f}%"
        f"{rsi_str} | {s['vs_30d_high_pct']:+.1f}% vs 30d high"
    )

    # Gold
    g_sign = "+" if g["change_pct"] >= 0 else ""
    gold_line = f"Gold: ${g['price']:,.2f} | {g_sign}{g['change_pct']:.2f}%"

    # Ratio
    avg_diff = r["vs_historical_avg"]
    diff_str = f"+{avg_diff:.1f} above" if avg_diff >= 0 else f"{avg_diff:.1f} below"
    ratio_signal_str = r["signal"].replace("_", " ").upper()
    ratio_line = f"Ratio: {r['value']} | {diff_str} historical avg | Signal: {ratio_signal_str}"

    # DXY
    d_sign = "+" if d["change_pct"] >= 0 else ""
    dxy_signal_str = d["signal"].replace("_", " ").upper()
    dxy_line = (
        f"DXY: {d['value']} | {d_sign}{d['change_pct']:.2f}% ({d['change_bps']:+d}bps)"
        f" | Signal: {dxy_signal_str}"
    )

    # US10Y
    u10y_signal_str = u["signal"].replace("_", " ").upper()
    us10y_line = (
        f"US10Y: {u['value']:.2f}% | {u['change_bps']:+d}bps"
        f" | Signal: {u10y_signal_str}"
    )

    # Volatility (optional)
    vol_line = ""
    if s["volatility_30d"] is not None:
        vol_line = f"\nVolatility (30d annualized): {s['volatility_30d']}%"

    # Significant move
    move_flag = "YES" if s["significant_move"] else "NO"
    s_sign2 = "+" if s["change_pct"] >= 0 else ""
    cmp = ">" if s["significant_move"] else "<"
    sig_line = (
        f"Significant move detected: {move_flag} "
        f"({s_sign2}{s['change_pct']:.2f}% {cmp} 2% threshold)"
    )

    signals_block = (
        "QUANTITATIVE SIGNALS (pre-computed)\n"
        f"{silver_line}\n"
        f"{gold_line}\n"
        f"{ratio_line}\n"
        f"{dxy_line}\n"
        f"{us10y_line}"
        f"{vol_line}\n"
        f"{sig_line}"
    )

    # Data quality footer
    _avail_labels = {
        "silver_price": "Silver",
        "gold_price": "Gold",
        "ratio": "Ratio",
        "dxy": "DXY",
        "us10y": "US10Y",
        "rsi_14": "RSI",
        "volatility": "Volatility",
    }
    _partial_labels = {
        "etf_flows_proxy": "ETF flows (volume proxy only)",
    }
    _missing_labels = {
        "slv_actual_flows": "SLV Actual Flows",
        "comex_inventory": "COMEX Inventory",
        "cot_positioning": "COT",
        "open_interest": "Open Interest",
        "real_yields": "Real Yields",
    }

    avail_str = ", ".join(_avail_labels.get(k, k) for k in data_quality["available"])
    partial_str = ", ".join(_partial_labels.get(k, k) for k in data_quality["partial"])
    missing_str = ", ".join(_missing_labels.get(k, k) for k in data_quality["missing"])

    dq_block = (
        f"\nDATA QUALITY: {data_quality['reliability']}\n"
        f"✅ Available: {avail_str}\n"
        f"⚠ Partial: {partial_str}\n"
        f"❌ Missing: {missing_str}"
    )

    return signals_block + dq_block
