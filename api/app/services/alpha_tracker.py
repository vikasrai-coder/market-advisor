"""Alpha Tracker — Progressive accuracy tracking for alpha alerts.

Records each alert, reconciles EOD, computes rolling accuracy,
and adaptively adjusts scanner thresholds based on performance.

This is the "training" system: not ML, but statistical tracking that
tightens filters as win rate improves and loosens when it drops.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, date
from typing import Any

import yfinance as yf

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "alpha_tracker_cache.json")
_TRAINING_FILE = os.path.join(os.path.dirname(__file__), "..", "alpha_training_data.json")
_lock = threading.Lock()


def _load_cache() -> dict[str, Any]:
    """Load tracker state from JSON cache."""
    try:
        with open(_CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "alerts_history": [],
            "daily_stats": [],
            "adaptive_thresholds": {},
            "created_at": datetime.now().isoformat(),
        }


def _save_cache(data: dict[str, Any]) -> None:
    """Persist tracker state to JSON cache."""
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as exc:
        print(f"[AlphaTracker] Failed to save cache: {exc}")


def _load_training_data() -> list[dict[str, Any]]:
    """Load training data records."""
    try:
        with open(_TRAINING_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_training_data(data: list[dict[str, Any]]) -> None:
    """Save training data records."""
    try:
        with open(_TRAINING_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as exc:
        print(f"[AlphaTracker] Failed to save training data: {exc}")


def record_training_data(raw_features: list[dict[str, Any]]) -> int:
    """Record raw features for all scanned symbols to build an ML training dataset.

    Returns number of training records recorded.
    """
    with _lock:
        training_records = _load_training_data()
        today = date.today().isoformat()

        recorded = 0
        for feat in raw_features:
            record = {
                "symbol": feat["symbol"],
                "display_symbol": feat["display_symbol"],
                "price": feat["price"],
                "composite_score": feat["composite_score"],
                "trend_score": feat["trend_score"],
                "technical_score": feat["technical_score"],
                "rsi": feat["rsi"],
                "vwap": feat["vwap"],
                "macd_crossover": feat["macd_crossover"],
                "volume_spike": feat["volume_spike"],
                "cap_segment": feat["cap_segment"],
                "sector": feat["sector"],
                "scan_date": today,
                "generated_at": feat.get("generated_at", datetime.now().isoformat()),
                "exit_price": None,
                "actual_return_pct": None,
                "outcome": "pending",  # pending | target_hit | stopped_out | held
                "label": None,         # 1 for hit (>= 10%), 0 for stop/held
                "reconciled_at": None,
            }
            training_records.append(record)
            recorded += 1

        # Keep only the last 3000 records to prevent file bloat
        training_records = training_records[-3000:]
        _save_training_data(training_records)
        return recorded


def record_alerts(alerts: list[dict[str, Any]]) -> int:
    """Record new alpha alerts for tracking.

    Returns number of alerts recorded.
    """
    import logging
    logger = logging.getLogger(__name__)

    with _lock:
        cache = _load_cache()
        today = date.today().isoformat()

        recorded = 0
        for alert in alerts:
            # BUG-04: Alert Deduplication
            is_duplicate = any(
                existing.get("symbol") == alert["symbol"] and
                existing.get("alert_date") == today and
                existing.get("entry_price") == alert["entry_price"]
                for existing in cache.get("alerts_history", [])
            )
            if is_duplicate:
                print(f"[AlphaTracker] Skipping duplicate alert for {alert['symbol']} on {today} at {alert['entry_price']}")
                continue

            # BUG-03: Risk/Reward Gate
            entry_price = alert.get("entry_price")
            target_price = alert.get("target_price")
            stop_loss = alert.get("stop_loss")
            
            try:
                ep = float(entry_price) if entry_price is not None else 0.0
                tp = float(target_price) if target_price is not None else 0.0
                sl = float(stop_loss) if stop_loss is not None else 0.0
            except (ValueError, TypeError):
                ep, tp, sl = 0.0, 0.0, 0.0

            if ep - sl <= 0:
                rr = 0.0
            else:
                rr = (tp - ep) / (ep - sl)
                
            if rr < 2.0:
                logger.warning(f"Poor R:R = {rr}")
                print(f"[AlphaTracker] Rejecting alert for {alert['symbol']} due to poor R:R = {rr:.2f}")
                continue

            entry = {
                "id": alert.get("id", ""),
                "symbol": alert["symbol"],
                "display_symbol": alert.get("display_symbol", ""),
                "cap_segment": alert.get("cap_segment", ""),
                "entry_price": alert["entry_price"],
                "target_price": alert["target_price"],
                "stop_loss": alert["stop_loss"],
                "composite_score": alert.get("composite_score", 0),
                "confidence": alert.get("confidence", 0),
                "alert_date": today,
                "generated_at": alert.get("generated_at", datetime.now().isoformat()),
                "outcome": "pending",  # pending | target_hit | stopped_out | held
                "exit_price": None,
                "actual_return_pct": None,
                "reconciled_at": None,
            }
            cache["alerts_history"].append(entry)
            recorded += 1

        # Keep only last 500 alerts to avoid unbounded growth
        cache["alerts_history"] = cache["alerts_history"][-500:]
        _save_cache(cache)
        return recorded


def reconcile_alerts(target_date: str | None = None) -> dict[str, Any]:
    """Reconcile pending alerts by checking actual prices.

    For each pending alert on the target_date (default: today),
    fetch the current/close price and determine outcome.

    Returns summary dict with counts.
    """
    with _lock:
        cache = _load_cache()
        training_records = _load_training_data()
        check_date = target_date or date.today().isoformat()

        pending = [
            a for a in cache["alerts_history"]
            if a["outcome"] == "pending" and a["alert_date"] == check_date
        ]
        pending_training = [
            r for r in training_records
            if r["outcome"] == "pending" and r["scan_date"] == check_date
        ]

        if not pending and not pending_training:
            return {"reconciled": 0, "message": "No pending alerts or training data for date"}

        # Fetch current prices for all pending symbols
        symbols = list({a["symbol"] for a in pending} | {r["symbol"] for r in pending_training})
        prices: dict[str, float] = {}

        try:
            tickers_str = " ".join(symbols)
            df = yf.download(
                tickers_str, period="1d", interval="1d",
                progress=False, threads=True
            )
            for sym in symbols:
                try:
                    if isinstance(df.columns, __import__("pandas").MultiIndex):
                        if sym in df.columns.get_level_values(0):
                            close = df[sym]["Close"].dropna()
                            if not close.empty:
                                prices[sym] = float(close.iloc[-1])
                    else:
                        close = df["Close"].dropna()
                        if not close.empty:
                            prices[sym] = float(close.iloc[-1])
                except Exception:
                    pass
        except Exception as exc:
            print(f"[AlphaTracker] Price fetch error: {exc}")

        target_hits = 0
        stopped_out = 0
        held = 0

        now = datetime.now().isoformat()

        # 1. Reconcile alerts_history
        for alert in pending:
            sym = alert["symbol"]
            current = prices.get(sym)
            if current is None:
                continue

            alert["exit_price"] = round(current, 2)
            entry = alert["entry_price"]
            if entry and entry > 0:
                alert["actual_return_pct"] = round(
                    ((current - entry) / entry) * 100, 2
                )
            alert["reconciled_at"] = now

            if current >= alert["target_price"]:
                alert["outcome"] = "target_hit"
                target_hits += 1
            elif current <= alert["stop_loss"]:
                alert["outcome"] = "stopped_out"
                stopped_out += 1
            else:
                alert["outcome"] = "held"
                held += 1

        # 2. Reconcile training_history
        reconciled_training = 0
        for record in pending_training:
            sym = record["symbol"]
            current = prices.get(sym)
            if current is None:
                continue

            record["exit_price"] = round(current, 2)
            entry = record["price"]
            if entry and entry > 0:
                ret = round(((current - entry) / entry) * 100, 2)
                record["actual_return_pct"] = ret

                # Tag outcome and training label (1 if target hit >= 10%, 0 otherwise)
                if ret >= 10.0:
                    record["outcome"] = "target_hit"
                    record["label"] = 1
                elif ret <= -3.0:
                    record["outcome"] = "stopped_out"
                    record["label"] = 0
                else:
                    record["outcome"] = "held"
                    record["label"] = 0

            record["reconciled_at"] = now
            reconciled_training += 1

        # Record daily stats
        total = target_hits + stopped_out + held
        if total > 0:
            win_rate = round((target_hits / total) * 100, 1)
            returns = [
                a["actual_return_pct"] for a in pending
                if a.get("actual_return_pct") is not None
            ]
            avg_return = round(sum(returns) / len(returns), 2) if returns else 0

            daily_stat = {
                "date": check_date,
                "total_alerts": total,
                "target_hits": target_hits,
                "stopped_out": stopped_out,
                "held": held,
                "win_rate": win_rate,
                "avg_return_pct": avg_return,
                "reconciled_at": now,
            }
            cache["daily_stats"].append(daily_stat)
            cache["daily_stats"] = cache["daily_stats"][-90:]  # keep 90 days

        # Adaptive threshold adjustment
        _adapt_thresholds(cache)

        _save_cache(cache)
        _save_training_data(training_records)

        return {
            "reconciled": total,
            "target_hits": target_hits,
            "stopped_out": stopped_out,
            "held": held,
            "reconciled_training": reconciled_training,
        }



def get_performance() -> dict[str, Any]:
    """Return rolling performance metrics.

    Used by the frontend to display the training progress panel.
    """
    with _lock:
        cache = _load_cache()

    alerts = cache.get("alerts_history", [])
    daily_stats = cache.get("daily_stats", [])
    adaptive = cache.get("adaptive_thresholds", {})

    # Overall stats from all reconciled alerts
    reconciled = [a for a in alerts if a["outcome"] != "pending"]
    total = len(reconciled)
    target_hits = len([a for a in reconciled if a["outcome"] == "target_hit"])
    stopped_out = len([a for a in reconciled if a["outcome"] == "stopped_out"])
    held = len([a for a in reconciled if a["outcome"] == "held"])

    win_rate = round((target_hits / total) * 100, 1) if total > 0 else 0
    returns = [a["actual_return_pct"] for a in reconciled if a.get("actual_return_pct") is not None]
    avg_return = round(sum(returns) / len(returns), 2) if returns else 0
    positive_returns = [r for r in returns if r > 0]
    negative_returns = [r for r in returns if r < 0]
    avg_win = round(sum(positive_returns) / len(positive_returns), 2) if positive_returns else 0
    avg_loss = round(sum(negative_returns) / len(negative_returns), 2) if negative_returns else 0
    profit_factor = round(
        abs(sum(positive_returns)) / abs(sum(negative_returns)), 2
    ) if negative_returns and sum(negative_returns) != 0 else 0

    # Current streak
    streak = 0
    streak_type = "none"
    for a in reversed(reconciled):
        if a["outcome"] == "target_hit":
            if streak_type in ("win", "none"):
                streak += 1
                streak_type = "win"
            else:
                break
        elif a["outcome"] == "stopped_out":
            if streak_type in ("loss", "none"):
                streak += 1
                streak_type = "loss"
            else:
                break

    # Training progress: estimate based on avg_return approaching 10%
    # 0% = avg_return at 0%, 100% = avg_return at 10%+
    training_progress = min(100, max(0, round((avg_return / 10.0) * 100)))

    # Recent 7 days performance
    recent_7 = daily_stats[-7:] if len(daily_stats) >= 7 else daily_stats
    recent_win_rate = 0
    if recent_7:
        r_total = sum(d["total_alerts"] for d in recent_7)
        r_hits = sum(d["target_hits"] for d in recent_7)
        recent_win_rate = round((r_hits / r_total) * 100, 1) if r_total > 0 else 0

    pending_count = len([a for a in alerts if a["outcome"] == "pending"])

    return {
        "total_alerts": total,
        "pending_alerts": pending_count,
        "target_hits": target_hits,
        "stopped_out": stopped_out,
        "held": held,
        "win_rate": win_rate,
        "avg_return_pct": avg_return,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": profit_factor,
        "streak": streak,
        "streak_type": streak_type,
        "training_progress": training_progress,
        "recent_7d_win_rate": recent_win_rate,
        "daily_stats": daily_stats[-30:],  # last 30 days for chart
        "adaptive_thresholds": adaptive,
    }


def _adapt_thresholds(cache: dict[str, Any]) -> None:
    """Adjust scanner thresholds based on recent performance.

    - If win rate > 50% over last 7 days → lower composite threshold slightly (capture more)
    - If win rate < 30% → raise composite threshold (be more selective)
    - Thresholds bounded to safe ranges
    """
    stats = cache.get("daily_stats", [])
    if len(stats) < 3:
        return  # not enough data to adapt

    recent = stats[-7:]
    total = sum(d["total_alerts"] for d in recent)
    hits = sum(d["target_hits"] for d in recent)
    if total == 0:
        return

    win_rate = hits / total

    current = cache.get("adaptive_thresholds", {})
    composite = current.get("min_composite", 75)

    if win_rate >= 0.50:
        # Performing well → can lower threshold to capture more opportunities
        composite = max(70, composite - 2)
    elif win_rate < 0.30:
        # Too many losses → raise threshold for stricter filter
        composite = min(90, composite + 3)

    cache["adaptive_thresholds"] = {
        "min_composite": composite,
        "last_adapted": datetime.now().isoformat(),
        "based_on_win_rate": round(win_rate * 100, 1),
    }
