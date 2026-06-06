"""Institutional-Grade 8-Pillar Alpha Scoring Engine.

Produces an Alpha Score (0-100), Confidence Score (0-100), and a BUY/HOLD/SELL
verdict for each stock based on 8 analysis pillars:

    1. Trend         (20%) — EMA alignment, Supertrend, ADX
    2. Momentum      (15%) — RSI zone, MACD histogram, Stochastic RSI
    3. Volume        (12%) — Relative volume, delivery proxy, volume breakout
    4. Volatility    (10%) — ATR regime, Bollinger position, squeeze detection
    5. Market Structure (13%) — S/R position, breakout/breakdown
    6. Relative Strength (10%) — Sector RS, stock-vs-Nifty RS
    7. Institutional  (10%) — Smart money (OBV/CMF), accumulation/distribution
    8. News Sentiment (10%) — FinBERT score from existing pipeline

Usage:
    from app.services.institutional_scorer import score_stock, run_institutional_scan
    result = score_stock(symbol, df, profile, sector_rs, news_score)
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf

from app.services import market_data, technicals
from app.services.supabase_store import get_client
from app.services.sector_rs import (
    get_today_market_context,
    _normalize_sector,
)


# ---------------------------------------------------------------------------
# Pillar Weights — calibrated for institutional-grade signal quality
# ---------------------------------------------------------------------------

PILLAR_WEIGHTS = {
    "trend": 0.20,
    "momentum": 0.15,
    "volume": 0.12,
    "volatility": 0.10,
    "market_structure": 0.13,
    "relative_strength": 0.10,
    "institutional": 0.10,
    "news_sentiment": 0.10,
}


# ---------------------------------------------------------------------------
# Individual Pillar Scorers (0-100 each)
# ---------------------------------------------------------------------------


def _score_trend(df: pd.DataFrame, close: pd.Series) -> dict:
    """Pillar 1: Trend — EMA alignment + Supertrend + ADX."""
    score = 50.0
    details = {}

    # EMA alignment
    ema = technicals.compute_ema_alignment(close)
    details["ema"] = ema
    alignment_score = ema.get("trend_strength", 50.0)

    # Supertrend
    st = technicals.compute_supertrend(df)
    details["supertrend"] = st
    st_score = 70.0 if st["trend"] == "bullish" else 30.0
    if st.get("flipped"):
        st_score += 15 if st["trend"] == "bullish" else -15

    # ADX (from existing regime function)
    regime = technicals.get_market_regime(df)
    details["regime"] = regime
    adx = regime.get("adx", 0.0)
    adx_score = 50.0
    if adx > 25:
        adx_score = 75.0 if regime["regime"] == "uptrend" else 25.0
    elif adx > 20:
        adx_score = 60.0 if regime["regime"] != "downtrend" else 35.0

    # Weighted combination: EMA 40%, Supertrend 35%, ADX 25%
    score = alignment_score * 0.40 + st_score * 0.35 + adx_score * 0.25
    score = max(0.0, min(100.0, score))

    return {"score": round(score, 1), "details": details}


def _score_momentum(close: pd.Series) -> dict:
    """Pillar 2: Momentum — RSI + MACD + Stochastic RSI."""
    score = 50.0
    details = {}

    # RSI
    rsi = technicals._rsi(close, 14)
    details["rsi"] = round(rsi, 2) if rsi else None
    rsi_score = 50.0
    if rsi is not None:
        if 45 <= rsi <= 65:
            rsi_score = 80.0  # Sweet spot
        elif 35 <= rsi < 45:
            rsi_score = 65.0  # Recovering
        elif rsi < 30:
            rsi_score = 55.0  # Oversold bounce potential
        elif 65 < rsi <= 75:
            rsi_score = 55.0  # Strong but cooling
        elif rsi > 75:
            rsi_score = 25.0  # Overbought

    # MACD
    macd_line, signal_line = technicals._macd(close)
    details["macd"] = round(macd_line, 4) if macd_line else None
    details["macd_signal"] = round(signal_line, 4) if signal_line else None
    macd_score = 50.0
    if macd_line is not None and signal_line is not None:
        if macd_line > signal_line and macd_line > 0:
            macd_score = 85.0  # Bullish above zero
        elif macd_line > signal_line:
            macd_score = 65.0  # Bullish below zero (early)
        elif macd_line < signal_line and macd_line < 0:
            macd_score = 15.0  # Bearish below zero
        elif macd_line < signal_line:
            macd_score = 35.0  # Bearish above zero (weakening)
        # MACD histogram direction
        macd_hist = macd_line - signal_line
        details["macd_histogram"] = round(macd_hist, 4)

    # Stochastic RSI
    stoch = technicals.compute_stochastic_rsi(close)
    details["stochastic_rsi"] = stoch
    stoch_score = 50.0
    if stoch["zone"] == "oversold":
        stoch_score = 70.0  # Bounce potential
        if stoch["bullish_cross"]:
            stoch_score = 90.0
    elif stoch["zone"] == "overbought":
        stoch_score = 25.0
        if stoch["bearish_cross"]:
            stoch_score = 10.0
    else:
        stoch_score = 55.0 if stoch["stoch_k"] > stoch["stoch_d"] else 45.0

    # Weighted: RSI 40%, MACD 35%, Stoch RSI 25%
    score = rsi_score * 0.40 + macd_score * 0.35 + stoch_score * 0.25
    score = max(0.0, min(100.0, score))

    return {"score": round(score, 1), "details": details}


def _score_volume(df: pd.DataFrame) -> dict:
    """Pillar 3: Volume — Relative volume + delivery proxy + breakout volume."""
    score = 50.0
    details = {}

    # Relative volume
    vol_conf = technicals.get_volume_confirmation(df)
    details["volume_confirmation"] = vol_conf
    vol_score = 50.0
    if vol_conf["strong"]:
        vol_score = 90.0
    elif vol_conf["confirmed"]:
        vol_score = 75.0
    elif vol_conf["volume_ratio"] > 1.0:
        vol_score = 55.0
    else:
        vol_score = 35.0

    # Delivery volume proxy
    delivery = technicals.compute_delivery_volume_proxy(df)
    details["delivery_proxy"] = delivery
    delivery_score = delivery.get("smart_volume_score", 50)

    # Weighted: Relative vol 60%, Delivery proxy 40%
    score = vol_score * 0.60 + delivery_score * 0.40
    score = max(0.0, min(100.0, score))

    return {"score": round(score, 1), "details": details}


def _score_volatility(df: pd.DataFrame, close: pd.Series) -> dict:
    """Pillar 4: Volatility — ATR regime + Bollinger Bands."""
    score = 50.0
    details = {}

    # ATR
    atr_levels = technicals.get_atr_levels(df, float(close.iloc[-1]))
    details["atr"] = atr_levels
    atr_score = 60.0 if atr_levels else 50.0  # ATR calculable = enough data

    # Bollinger Bands
    bb = technicals.compute_bollinger_bands(close)
    details["bollinger_bands"] = bb
    bb_score = 50.0
    if bb["squeeze"]:
        bb_score = 75.0  # Squeeze = upcoming breakout potential
    if bb["zone"] == "below_lower":
        bb_score = 70.0  # Oversold bounce
    elif bb["zone"] == "above_upper":
        bb_score = 25.0  # Overbought extension
    elif bb["percent_b"] is not None:
        # Sweet spot: %B between 0.2 and 0.8
        pct_b = bb["percent_b"]
        if 0.2 <= pct_b <= 0.8:
            bb_score = 65.0
        elif pct_b < 0.2:
            bb_score = 55.0  # Near lower band
        else:
            bb_score = 40.0  # Near upper band

    # Weighted: ATR 40%, Bollinger 60%
    score = atr_score * 0.40 + bb_score * 0.60
    score = max(0.0, min(100.0, score))

    return {"score": round(score, 1), "details": details}


def _score_market_structure(df: pd.DataFrame) -> dict:
    """Pillar 5: Market Structure — S/R levels + breakout/breakdown."""
    score = 50.0
    details = {}

    # Key levels
    levels = technicals.get_key_levels(df)
    details["key_levels"] = levels

    # Breakout/breakdown detection
    bb_detection = technicals.detect_breakout_breakdown(df)
    details["breakout_breakdown"] = bb_detection

    status = bb_detection["status"]
    if status == "breakout":
        score = 85.0 if bb_detection["volume_confirmed"] else 65.0
    elif status == "near_breakout":
        score = 70.0
    elif status == "retest_support":
        score = 65.0  # Healthy retest
    elif status == "breakdown":
        score = 15.0 if bb_detection["volume_confirmed"] else 30.0
    elif status == "retest_resistance":
        score = 35.0  # Resistance rejection
    else:
        # Range-bound: check S/R proximity
        if not levels.get("target_blocked"):
            score = 55.0
        else:
            score = 35.0  # Target blocked by resistance

    score = max(0.0, min(100.0, score))
    return {"score": round(score, 1), "details": details}


def _score_relative_strength(
    close: pd.Series,
    sector_rs: dict | None = None,
    nifty_close: pd.Series | None = None,
) -> dict:
    """Pillar 6: Relative Strength — sector RS + stock RS vs Nifty."""
    score = 50.0
    details = {}

    # Sector RS (from cached market context)
    sector_score = 50.0
    if sector_rs:
        details["sector_rs"] = sector_rs
        status = sector_rs.get("status", "neutral")
        if status == "leading":
            sector_score = 90.0
        elif status == "outperforming":
            sector_score = 72.0
        elif status == "neutral":
            sector_score = 50.0
        elif status == "lagging":
            sector_score = 20.0

    # Stock RS vs Nifty
    stock_rs = technicals.compute_stock_rs_vs_nifty(close, nifty_close)
    details["stock_rs"] = stock_rs
    stock_score = 50.0
    rs_val = stock_rs.get("rs_score", 1.0)
    if rs_val > 1.10:
        stock_score = 90.0
    elif rs_val > 1.05:
        stock_score = 75.0
    elif rs_val > 0.95:
        stock_score = 50.0
    elif rs_val > 0.90:
        stock_score = 30.0
    else:
        stock_score = 15.0

    # Weighted: Sector 50%, Stock 50%
    score = sector_score * 0.50 + stock_score * 0.50
    score = max(0.0, min(100.0, score))

    return {"score": round(score, 1), "details": details}


def _score_institutional(df: pd.DataFrame) -> dict:
    """Pillar 7: Institutional Activity — smart money (OBV/CMF)."""
    score = 50.0
    details = {}

    smart_money = technicals.get_smart_money_signals(df)
    details["smart_money"] = smart_money

    signal = smart_money.get("signal", "neutral")
    cmf = smart_money.get("cmf", 0.0)
    obv_trend = smart_money.get("obv_trend", "flat")

    if signal == "accumulation":
        score = 85.0
        if cmf > 0.20:
            score = 92.0
    elif signal == "distribution":
        score = 15.0
        if smart_money.get("bearish_divergence"):
            score = 8.0  # Very dangerous
    else:
        # Neutral — use CMF for finer grade
        if cmf > 0.05:
            score = 62.0
        elif cmf < -0.05:
            score = 38.0
        else:
            score = 50.0

    score = max(0.0, min(100.0, score))
    return {"score": round(score, 1), "details": details}


def _score_news_sentiment(news_score: float) -> dict:
    """Pillar 8: News Sentiment — FinBERT or default 50.0."""
    # news_score is already 0-100 from the existing pipeline
    return {"score": round(max(0.0, min(100.0, news_score)), 1), "details": {}}


# ---------------------------------------------------------------------------
# Alpha Score + Confidence Score + Verdict
# ---------------------------------------------------------------------------


def _compute_alpha_score(pillar_scores: dict[str, float]) -> float:
    """Weighted sum of all 8 pillar scores → Alpha Score (0-100)."""
    alpha = 0.0
    for pillar, weight in PILLAR_WEIGHTS.items():
        alpha += pillar_scores.get(pillar, 50.0) * weight
    return round(max(0.0, min(100.0, alpha)), 1)


def _compute_confidence_score(pillar_scores: dict[str, float], pillar_details: dict) -> float:
    """Confidence = how many pillars confirm the signal direction.

    Base: 40
    Each pillar > 60 adds points (bullish confirmation)
    Cross-pillar synergies add bonus:
      - Trend + Momentum > 70 each → +5
      - Volume + Breakout > 70 each → +5
      - Institutional + Volume > 70 each → +5
    Capped at 95.
    """
    confidence = 40.0

    # Count confirming pillars
    bullish_pillars = [p for p, s in pillar_scores.items() if s > 60]
    bearish_pillars = [p for p, s in pillar_scores.items() if s < 40]

    # Each bullish confirmation adds points
    for p in bullish_pillars:
        s = pillar_scores[p]
        if s > 80:
            confidence += 8
        elif s > 70:
            confidence += 6
        else:
            confidence += 4

    # Each bearish pillar reduces confidence
    for p in bearish_pillars:
        s = pillar_scores[p]
        if s < 20:
            confidence -= 6
        elif s < 30:
            confidence -= 4
        else:
            confidence -= 2

    # Cross-pillar synergy bonuses
    if pillar_scores.get("trend", 0) > 70 and pillar_scores.get("momentum", 0) > 70:
        confidence += 5
    if pillar_scores.get("volume", 0) > 70 and pillar_scores.get("market_structure", 0) > 70:
        confidence += 5
    if pillar_scores.get("institutional", 0) > 70 and pillar_scores.get("volume", 0) > 70:
        confidence += 5

    # Penalty for conflicting signals
    if len(bullish_pillars) >= 3 and len(bearish_pillars) >= 2:
        confidence -= 10  # Mixed signals = lower confidence

    return round(max(0.0, min(95.0, confidence)), 1)


def _compute_verdict(alpha: float, confidence: float, pillar_scores: dict) -> str:
    """Determine BUY / HOLD / SELL verdict."""
    trend = pillar_scores.get("trend", 50)
    momentum = pillar_scores.get("momentum", 50)

    if alpha >= 65 and confidence >= 60 and trend >= 55:
        return "BUY"
    elif alpha < 40 or (trend < 35 and momentum < 35):
        return "SELL"
    else:
        return "HOLD"


def _compute_trade_levels(
    price: float,
    df: pd.DataFrame,
    alpha: float,
    pillar_details: dict,
) -> dict:
    """Compute Entry, Stop Loss, Target 1, Target 2, Risk-Reward."""
    if price <= 0:
        return {
            "entry": 0, "stop_loss": 0,
            "target_1": 0, "target_2": 0, "risk_reward": 0,
        }

    # ATR-based levels (preferred)
    atr_data = pillar_details.get("volatility", {}).get("details", {}).get("atr")
    if atr_data:
        sl = atr_data["stop_loss"]
        t1 = atr_data["target_price"]
        # Target 2 = 1.5x the distance of Target 1
        t1_dist = t1 - price
        t2 = round(price + t1_dist * 1.5, 2)
        sl_dist = price - sl
        rr = round(t1_dist / sl_dist, 2) if sl_dist > 0 else 0
    else:
        # Fallback: percentage-based
        volatility_pct = 3.0  # default 3%
        bb = pillar_details.get("volatility", {}).get("details", {}).get("bollinger_bands", {})
        if bb and bb.get("bandwidth"):
            volatility_pct = min(8.0, max(2.0, bb["bandwidth"] / 3))

        sl = round(price * (1 - volatility_pct / 100 * 2), 2)
        t1 = round(price * (1 + volatility_pct / 100 * 5), 2)
        t2 = round(price * (1 + volatility_pct / 100 * 7.5), 2)
        sl_dist = price - sl
        rr = round((t1 - price) / sl_dist, 2) if sl_dist > 0 else 0

    return {
        "entry": round(price, 2),
        "stop_loss": sl,
        "target_1": t1,
        "target_2": t2,
        "risk_reward": rr,
    }


def _generate_reasoning(
    symbol: str,
    alpha: float,
    confidence: float,
    verdict: str,
    pillar_scores: dict,
    pillar_details: dict,
    trade_levels: dict,
) -> str:
    """Generate concise institutional-quality reasoning."""
    display = symbol.replace(".NS", "").replace(".BO", "")
    parts = [f"{display} — Alpha {alpha:.0f}/100, Confidence {confidence:.0f}%"]

    # Trend
    trend_detail = pillar_details.get("trend", {}).get("details", {})
    ema = trend_detail.get("ema", {})
    st = trend_detail.get("supertrend", {})
    if ema.get("alignment") == "bullish":
        parts.append("EMA stack bullish (20>50>200)")
    elif ema.get("alignment") == "bearish":
        parts.append("EMA stack bearish")
    if st.get("trend") == "bullish":
        if st.get("flipped"):
            parts.append("Supertrend JUST flipped bullish ⚡")
        else:
            parts.append("Supertrend bullish")

    # Momentum
    mom_detail = pillar_details.get("momentum", {}).get("details", {})
    rsi_val = mom_detail.get("rsi")
    if rsi_val:
        parts.append(f"RSI {rsi_val:.1f}")
    stoch = mom_detail.get("stochastic_rsi", {})
    if stoch.get("bullish_cross"):
        parts.append("Stoch RSI bullish cross ⚡")
    elif stoch.get("zone") == "oversold":
        parts.append("Stoch RSI oversold (bounce setup)")

    # Volume
    vol_detail = pillar_details.get("volume", {}).get("details", {})
    vc = vol_detail.get("volume_confirmation", {})
    if vc.get("strong"):
        parts.append(f"Volume {vc['volume_ratio']:.1f}x avg (strong)")
    elif vc.get("confirmed"):
        parts.append(f"Volume confirmed {vc['volume_ratio']:.1f}x avg")

    # Market structure
    ms_detail = pillar_details.get("market_structure", {}).get("details", {})
    bb = ms_detail.get("breakout_breakdown", {})
    if bb.get("status") == "breakout":
        parts.append(f"BREAKOUT above ₹{bb['level']:.0f}" if bb.get("level") else "Breakout")
    elif bb.get("status") == "near_breakout":
        parts.append(f"Near breakout at ₹{bb['level']:.0f}" if bb.get("level") else "Near breakout")

    # Institutional
    inst_detail = pillar_details.get("institutional", {}).get("details", {})
    sm = inst_detail.get("smart_money", {})
    if sm.get("signal") == "accumulation":
        parts.append("Smart money accumulating")
    elif sm.get("signal") == "distribution":
        parts.append("⚠️ Institutional distribution detected")

    # Trade levels
    rr = trade_levels.get("risk_reward", 0)
    parts.append(f"R:R {rr:.1f}:1")

    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Main Scoring Function
# ---------------------------------------------------------------------------


def score_stock(
    symbol: str,
    df: pd.DataFrame,
    profile: dict | None = None,
    sector_rs: dict | None = None,
    news_score: float = 50.0,
    nifty_close: pd.Series | None = None,
) -> dict[str, Any]:
    """Run the full 8-pillar institutional analysis on a single stock.

    Returns:
        alpha_score: 0-100
        confidence_score: 0-100
        verdict: "BUY" | "HOLD" | "SELL"
        entry, stop_loss, target_1, target_2, risk_reward
        pillar_scores: {pillar_name: 0-100}
        pillar_details: {pillar_name: {sub-indicator details}}
        reasoning: str
    """
    if df.empty or "Close" not in df.columns:
        return _empty_result(symbol, profile)

    close = df["Close"].astype(float)
    if len(close) < 10:
        return _empty_result(symbol, profile)

    price = float(close.iloc[-1])

    # Run all 8 pillars
    p1 = _score_trend(df, close)
    p2 = _score_momentum(close)
    p3 = _score_volume(df)
    p4 = _score_volatility(df, close)
    p5 = _score_market_structure(df)
    p6 = _score_relative_strength(close, sector_rs, nifty_close)
    p7 = _score_institutional(df)
    p8 = _score_news_sentiment(news_score)

    pillar_scores = {
        "trend": p1["score"],
        "momentum": p2["score"],
        "volume": p3["score"],
        "volatility": p4["score"],
        "market_structure": p5["score"],
        "relative_strength": p6["score"],
        "institutional": p7["score"],
        "news_sentiment": p8["score"],
    }

    pillar_details = {
        "trend": p1,
        "momentum": p2,
        "volume": p3,
        "volatility": p4,
        "market_structure": p5,
        "relative_strength": p6,
        "institutional": p7,
        "news_sentiment": p8,
    }

    alpha = _compute_alpha_score(pillar_scores)
    confidence = _compute_confidence_score(pillar_scores, pillar_details)
    verdict = _compute_verdict(alpha, confidence, pillar_scores)
    trade_levels = _compute_trade_levels(price, df, alpha, pillar_details)
    reasoning = _generate_reasoning(
        symbol, alpha, confidence, verdict, pillar_scores, pillar_details, trade_levels
    )

    display = symbol.replace(".NS", "").replace(".BO", "")
    prof = profile or {}

    return {
        "symbol": symbol,
        "display_symbol": display,
        "name": prof.get("name", display),
        "sector": prof.get("sector", "N/A"),
        "cap_segment": prof.get("cap_segment", "unknown"),
        "price": price,
        "alpha_score": alpha,
        "confidence_score": confidence,
        "verdict": verdict,
        "entry": trade_levels["entry"],
        "stop_loss": trade_levels["stop_loss"],
        "target_1": trade_levels["target_1"],
        "target_2": trade_levels["target_2"],
        "risk_reward": trade_levels["risk_reward"],
        "pillar_scores": pillar_scores,
        "pillar_details": pillar_details,
        "reasoning": reasoning,
        "generated_at": datetime.now().isoformat(),
    }


def _empty_result(symbol: str, profile: dict | None = None) -> dict:
    """Empty result for stocks with insufficient data."""
    display = symbol.replace(".NS", "").replace(".BO", "")
    prof = profile or {}
    return {
        "symbol": symbol,
        "display_symbol": display,
        "name": prof.get("name", display),
        "sector": prof.get("sector", "N/A"),
        "cap_segment": prof.get("cap_segment", "unknown"),
        "price": 0,
        "alpha_score": 0,
        "confidence_score": 0,
        "verdict": "HOLD",
        "entry": 0, "stop_loss": 0, "target_1": 0, "target_2": 0, "risk_reward": 0,
        "pillar_scores": {k: 50.0 for k in PILLAR_WEIGHTS},
        "pillar_details": {},
        "reasoning": f"{display} — Insufficient data for institutional analysis.",
        "generated_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Bulk Scanner — runs across entire watchlist
# ---------------------------------------------------------------------------

import json
import os
from datetime import datetime, timedelta

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "institutional_scan_cache.json")


def get_cached_institutional_scan() -> dict[str, Any] | None:
    """Retrieve the cached institutional scan results if fresh (within 30 mins)."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached = json.load(f)
            gen_time_str = cached.get("summary", {}).get("generated_at")
            if gen_time_str:
                gen_time = datetime.fromisoformat(gen_time_str)
                # Cache is fresh for 30 minutes
                if datetime.now() - gen_time < timedelta(minutes=30):
                    return cached
        except Exception as e:
            print(f"[InstitutionalScanner] Error reading cache: {e}")
    return None


