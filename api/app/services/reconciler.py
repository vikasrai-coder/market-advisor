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

        if outcome != "pending":
            if outcome == "target_hit":
                target_hits += 1
            else:
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
