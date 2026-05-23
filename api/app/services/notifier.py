"""Telegram notification service to broadcast top recommendations to channels."""

import logging
import os
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("app.notifier")


def send_telegram_recommendations(recs: list[dict[str, Any]], mode_label: str = "Swing Trade") -> bool:
    """Format and broadcast top picks to the specified Telegram channel/chat.

    Looks for TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID environment variables.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not token or not channel_id:
        logger.info("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not configured.")
        return False

    if not recs:
        return False

    # Format broadcast message
    message = f"🚨 *MARKET ADVISOR BREAKOUT ALERTS* 🚨\n"
    message += f"📊 Timeframe Mode: *{mode_label}*\n"
    message += f"📅 Target Execution Date: *{recs[0].get('trade_date', 'Next Session')}*\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for r in recs[:5]:  # Broadcast top 5 picks to keep message concise
        sym = r.get("symbol", "").replace(".NS", "").replace(".BO", "")
        rank = r.get("rank", 1)
        composite = r.get("composite_score", 0)
        target = r.get("target_price")
        stop = r.get("stop_loss")
        reason = r.get("reasoning", "")
        
        # Format reasoning to fit within limits
        short_reason = reason[:160] + "..." if len(reason) > 160 else reason
        undervalued_tag = " [🔥 UNDERVALUED]" if r.get("is_undervalued") else ""

        message += f"#{rank} *{sym}*{undervalued_tag} • Composite: *{composite}*\n"
        if target and stop:
            message += f"🎯 Target: `₹{target:.2f}` • SL: `₹{stop:.2f}`\n"
        message += f"💡 AI Rationale: _{short_reason}_\n\n"

    message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"🔗 View live charts at: {os.getenv('NEXT_PUBLIC_APP_URL', 'http://localhost:3000')}"

    # Send request using standard urllib (no external requests lib dependency needed)
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