def run_institutional_scan(force_refresh: bool = False) -> dict[str, Any]:
    """Run the 8-pillar institutional scanner across all watchlist symbols.

    Returns:
        results: list of scored stock dicts
        alerts: list of high-alpha stocks (Alpha > 80, Confidence > 75, R:R > 1:2)
        summary: scan metadata
    """
    if not force_refresh:
        cached = get_cached_institutional_scan()
        if cached:
            print("[InstitutionalScanner] Returning cached scan results.")
            return cached

    symbols = market_data.get_watchlist()

    # Bulk download 3-month daily data
    bulk_history: dict[str, pd.DataFrame] = {}
    try:
        tickers_str = " ".join(symbols)
        df = yf.download(
            tickers_str, period="1y", interval="1d",
            group_by="ticker", progress=False, threads=True, timeout=20,
        )
        for sym in symbols:
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if sym in df.columns.get_level_values(0):
                        sym_df = df[sym].copy().dropna(how="all")
                        if not sym_df.empty:
                            bulk_history[sym] = sym_df
                else:
                    sym_df = df.copy().dropna(how="all")
                    if not sym_df.empty:
                        bulk_history[sym] = sym_df
            except Exception:
                pass
    except Exception as exc:
        print(f"[InstitutionalScanner] Bulk download error: {exc}")

    # Fetch Nifty data once for all RS calculations
    nifty_close = None
    try:
        nifty_df = yf.download("^NSEI", period="1y", interval="1d", progress=False, timeout=10)

        if not nifty_df.empty:
            nifty_col = nifty_df["Close"]
            if isinstance(nifty_col, pd.DataFrame):
                nifty_col = nifty_col.iloc[:, 0]
            nifty_close = nifty_col.dropna()
    except Exception:
        pass


    # Fetch DB profiles
    db_profiles: dict[str, dict] = {}
    client = get_client()
    if client:
        try:
            res = client.table("stocks").select("*").in_("symbol", symbols).execute()
            for row in res.data:
                db_profiles[row["symbol"]] = row
        except Exception as e:
            print(f"[InstitutionalScanner] DB profiles query error: {e}")


    # Market context for sector RS
    try:
        market_ctx = get_today_market_context()
    except Exception:
        market_ctx = {"breadth": {"environment": "risk_on"}, "sectors": {}}

    # Parallel scoring
    results: list[dict] = []
    scanned = 0

    def _score_one(sym: str) -> dict | None:
        history = bulk_history.get(sym)
        if history is None or history.empty:
            return None

        profile = db_profiles.get(sym, {"symbol": sym, "name": sym.replace(".NS", "")})

        # Look up sector RS from cached context
        sector_rs = None
        sector = profile.get("sector")
        if sector:
            normalized = _normalize_sector(sector)
            if normalized and normalized in market_ctx.get("sectors", {}):
                sector_rs = market_ctx["sectors"][normalized]

        return score_stock(sym, history, profile, sector_rs, 50.0, nifty_close)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_score_one, sym): sym
            for sym in symbols
            if sym in bulk_history
        }
        for future in as_completed(futures):
            scanned += 1
            try:
                result = future.result(timeout=20)
                if result and result.get("alpha_score", 0) > 0:
                    results.append(result)
            except Exception:
                pass

    # Sort by alpha score descending
    results.sort(key=lambda r: r["alpha_score"], reverse=True)

    # Filter high-conviction alerts
    alerts = [
        r for r in results
        if r["alpha_score"] > 80
        and r["confidence_score"] > 75
        and r["risk_reward"] > 2.0
        and r["verdict"] == "BUY"
    ]

    # Fire Telegram alerts for qualifying trades
    try:
        from app.services.notifier import send_institutional_alpha_alert
        for alert in alerts:
            send_institutional_alpha_alert(alert)
    except Exception:
        pass

    res_data = {
        "results": results,
        "alerts": alerts,
        "summary": {
            "scanned": scanned,
            "total_results": len(results),
            "high_alpha_alerts": len(alerts),
            "market_environment": market_ctx.get("breadth", {}).get("environment", "unknown"),
            "generated_at": datetime.now().isoformat(),
        },
    }

    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(res_data, f, default=str)
    except Exception as e:
        print(f"[InstitutionalScanner] Error writing cache: {e}")

    return res_data
