"""Alpha Scanner — High-conviction same-day trade filter.

Surfaces only trades where multiple technical signals converge, targeting
10%+ intraday profit potential across all cap segments (small/mid/large).

This is an admin-only analytical tool. All outputs carry market risk.
"""

from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from app.services import market_data, technicals
from app.services.supabase_store import get_client
from app.services.sector_rs import get_today_market_context, get_sector_relative_strength, _normalize_sector

ALPHA_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "alpha_scan_cache.json")


def get_cached_alpha_scan() -> dict[str, Any] | None:
    """Retrieve the cached alpha scan results if fresh (within 30 mins)."""
    if os.path.exists(ALPHA_CACHE_FILE):
        try:
            with open(ALPHA_CACHE_FILE, "r") as f:
                cached = json.load(f)
            gen_time_str = cached.get("generated_at")
            if gen_time_str:
                gen_time = datetime.fromisoformat(gen_time_str)
                # Cache is fresh for 30 minutes
                if datetime.now() - gen_time < timedelta(minutes=30):
                    return cached
        except Exception as e:
            print(f"[AlphaScanner] Error reading cache: {e}")
    return None



# ---------------------------------------------------------------------------
# Configurable thresholds — the tracker can tighten these over time
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "min_composite": 75,        # minimum composite score (trend+technical weighted)
    "min_rsi": 38,              # RSI floor — avoid dead momentum
    "max_rsi": 70,              # RSI ceiling — avoid overbought traps
    "min_volume_spike": 1.3,    # volume vs 20-period avg multiplier
    "require_vwap_above": True, # price must be above VWAP
    "require_macd_cross": False, # bullish MACD crossover (nice-to-have, not required)
    "target_pct": 0.10,         # 10% profit target
    "stop_pct": 0.03,           # 3% stop loss (3.3:1 reward-to-risk)
}


# ---------------------------------------------------------------------------
# Enhancement #7 — Market/Sector Gate Before Firing Any Alpha Alert
# ---------------------------------------------------------------------------


def should_fire_alpha_alert(
    sector: str | None,
    composite_score: float,
    market_ctx: dict | None = None,
) -> tuple[bool, str]:
    """Final gate before firing an alpha alert.

    Returns (should_fire: bool, suppression_reason: str).
    Suppresses alerts on risk-off days and lagging sectors.
    Raises minimum bar to 80 in caution mode.
    """
    ctx = market_ctx or {}
    breadth = ctx.get("breadth", {"environment": "risk_on"})
    env = breadth.get("environment", "risk_on")

    if env == "risk_off":
        reasons = ", ".join(breadth.get("reasons", ["risk conditions"]))
        return False, f"Market risk-off: {reasons}"

    # Sector RS gate
    if sector:
        normalized = _normalize_sector(sector)
        if normalized:
            sectors_map = ctx.get("sectors", {})
            if normalized in sectors_map:
                sector_rs = sectors_map[normalized]
            else:
                try:
                    sector_rs = get_sector_relative_strength(normalized)
                except Exception:
                    sector_rs = {"status": "neutral"}
            if sector_rs.get("status") == "lagging" and composite_score < 80:
                return False, f"Sector {sector} lagging — alert suppressed unless score ≥ 80"

    # Caution mode raises bar
    min_score = 80.0 if env == "caution" else 70.0
    if composite_score < min_score:
        return False, f"Score {composite_score:.0f} below {min_score:.0f} threshold for {env} market"

    return True, ""


