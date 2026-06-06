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


def _get_groww_link(symbol: str, company_name: str | None = None) -> str:
    """Generate dynamic slugified Groww stock link from company name, falling back to symbol."""
    import re
    if not company_name:
        norm_sym = symbol
        if not norm_sym.endswith(".NS") and not norm_sym.endswith(".BO"):
            norm_sym = f"{norm_sym}.NS"
        try:
            # Attempt to pull company name instantly from local DB cache
            from app.services.supabase_store import get_client
            client = get_client()
            if client:
                res = client.table("stocks").select("name").eq("symbol", norm_sym).execute()
                if res and res.data:
                    company_name = res.data[0].get("name")
        except Exception:
            pass

        # Fallback to yfinance profile search
        if not company_name:
            try:
                from app.services.market_data import fetch_stock_profile
                profile = fetch_stock_profile(norm_sym)
                if profile and profile.get("name"):
                    company_name = profile["name"]
            except Exception:
                pass

    if company_name and company_name != symbol:
        # Convert to lowercase
        slug = company_name.lower()
        # Clean up common Indian corporate abbreviations
        slug = slug.replace(" limited", " ltd")
        slug = slug.replace(" corp.", " corp")
        # Strip all non-alphanumeric characters, except spaces/hyphens
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        # Replace spaces/consecutive hyphens with a single hyphen
        slug = re.sub(r'[\s-]+', '-', slug)
        slug = slug.strip('-')
        return f"https://groww.in/stocks/{slug}"

    # Default fallback to lowercase symbol slug
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").lower()
    return f"https://groww.in/stocks/{clean_sym}"


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
        rank = r.get("rank", 1)
        composite = r.get("composite_score", 0)
        target = r.get("target_price")
        stop = r.get("stop_loss")
        reason = r.get("reasoning", "")
        
        # Resolve dynamic company name and Groww slug
        company_name = r.get("stocks", {}).get("name") if isinstance(r.get("stocks"), dict) else None
        groww_link = _get_groww_link(symbol=r.get("symbol", ""), company_name=company_name)
        
        short_reason = reason[:160] + "..." if len(reason) > 160 else reason
        undervalued_tag = " [🔥 UNDERVALUED]" if r.get("is_undervalued") else ""

        message += f"#{rank} *{sym_clean}*{undervalued_tag} • Composite: *{composite}*\n"
        if target and stop:
            message += f"🎯 Target: `₹{target:.2f}` • SL: `₹{stop:.2f}`\n"
        message += f"💼 [Trade on Groww]({groww_link})\n"
        message += f"💡 AI Rationale: _{short_reason}_\n\n"

    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"🔗 Start Trading on Groww: https://groww.in"

    return _send_telegram_msg(message)


def send_telegram_entry_alert(r: dict[str, Any], entry_price: float) -> bool:
    """Format and broadcast a high-probability buy entry alert."""
    sym = r.get("symbol", "").replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    target = r.get("target_price")
    stop = r.get("stop_loss")
    score = r.get("composite_score", 0)
    mode = r.get("trade_mode", "Swing").upper()
    reason = r.get("reasoning", "")

    # Resolve dynamic company name and Groww slug
    company_name = r.get("stocks", {}).get("name") if isinstance(r.get("stocks"), dict) else None
    groww_link = _get_groww_link(symbol=r.get("symbol", ""), company_name=company_name)

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
    message += f"💼 Trade on Groww: {groww_link}"

    return _send_telegram_msg(message)


def send_telegram_profit_alert(symbol: str, target_price: float, entry_price: float, trade_mode: str) -> bool:
    """Format and broadcast a target-hit profit booking alert."""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    
    # Resolve dynamic company name and Groww slug
    groww_link = _get_groww_link(symbol=symbol)
    
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
    message += f"💼 View Stock on Groww: {groww_link}\n"
    message += f"Position closed successfully in the green! Capital objective achieved. 💰"

    return _send_telegram_msg(message)


def send_telegram_exit_alert(symbol: str, stop_loss: float, entry_price: float, trade_mode: str) -> bool:
    """Format and broadcast a stop-loss exit alert to protect capital."""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    
    # Resolve dynamic company name and Groww slug
    groww_link = _get_groww_link(symbol=symbol)
    
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
    message += f"💼 View Stock on Groww: {groww_link}\n"
    message += f"Position closed strictly at stop-loss threshold to manage risks and protect trading capital. 🛡️"

    return _send_telegram_msg(message)


def send_telegram_reversal_alert(symbol: str, price: float, reason: str, trade_mode: str) -> bool:
    """Format and broadcast a trend reversal warning alert to protect capital."""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    sym_clean = sym.upper()
    
    # Resolve dynamic company name and Groww slug
    groww_link = _get_groww_link(symbol=symbol)

    message = f"⚠️ *TECHNICAL TREND REVERSAL* ⚠️\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📉 Ticker: *{sym_clean}* [⚠️ Turned bearish!]\n"
    message += f"💵 Current Live Price: *₹{price:.2f}*\n"
    message += f"📊 Timeframe Mode: *{trade_mode.upper()}*\n"
    message += f"⚡ Reversal Signal: *{reason}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"💼 View Stock on Groww: {groww_link}\n"
    message += f"⚠️ Action Note: The technical trend has reversed to BEARISH. Consider booking profits or exiting position early to manage risks and preserve capital! 🛡️"

    return _send_telegram_msg(message)


