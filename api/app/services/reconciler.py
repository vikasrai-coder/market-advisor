"""Performance reconciliation service to track target price vs stop loss hits."""

from datetime import date, datetime, timedelta
import yfinance as yf
from app.services.supabase_store import get_client
from app.symbols import normalize_symbol


def reconcile_recommendations() -> dict[str, int]:
    """Fetch pending recommendations and verify if target price or stop loss was reached.

    Returns:
        Summary count of reconciled outcomes: target_hits, stopped_outs, remain_pending.
    """
    client = get_client()
    if not client:
        return {"target_hits": 0, "stopped_outs": 0, "remain_pending": 0}

    # Fetch pending recommendations from last 14 days
    threshold = (date.today() - timedelta(days=14)).isoformat()
    try:
        pending = (
            client.table("recommendations")
            .select("*")
            .eq("performance_status", "pending")
            .gte("trade_date", threshold)
            .execute()
        )
    except Exception:
        # Graceful return if column performance_status doesn't exist yet
        return {"target_hits": 0, "stopped_outs": 0, "remain_pending": 0}

    target_hits = 0
    stopped_outs = 0
    remain_pending = 0

    for rec in pending.data:
        symbol = rec.get("symbol")
        trade_date_str = rec.get("trade_date")
        target_price = rec.get("target_price")
        stop_loss = rec.get("stop_loss")

        if not symbol or not trade_date_str or target_price is None or stop_loss is None:
            continue

        try:
            target_price = float(target_price)
            stop_loss = float(stop_loss)
            trade_date = date.fromisoformat(trade_date_str)
        except (ValueError, TypeError):
            continue

        # Don't check performance on the future trade date itself before it happens
        if trade_date > date.today():
            remain_pending += 1
            continue

        # Fetch history since trade date to now
        norm_sym = normalize_symbol(symbol)
        ticker = yf.Ticker(norm_sym)
        # Fetch daily data
        hist = ticker.history(start=trade_date.isoformat(), end=(date.today() + timedelta(days=1)).isoformat())

        if hist.empty:
            remain_pending += 1
            continue

        # Scan candle highs and lows chronologically since trade date
        outcome = "pending"
        exit_price = None

        for idx, row in hist.iterrows():
            high = float(row["High"])
            low = float(row["Low"])

            # Check if stop loss was hit first, or target hit
            # We check both; if low <= stop loss, stopped out. If high >= target, target hit.
            if low <= stop_loss:
                outcome = "stopped_out"
                exit_price = stop_loss
                break
            elif high >= target_price:
                outcome = "target_hit"
                exit_price = target_price
                break

        # Check for technical trend reversals to identify if a bullish recommendation turns bearish!
        if outcome == "pending":
            try:
                mode_lower = (rec.get("trade_mode") or "swing").lower()
                
                if mode_lower == "intraday":
                    # Intraday checks hourly candles
                    hist_60m = ticker.history(period="5d", interval="60m")
                    if not hist_60m.empty:
                        from app.services.technicals import compute_intraday_indicators
                        indicators = compute_intraday_indicators(hist_60m)
                        
                        price = indicators.get("price")
                        sma_9 = indicators.get("sma_9")
                        sma_21 = indicators.get("sma_21")
                        bearish_cross = indicators.get("bearish_crossover", False)
                        
                        if bearish_cross or (price and sma_9 and sma_21 and price < sma_9 and price < sma_21):
                            outcome = "bearish_warning"
                            exit_price = price
                            reversal_reason = "MACD Bearish Crossover" if bearish_cross else "Price broke below 9/21 hourly SMAs"
                            
                            from app.services.notifier import send_telegram_reversal_alert
                            send_telegram_reversal_alert(symbol, price, reversal_reason, mode_lower)
                else:
                    # Swing / longterm / future use daily candles
                    hist_1d = ticker.history(period="30d", interval="1d")
                    if not hist_1d.empty:
                        from app.services.technicals import compute_indicators
                        indicators = compute_indicators(hist_1d)
                        
                        price = indicators.get("price")
                        macd = indicators.get("macd")
                        macd_sig = indicators.get("macd_signal")
                        rsi = indicators.get("rsi")
                        sma_20 = indicators.get("sma_20")
                        
                        is_macd_bearish = macd is not None and macd_sig is not None and macd < macd_sig
                        is_rsi_bearish = rsi is not None and rsi < 45
                        is_sma_bearish = price and sma_20 and price < sma_20
                        
                        if is_macd_bearish or is_rsi_bearish or is_sma_bearish:
                            outcome = "bearish_warning"
                            exit_price = price
                            
                            reversal_reason = []
                            if is_macd_bearish: reversal_reason.append("MACD Bearish Crossover")
                            if is_rsi_bearish: reversal_reason.append("RSI below 45")
                            if is_sma_bearish: reversal_reason.append("Price below 20-day SMA")
                            
                            from app.services.notifier import send_telegram_reversal_alert
                            send_telegram_reversal_alert(symbol, price, ", ".join(reversal_reason), mode_lower)
            except Exception:
                pass

        if outcome != "pending":
            if outcome == "target_hit":
                target_hits += 1
            elif outcome == "stopped_out":
                stopped_outs += 1

            client.table("recommendations").update({
                "performance_status": outcome,
                "exit_price": exit_price,
            }).eq("id", rec["id"]).execute()

            try:
                from app.services.notifier import send_telegram_profit_alert, send_telegram_exit_alert
                entry_price = float(rec.get("price") or rec.get("buy_price") or rec.get("entry") or 0.0)
                if entry_price == 0.0 and target_price:
                    entry_price = round(target_price / 1.05, 2)

                if outcome == "target_hit":
                    send_telegram_profit_alert(
                        symbol=symbol,
                        target_price=target_price,
                        entry_price=entry_price,
                        trade_mode=rec.get("trade_mode") or "Swing"
                    )
                elif outcome == "stopped_out":
                    send_telegram_exit_alert(
                        symbol=symbol,
                        stop_loss=stop_loss,
                        entry_price=entry_price,
                        trade_mode=rec.get("trade_mode") or "Swing"
                    )
            except Exception:
                pass
        else:
            remain_pending += 1

    return {
        "target_hits": target_hits,
        "stopped_outs": stopped_outs,
        "remain_pending": remain_pending,
    }