def scan_alpha_alerts(
    thresholds: dict[str, Any] | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Run the alpha scanner across all watchlist symbols.

    Returns a dict with:
      - alerts: list of AlphaAlert dicts
      - scanned: total symbols processed
      - passed: how many passed the filter
      - generated_at: ISO timestamp
      - thresholds: the filter thresholds used
    """
    if not force_refresh:
        cached = get_cached_alpha_scan()
        if cached:
            print("[AlphaScanner] Returning cached scan results.")
            return cached

    # Load learned adjustments from self-learning brain
    try:
        from app.services.loss_analyzer import load_learned_adjustments
        learned = load_learned_adjustments()
    except Exception:
        learned = {}

    cfg = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    # Apply learned composite override if applicable
    if learned:
        min_comp_override = learned.get("min_composite_score_override")
        if min_comp_override:
            cfg["min_composite"] = max(cfg["min_composite"], min_comp_override)

    symbols = market_data.get_watchlist()

    # Bulk download 5-day 60-min candles
    bulk_history: dict[str, pd.DataFrame] = {}
    try:
        tickers_str = " ".join(symbols)
        df = yf.download(
            tickers_str,
            period="5d",
            interval="60m",
            group_by="ticker",
            progress=False,
            threads=True,
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
        print(f"[AlphaScanner] Bulk download error: {exc}")

    # Fetch DB profiles for cap segment info
    db_profiles: dict[str, dict] = {}
    client = get_client()
    if client:
        try:
            res = client.table("stocks").select("*").execute()
            for row in res.data:
                db_profiles[row["symbol"]] = row
        except Exception:
            pass

    # ENHANCEMENT #7 — Fetch market context once (cached) for gate checks
    try:
        market_ctx = get_today_market_context()
    except Exception:
        market_ctx = {"breadth": {"environment": "risk_on"}, "sectors": {}}

    # Hard abort on risk-off
    if market_ctx["breadth"].get("environment") == "risk_off":
        reasons = ", ".join(market_ctx["breadth"].get("reasons", []))
        return {
            "alerts": [],
            "raw_features": [],
            "scanned": 0,
            "passed": 0,
            "generated_at": datetime.now().isoformat(),
            "thresholds": cfg,
            "suppressed": True,
            "suppression_reason": f"Market risk-off: {reasons}",
        }

    # Parallel analysis
    alerts: list[dict[str, Any]] = []
    scanned = 0

    def _analyze_one(sym: str) -> dict[str, Any] | None:
        history = bulk_history.get(sym)
        if history is None or history.empty:
            return None

        metrics = technicals.compute_intraday_indicators(history)
        profile = db_profiles.get(sym, {})

        # Compute weighted composite (same weights as intraday scan mode)
        trend = metrics.get("trend_score") or 0
        technical = metrics.get("technical_score") or 0
        composite = round(trend * 0.50 + technical * 0.50, 2)

        price = metrics.get("price")
        rsi = metrics.get("rsi")
        vol_spike = metrics.get("volume_spike", False)
        vol_ratio = metrics.get("volume_ratio", 1.0)
        vwap = metrics.get("vwap")
        bullish_cross = metrics.get("bullish_crossover", False)

        # Build raw features for training
        raw_feat = {
            "symbol": sym,
            "display_symbol": sym.replace(".NS", "").replace(".BO", ""),
            "price": round(price, 2) if price else None,
            "composite_score": composite,
            "trend_score": trend,
            "technical_score": technical,
            "rsi": round(rsi, 2) if rsi else None,
            "vwap": round(vwap, 2) if vwap else None,
            "macd_crossover": bullish_cross,
            "volume_spike": vol_spike,
            "volume_ratio": round(vol_ratio, 2),
            "cap_segment": profile.get("cap_segment", "unknown"),
            "sector": profile.get("sector", "N/A"),
            "generated_at": datetime.now().isoformat(),
        }

        # Apply sector learning penalty of 25 to the composite score if the sector is suppressed by the self-learning brain
        sector_penalty = 0
        if learned:
            sector = profile.get("sector")
            if sector and sector in learned.get("suppressed_sectors", []):
                sector_penalty = 25
                composite = max(0.0, composite - sector_penalty)

        # --- Apply strict filters ---
        passed_filter = True
        if composite < cfg["min_composite"]:
            passed_filter = False
            raw_feat["suppression_reason"] = f"Composite score {composite} (after sector penalty -{sector_penalty}) below {cfg['min_composite']}"
        elif rsi is not None and (rsi < cfg["min_rsi"] or rsi > cfg["max_rsi"]):
            passed_filter = False
        elif cfg["min_volume_spike"] > 1.0 and vol_ratio < cfg["min_volume_spike"]:
            passed_filter = False
        elif cfg["require_vwap_above"] and price and vwap and price < vwap:
            passed_filter = False
        elif cfg["require_macd_cross"] and not bullish_cross:
            passed_filter = False

        # ENHANCEMENT #7 — Market/sector gate
        if passed_filter:
            sector = profile.get("sector")
            should_fire, suppression = should_fire_alpha_alert(
                sector, composite, market_ctx
            )
            if not should_fire:
                passed_filter = False
                raw_feat["suppression_reason"] = suppression

        if not passed_filter:
            return {"alert": None, "raw_features": raw_feat}

        # --- Passed all filters → build alert ---
        entry = round(price, 2) if price else 0
        target = round(entry * (1 + cfg["target_pct"]), 2)
        stop_loss = round(entry * (1 - cfg["stop_pct"]), 2)

        # Confidence scoring: stack of confirmations
        confidence = 0.60
        if bullish_cross:
            confidence += 0.12
        if vol_spike:
            confidence += 0.08
        if vwap and price and price > vwap:
            confidence += 0.06
        if rsi and 45 <= rsi <= 60:
            confidence += 0.06
        if composite >= 85:
            confidence += 0.08
        confidence = min(confidence, 0.98)

        cap_segment = profile.get("cap_segment", "unknown")
        display = sym.replace(".NS", "").replace(".BO", "")
        name = profile.get("name", display)
        sector = profile.get("sector", "N/A")

        # Build reasoning — include sector RS context if available
        signals = []
        if bullish_cross:
            signals.append("MACD bullish crossover on 60m")
        if vol_spike:
            signals.append("Volume spike >1.5× avg")
        if vwap and price and price > vwap:
            signals.append(f"Price ₹{price:.0f} above VWAP ₹{vwap:.0f}")
        if rsi:
            signals.append(f"RSI {rsi:.1f} in momentum zone")
        signals.append(f"Composite score {composite:.0f}/100")
        # Append sector RS context
        normalized_sector = _normalize_sector(profile.get("sector"))
        if normalized_sector:
            sector_map = market_ctx.get("sectors", {})
            if normalized_sector in sector_map:
                sr = sector_map[normalized_sector]
                signals.append(f"Sector {normalized_sector} RS: {sr.get('status', 'neutral')} ({sr.get('rs_score', 1.0):.3f})")

        reasoning = f"{display} ({cap_segment.upper()} cap) showing strong intraday setup. " + ". ".join(signals) + "."

        alert = {
            "id": str(uuid.uuid4()),
            "symbol": sym,
            "display_symbol": display,
            "name": name,
            "sector": sector,
            "cap_segment": cap_segment,
            "entry_price": entry,
            "target_price": target,
            "stop_loss": stop_loss,
            "target_pct": round(cfg["target_pct"] * 100, 1),
            "stop_pct": round(cfg["stop_pct"] * 100, 1),
            "composite_score": composite,
            "rsi": round(rsi, 2) if rsi else None,
            "vwap": round(vwap, 2) if vwap else None,
            "macd_crossover": bullish_cross,
            "volume_spike": vol_spike,
            "confidence": round(confidence, 2),
            "reasoning": reasoning,
            "key_signals": signals,
            "generated_at": datetime.now().isoformat(),
        }

        return {"alert": alert, "raw_features": raw_feat}

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_analyze_one, sym): sym
            for sym in symbols
        }
        raw_features = []
        for future in as_completed(futures):
            scanned += 1
            try:
                result = future.result(timeout=15)
                if result is not None:
                    if result.get("raw_features"):
                        raw_features.append(result["raw_features"])
                    if result.get("alert"):
                        alerts.append(result["alert"])
            except Exception:
                pass

    # Sort by composite score descending, then confidence
    alerts.sort(key=lambda a: (a["composite_score"], a["confidence"]), reverse=True)

    res_data = {
        "alerts": alerts,
        "raw_features": raw_features,
        "scanned": scanned,
        "passed": len(alerts),
        "generated_at": datetime.now().isoformat(),
        "thresholds": cfg,
    }

    try:
        with open(ALPHA_CACHE_FILE, "w") as f:
            json.dump(res_data, f, default=str)
    except Exception as e:
        print(f"[AlphaScanner] Error writing cache: {e}")

    return res_data