def send_institutional_alpha_alert(analysis: dict) -> bool:
    """Fire an institutional-grade alpha alert — only for highest-conviction setups.

    Gate: Alpha > 80, Confidence > 75, R:R > 1:2.
    """
    alpha = analysis.get("alpha_score", 0)
    confidence = analysis.get("confidence_score", 0)
    rr = analysis.get("risk_reward", 0)

    # Hard gate — do not send unless all thresholds met
    if alpha <= 80 or confidence <= 75 or rr <= 2.0:
        return False

    sym = analysis.get("display_symbol", "").upper()
    name = analysis.get("name", sym)
    verdict = analysis.get("verdict", "BUY")
    entry = analysis.get("entry", 0)
    sl = analysis.get("stop_loss", 0)
    t1 = analysis.get("target_1", 0)
    t2 = analysis.get("target_2", 0)
    sector = analysis.get("sector", "N/A")
    reasoning = analysis.get("reasoning", "")

    pillar_scores = analysis.get("pillar_scores", {})

    # Build pillar summary
    pillar_lines = []
    pillar_labels = {
        "trend": "📈 Trend",
        "momentum": "⚡ Momentum",
        "volume": "📊 Volume",
        "volatility": "🌊 Volatility",
        "market_structure": "🏗️ Structure",
        "relative_strength": "💪 Rel. Strength",
        "institutional": "🏦 Institutional",
        "news_sentiment": "📰 News",
    }
    for key, label in pillar_labels.items():
        s = pillar_scores.get(key, 50)
        bar = "█" * int(s / 10) + "░" * (10 - int(s / 10))
        pillar_lines.append(f"  {label}: `{bar}` *{s:.0f}*")

    groww_link = _get_groww_link(symbol=analysis.get("symbol", ""))

    message = f"🔥 *INSTITUTIONAL ALPHA ALERT* 🔥\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"🏛️ *{sym}* — {name}\n"
    message += f"📊 Sector: *{sector}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    message += f"🎯 Alpha Score: *{alpha:.0f}/100*\n"
    message += f"🔒 Confidence: *{confidence:.0f}%*\n"
    message += f"✅ Verdict: *{verdict}*\n\n"
    message += f"📋 *8-PILLAR BREAKDOWN:*\n"
    message += "\n".join(pillar_lines)
    message += f"\n\n"
    message += f"💰 *TRADE PLAN:*\n"
    message += f"  Entry: `₹{entry:.2f}`\n"
    message += f"  Stop Loss: `₹{sl:.2f}`\n"
    message += f"  Target 1: `₹{t1:.2f}`\n"
    message += f"  Target 2: `₹{t2:.2f}`\n"
    message += f"  Risk:Reward: `1:{rr:.1f}`\n\n"
    message += f"💡 _{reasoning[:300]}_\n\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"💼 [Trade on Groww]({groww_link})"

    return _send_telegram_msg(message)


def send_momentum_collapse_alert(symbol: str, price: float, data: dict) -> bool:
    """Alert when momentum collapses across all oscillators simultaneously.

    Fires when: RSI < 40 + MACD histogram declining + Stoch RSI < 20.
    """
    sym = symbol.replace(".NS", "").replace(".BO", "").upper()
    groww_link = _get_groww_link(symbol=symbol)

    rsi = data.get("rsi", 0)
    stoch_k = data.get("stoch_k", 50)
    macd_hist = data.get("macd_histogram", 0)

    message = f"🚨 *MOMENTUM COLLAPSE DETECTED* 🚨\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📉 Ticker: *{sym}*\n"
    message += f"💵 Current Price: *₹{price:.2f}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"⚡ RSI: *{rsi:.1f}* (below 40)\n"
    message += f"📊 Stoch RSI %K: *{stoch_k:.1f}* (below 20)\n"
    message += f"📉 MACD Histogram: *{macd_hist:.4f}* (declining)\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"⚠️ *All momentum indicators have collapsed simultaneously.*\n"
    message += f"🛡️ ACTION: Exit all open positions in {sym} immediately to preserve capital.\n\n"
    message += f"💼 View on Groww: {groww_link}"

    return _send_telegram_msg(message)


def send_trend_reversal_exit_alert(symbol: str, price: float, data: dict) -> bool:
    """Alert when Supertrend flips bearish + price below EMA20.

    This is a stronger exit signal than the basic reversal alert.
    """
    sym = symbol.replace(".NS", "").replace(".BO", "").upper()
    groww_link = _get_groww_link(symbol=symbol)

    supertrend_val = data.get("supertrend_value", 0)
    ema20 = data.get("ema20", 0)

    message = f"🔴 *CONFIRMED TREND REVERSAL — EXIT* 🔴\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📉 Ticker: *{sym}*\n"
    message += f"💵 Current Price: *₹{price:.2f}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"🔻 Supertrend: FLIPPED BEARISH at *₹{supertrend_val:.2f}*\n"
    message += f"🔻 Price below EMA20: *₹{ema20:.2f}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"⚠️ *Dual confirmation: Supertrend bearish flip + EMA20 breakdown.*\n"
    message += f"🛡️ ACTION: Close position to protect capital. Trend structure is broken.\n\n"
    message += f"💼 View on Groww: {groww_link}"

    return _send_telegram_msg(message)
