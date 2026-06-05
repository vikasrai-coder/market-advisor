"""Quantitative backtest simulator to test past stock indicator scans and subsequent performance."""

import logging
import statistics
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from app.config import settings
from app.scan_modes import get_config
from app.services import market_data, technicals
from app.services.analyzer import (
    _select_diversified_top_buys,
    _target_for_mode,
    _stop_for_mode,
)
from app.symbols import normalize_symbol, display_symbol

logger = logging.getLogger(__name__)


def run_backtest_simulation(
    mode: str = "swing",
    start_date_str: str = "",
    check_days: int = 5,
) -> dict[str, Any]:
    """Simulate a scan at a past starting date, compile recommendations, and check subsequent outcomes.

    Args:
        mode: The trading mode ("intraday", "swing", "longterm", "future")
        start_date_str: ISO format string of the target date (e.g. "2026-05-10")
        check_days: Subsequent trading days to monitor for target/stop hits.
    """
    try:
        start_date = date.fromisoformat(start_date_str)
    except (ValueError, TypeError):
        start_date = date.today() - timedelta(days=10)

    cfg = get_config(mode)
    symbols = market_data.get_watchlist()
    
    logger.info(f"Starting historical backtest scan on {start_date.isoformat()} for mode '{mode}' across {len(symbols)} symbols")

    scored: list[dict[str, Any]] = []
    errors: list[str] = []

    # Fetch indicators up to start_date for each stock
    for symbol in symbols:
        try:
            norm_sym = normalize_symbol(symbol)
            # Fetch lookback history up to signal date D
            history = _fetch_history_up_to(norm_sym, start_date, mode)
            if history.empty or len(history) < 5:
                continue

            profile = market_data.fetch_stock_profile(norm_sym)
            
            # Compute indicators
            if mode == "intraday":
                metrics = technicals.compute_intraday_indicators(history)
            elif mode == "longterm":
                metrics = technicals.compute_longterm_indicators(history, profile)
            else:
                metrics = technicals.compute_indicators(history)

            if metrics.get("price") is None:
                continue

            # Composite score calculation (matching analyzer.py)
            trend = metrics.get("trend_score") or 50.0
            technical = metrics.get("technical_score") or 50.0
            fundamental = metrics.get("fundamental_score") or 50.0
            news_score = 50.0  # Constant neutral news score to avoid future news leaks

            if mode == "longterm":
                composite = round(
                    trend * cfg.weight_trend
                    + technical * cfg.weight_technical
                    + news_score * cfg.weight_news
                    + fundamental * cfg.weight_fundamental,
                    2,
                )
            else:
                composite = round(
                    trend * cfg.weight_trend
                    + technical * cfg.weight_technical
                    + news_score * cfg.weight_news,
                    2,
                )

            scored.append({
                "symbol": norm_sym,
                "display_symbol": display_symbol(norm_sym),
                "profile": profile,
                "metrics": metrics,
                "news_score": news_score,
                "composite_score": composite,
            })
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")

    if not scored:
        return {
            "mode": mode,
            "start_date": start_date.isoformat(),
            "check_days": check_days,
            "metrics": {
                "win_rate": 0.0,
                "avg_return": 0.0,
                "total_picks": 0,
                "target_hits": 0,
                "stop_hits": 0,
                "held": 0,
                "index_return": 0.0,
                "outperformance": 0.0,
            },
            "results": [],
            "errors": errors,
        }

    # Diversify and pick top buys
    top_buys = _select_diversified_top_buys(scored, count=cfg.top_picks)
    
    # Compute relative valuation medians for undervalued tags
    sector_pes = {}
    for item in scored:
        sec_name = item["profile"].get("sector")
        pe_val = item["profile"].get("pe_ratio")
        if sec_name and pe_val is not None and pe_val > 0:
            if sec_name not in sector_pes:
                sector_pes[sec_name] = []
            sector_pes[sec_name].append(pe_val)
    sector_medians = {}
    for sec_name, pes_list in sector_pes.items():
        if len(pes_list) >= 2:
            sector_medians[sec_name] = statistics.median(pes_list)

    results: list[dict[str, Any]] = []
    win_count = 0
    loss_count = 0
    held_count = 0
    all_returns = []

    for rank, item in enumerate(top_buys, start=1):
        sym = item["symbol"]
        entry_price = float(item["metrics"]["price"])
        
        target_price = _target_for_mode(entry_price, mode)
        stop_loss = _stop_for_mode(entry_price, mode)

        # Check undervalued badge status
        item_sector = item["profile"].get("sector")
        item_pe = item["profile"].get("pe_ratio")
        is_undervalued = False
        if item_sector and item_pe is not None and item_pe > 0 and item_sector in sector_medians:
            if item_pe < sector_medians[item_sector] * 0.8:
                is_undervalued = True

        # Fetch subsequent history to check target/stop hits
        sub_history = _fetch_subsequent_history(sym, start_date, check_days, mode)
        
        outcome = "held"
        exit_price = entry_price
        exit_date = None
        pct_return = 0.0

        if not sub_history.empty:
            # For intraday, we simulate hourly candles
            # Otherwise, we look at daily bars
            candles_to_check = sub_history.head(check_days * 7 if mode == "intraday" else check_days)
            
            for idx, row in candles_to_check.iterrows():
                high = float(row["High"])
                low = float(row["Low"])
                close_price = float(row["Close"])
                open_price = float(row["Open"])
                candle_date = idx.to_pydatetime().date() if isinstance(idx, pd.Timestamp) else start_date

                # Green candle: target checked first
                if close_price >= open_price:
                    if high >= target_price:
                        outcome = "target_hit"
                        exit_price = target_price
                        exit_date = candle_date.isoformat()
                        break
                    elif low <= stop_loss:
                        outcome = "stopped_out"
                        exit_price = stop_loss
                        exit_date = candle_date.isoformat()
                        break
                # Red candle: stop checked first
                else:
                    if low <= stop_loss:
                        outcome = "stopped_out"
                        exit_price = stop_loss
                        exit_date = candle_date.isoformat()
                        break
                    elif high >= target_price:
                        outcome = "target_hit"
                        exit_price = target_price
                        exit_date = candle_date.isoformat()
                        break
            
            # If not hit, close at final candle
            if outcome == "held":
                exit_price = float(candles_to_check["Close"].iloc[-1])
                exit_date = candles_to_check.index[-1].to_pydatetime().date().isoformat() if isinstance(candles_to_check.index[-1], pd.Timestamp) else None

            pct_return = round(((exit_price - entry_price) / entry_price) * 100, 2)
        else:
            outcome = "insufficient_data"
            pct_return = 0.0

        if outcome == "target_hit":
            win_count += 1
        elif outcome == "stopped_out":
            loss_count += 1
        else:
            held_count += 1

        all_returns.append(pct_return)

        results.append({
            "rank": rank,
            "symbol": sym,
            "display_symbol": item["display_symbol"],
            "name": item["profile"].get("name"),
            "sector": item_sector,
            "is_undervalued": is_undervalued,
            "composite_score": item["composite_score"],
            "rsi": item["metrics"].get("rsi"),
            "macd": item["metrics"].get("macd"),
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "outcome": outcome,
            "exit_price": exit_price,
            "exit_date": exit_date,
            "return_pct": pct_return,
        })

    # Calculate index return (Nifty 50 ^NSEI)
    index_return = 0.0
    try:
        index_hist_up = _fetch_history_up_to("^NSEI", start_date, mode)
        if not index_hist_up.empty:
            index_entry = float(index_hist_up["Close"].iloc[-1])
            index_sub = _fetch_subsequent_history("^NSEI", start_date, check_days, mode)
            if not index_sub.empty:
                index_candles = index_sub.head(check_days * 6 if mode == "intraday" else check_days)
                index_exit = float(index_candles["Close"].iloc[-1])
                index_return = round(((index_exit - index_entry) / index_entry) * 100, 2)
    except Exception:
        pass

    total_picks = len(results)
    resolved_picks = win_count + loss_count + (held_count if held_count > 0 else 0)
    win_rate = round((win_count / resolved_picks * 100), 2) if resolved_picks > 0 else 0.0
    avg_return = round(statistics.mean(all_returns), 2) if all_returns else 0.0
    outperformance = round(avg_return - index_return, 2)

    res_data = {
        "mode": mode,
        "start_date": start_date.isoformat(),
        "check_days": check_days,
        "metrics": {
            "win_rate": win_rate,
            "avg_return": avg_return,
            "total_picks": total_picks,
            "target_hits": win_count,
            "stop_hits": loss_count,
            "held": held_count,
            "index_return": index_return,
            "outperformance": outperformance,
        },
        "results": results,
        "errors": errors,
    }

    # Persist the backtest run to Supabase for historical tracking
    try:
        from app.services.supabase_store import get_client
        client = get_client()
        if client:
            run_payload = {
                "mode": res_data["mode"],
                "start_date": res_data["start_date"],
                "check_days": res_data["check_days"],
                "win_rate": res_data["metrics"]["win_rate"],
                "avg_return": res_data["metrics"]["avg_return"],
                "total_picks": res_data["metrics"]["total_picks"],
                "target_hits": res_data["metrics"]["target_hits"],
                "stop_hits": res_data["metrics"]["stop_hits"],
                "held": res_data["metrics"]["held"],
                "index_return": res_data["metrics"]["index_return"],
                "outperformance": res_data["metrics"]["outperformance"]
            }
            
            run_res = client.table("backtest_runs").insert(run_payload).execute()
            if run_res.data:
                run_id = run_res.data[0]["id"]
                results_rows = []
                for r in res_data["results"]:
                    results_rows.append({
                        "run_id": run_id,
                        "rank": r["rank"],
                        "symbol": r["symbol"],
                        "name": r.get("name"),
                        "sector": r.get("sector"),
                        "is_undervalued": r["is_undervalued"],
                        "composite_score": r["composite_score"],
                        "rsi": r.get("rsi"),
                        "macd": r.get("macd"),
                        "entry_price": r["entry_price"],
                        "target_price": r["target_price"],
                        "stop_loss": r["stop_loss"],
                        "exit_price": r["exit_price"],
                        "exit_date": r.get("exit_date"),
                        "return_pct": r["return_pct"],
                        "outcome": r["outcome"]
                    })
                if results_rows:
                    client.table("backtest_results").insert(results_rows).execute()
                    logger.info(f"Successfully stored backtest run {run_id} and {len(results_rows)} detailed results in Supabase.")
    except Exception as exc:
        logger.error(f"Error persisting backtest results to Supabase: {exc}", exc_info=True)

    return res_data


