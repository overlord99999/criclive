#!/usr/bin/env python3
"""
CricketLive Bot — Main entry point
Run: python main.py
"""

import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

from config import BOT_TOKEN
import database as db
from handlers import (
    start_cmd, callback_handler, message_handler
)
from admin_handlers import admin_cmd, admin_callback, admin_message_handler

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── Background jobs ─────────────────────────────────────────────────────────

async def send_reminders(context):
    """Check and send pending reminders every minute."""
    pending = db.get_pending_reminders()
    for r in pending:
        try:
            u = db.get_user(r["user_id"])
            lang = u["language"] if u else "en"
            from strings import t
            text = t(lang, "reminder_alert", title=r["title"])
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            await context.bot.send_message(
                chat_id=r["user_id"],
                text=text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "▶️ Watch Now" if lang == "en" else "▶️ अभी देखें",
                        callback_data=f"match_{r['match_id']}_ipl"
                    )
                ]])
            )
            db.mark_reminder_sent(r["id"])
        except Exception as e:
            logger.error(f"Reminder error for user {r['user_id']}: {e}")


async def auto_update_scores(context):
    """Fetch live scores from CricAPI every 60 seconds and update DB."""
    try:
        from cricapi import fetch_live_matches, format_score
        api_matches = await fetch_live_matches()
        live_matches = db.get_live_matches()

        for db_match in live_matches:
            title_lower = db_match["title"].lower()
            for api_m in api_matches:
                api_name = (api_m.get("name", "") or "").lower()
                if any(team.lower() in api_name for team in
                       [db_match.get("team1",""), db_match.get("team2","")]):
                    score = format_score(api_m)
                    if score:
                        db.update_match(db_match["id"], score=score)
                    break
    except Exception as e:
        logger.error(f"Score update error: {e}")


# ─── Error handler ────────────────────────────────────────────────────────────

async def error_handler(update, context):
    logger.error(f"Update {update} caused error: {context.error}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Init database
    db.init_db()
    logger.info("Database initialized")

    # Build app
    app = Application.builder().token(BOT_TOKEN).build()

    # ── User command handlers ──
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu",  lambda u, c: start_cmd(u, c)))

    # ── Admin command ──
    app.add_handler(CommandHandler("admin", admin_cmd))

    # ── Callback query — admin callbacks handled first ──
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # ── Message handler — admin messages handled first ──
    
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _combined_message_handler
    ))
    # ── Error handler ──
    app.add_error_handler(error_handler)

    # ── Background jobs ──
    job_queue = app.job_queue
    job_queue.run_repeating(send_reminders,    interval=60,  first=10)
    job_queue.run_repeating(auto_update_scores, interval=90, first=30)

    logger.info("🏏 CricketLive Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


async def _combined_message_handler(update: Update, context):
    """Route messages to admin or user handler based on state."""
    from config import ADMIN_IDS
    from admin_handlers import is_admin

    uid = update.effective_user.id
    state = context.user_data.get("admin_state")

    if is_admin(uid) and state:
        await admin_message_handler(update, context)
    else:
        await message_handler(update, context)


if __name__ == "__main__":
    main()
