"""Telegram notification service to broadcast top recommendations and trade alerts to channels."""

import logging
import os
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("app.notifier")


def _send_telegram_msg(message: str) -> bool:
    """Helper function to post Markdown messages using urllib."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not token or not channel_id:
        logger.info("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not configured.")
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": channel_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            logger.info("Telegram broadcast posted successfully.")
            return "ok" in res_body.lower()
    except Exception as exc:
        logger.error(f"Failed to post Telegram broadcast: {exc}")
        return False


def send_telegram_recommendations(recs: list[dict[str, Any]], mode_label: str = "Swing Trade") -> bool:
    """Format and broadcast top picks to the specified Telegram channel/chat."""
    if not recs:
        return False

    message = f"🚨 *MARKET ADVISOR BREAKOUT ALERTS* 🚨\n"
    message += f"📊 Timeframe Mode: *{mode_label}*\n"
    message += f"📅 Target Execution Date: *{recs[0].get('trade_date', 'Next Session')}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for r in recs[:5]:  # Broadcast top 5 picks to keep message concise
        sym = r.get("symbol", "").replace(".NS", "").replace(".BO", "")
        sym_clean = sym.upper()
        sym_lower = sym.lower()
        rank = r.get("rank", 1)
        composite = r.get("composite_score", 0)
        target = r.get("target_price")
        stop = r.get("stop_loss")
        reason = r.get("reasoning", "")
        
        short_reason = reason[:160] + "..." if len(reason) > 160 else reason
        undervalued_tag = " [🔥 UNDERVALUED]" if r.get("is_undervalued") else ""

        message += f"#{rank} *{sym_clean}*{undervalued_tag} • Composite: *{composite}*\n"
        if target and stop:
            message += f"🎯 Target: `₹{target:.2f}` • SL: `₹{stop:.2f}`\n"
        message += f"💼 [Trade on Groww](https://groww.in/stocks/{sym_lower})\n"
        message += f"💡 AI Rationale: _{short_reason}_\n\n"

    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"🔗 Start Trading on Groww: https://groww.in"

    return _send_telegram_msg(message)


def send_telegram_entry_alert(r: dict[str, Any], entry_price: float) -> bool:
    """Format and broadcast a high-probability buy entry alert."""
    sym = r.get("symbol", "").replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    sym_lower = sym.lower()
    target = r.get("target_price")
    stop = r.get("stop_loss")
    score = r.get("composite_score", 0)
    mode = r.get("trade_mode", "Swing").upper()
    reason = r.get("reasoning", "")

    # Calculate potential gain
    gain_pct = 0.0
    if entry_price > 0 and target:
        gain_pct = ((target - entry_price) / entry_price) * 100

    undervalued_tag = " [🔥 PRIME UNDERVALUED]" if r.get("is_undervalued") else " [🚀 TREND BREAKOUT]"

    message = f"🚨 *HIGH-PROBABILITY BUY ENTRY* 🚨\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📈 Ticker: *{sym_clean}*{undervalued_tag}\n"
    message += f"📊 Trade Mode: *{mode}*\n"
    message += f"⚡ Signal Score: *{score}*\n"
    message += f"💵 Recommended Entry Zone: *₹{entry_price:.2f}*\n"
    if target:
        message += f"🎯 Profit Booking Target: *₹{target:.2f}* (+{gain_pct:.1f}%)\n"
    if stop:
        message += f"🛡️ Stop Loss Protection: *₹{stop:.2f}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    if reason:
        message += f"💡 AI Rationale: _{reason[:250]}_\n\n"
    message += f"💼 Trade on Groww: https://groww.in/stocks/{sym_lower}"

    return _send_telegram_msg(message)


def send_telegram_profit_alert(symbol: str, target_price: float, entry_price: float, trade_mode: str) -> bool:
    """Format and broadcast a target-hit profit booking alert."""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    sym_lower = sym.lower()
    
    gain_pct = 0.0
    if entry_price > 0:
        gain_pct = ((target_price - entry_price) / entry_price) * 100

    message = f"🎉 *PROFIT BOOKING ACHIEVED* 🎉\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"🚀 Ticker: *{sym_clean}* [🔥 target hit]\n"
    message += f"🏆 Target Price Reached: *₹{target_price:.2f}*\n"
    if entry_price > 0:
        message += f"💵 Initial Buy Entry: *₹{entry_price:.2f}*\n"
        message += f"📈 Net Profit Secured: *+{gain_pct:.1f}%* profit booked!\n"
    message += f"📊 Timeframe Mode: *{trade_mode.upper()}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"💼 View Stock on Groww: https://groww.in/stocks/{sym_lower}\n"
    message += f"Position closed successfully in the green! Capital objective achieved. 💰"

    return _send_telegram_msg(message)


def send_telegram_exit_alert(symbol: str, stop_loss: float, entry_price: float, trade_mode: str) -> bool:
    """Format and broadcast a stop-loss exit alert to protect capital."""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    sym_lower = sym.lower()
    
    loss_pct = 0.0
    if entry_price > 0:
        loss_pct = ((entry_price - stop_loss) / entry_price) * 100

    message = f"⚠️ *EXIT SYSTEM / STOP LOSS HIT* ⚠️\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📉 Ticker: *{sym_clean}* [❌ stop loss triggered]\n"
    message += f"🛡️ Stop Price Triggered: *₹{stop_loss:.2f}*\n"
    if entry_price > 0:
        message += f"💵 Initial Buy Entry: *₹{entry_price:.2f}*\n"
        message += f"📉 Capital Drawdown: *-{loss_pct:.1f}%*\n"
    message += f"📊 Timeframe Mode: *{trade_mode.upper()}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"💼 View Stock on Groww: https://groww.in/stocks/{sym_lower}\n"
    message += f"Position closed strictly at stop-loss threshold to manage risks and protect trading capital. 🛡️"

    return _send_telegram_msg(message)