def _fetch_history_up_to(symbol: str, end_date: date, mode: str) -> pd.DataFrame:
    """Fetch lookback historical price data up to end_date."""
    cfg = get_config(mode)
    if mode == "intraday":
        start = end_date - timedelta(days=12)
        interval = "60m"
    elif mode == "longterm":
        start = end_date - timedelta(days=450)
        interval = "1d"
    else:
        start = end_date - timedelta(days=280)
        interval = "1d"

    end_str = (end_date + timedelta(days=1)).isoformat()
    start_str = start.isoformat()

    ticker = yf.Ticker(symbol)
    history = ticker.history(start=start_str, end=end_str, interval=interval, auto_adjust=True)
    if history.empty and symbol.endswith(".NS"):
        alt = symbol.replace(".NS", ".BO")
        history = yf.Ticker(alt).history(start=start_str, end=end_str, interval=interval, auto_adjust=True)

    return history


def _fetch_subsequent_history(symbol: str, start_date: date, check_days: int, mode: str) -> pd.DataFrame:
    """Fetch historical price data starting after start_date to verify targets/stops."""
    start_str = (start_date + timedelta(days=1)).isoformat()
    if mode == "intraday":
        end_str = (start_date + timedelta(days=check_days + 3)).isoformat()
        interval = "60m"
    else:
        # Fetch double the calendar days to ensure we get enough actual trading days
        end_str = (start_date + timedelta(days=check_days * 2 + 10)).isoformat()
        interval = "1d"

    ticker = yf.Ticker(symbol)
    history = ticker.history(start=start_str, end=end_str, interval=interval, auto_adjust=True)
    if history.empty and symbol.endswith(".NS"):
        alt = symbol.replace(".NS", ".BO")
        history = yf.Ticker(alt).history(start=start_str, end=end_str, interval=interval, auto_adjust=True)

    return history
