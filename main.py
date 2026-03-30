#!/usr/bin/env python3
"""
CricketLive Bot — Main entry point
Run: python main.py
"""

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

from config import BOT_TOKEN, ADMIN_IDS
import database as db
from strings import t
from handlers import start_cmd, callback_handler, message_handler
from admin_handlers import admin_cmd, admin_callback, admin_message_handler, is_admin

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── Combined message handler ────────────────────────────────────────────────

async def combined_message_handler(update: Update, context):
    """Route messages: admin state → admin handler, else → user handler."""
    if update.effective_user is None:
        return
    uid = update.effective_user.id
    state = context.user_data.get("admin_state")
    if is_admin(uid) and state:
        await admin_message_handler(update, context)
    else:
        await message_handler(update, context)


# ─── Background job: reminders ───────────────────────────────────────────────

async def job_send_reminders(context):
    pending = db.get_pending_reminders()
    for r in pending:
        try:
            u = db.get_user(r["user_id"])
            lang = u["language"] if u else "en"
            text = t(lang, "reminder_alert", title=r["title"])
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
            logger.info(f"Reminder sent to {r['user_id']} for match {r['match_id']}")
        except Exception as e:
            logger.error(f"Reminder failed for user {r['user_id']}: {e}")


# ─── Background job: live score updates ──────────────────────────────────────

async def job_update_scores(context):
    try:
        from cricapi import fetch_live_matches, format_score
        api_matches = await fetch_live_matches()
        if not api_matches:
            return
        for db_match in db.get_live_matches():
            for api_m in api_matches:
                api_name = (api_m.get("name", "") or "").lower()
                t1 = (db_match.get("team1") or "").lower()
                t2 = (db_match.get("team2") or "").lower()
                if t1 in api_name or t2 in api_name:
                    score = format_score(api_m)
                    if score:
                        db.update_match(db_match["id"], score=score)
                    break
    except Exception as e:
        logger.error(f"Score update error: {e}")


# ─── Error handler ────────────────────────────────────────────────────────────

async def error_handler(update, context):
    logger.error(f"Error: {context.error}", exc_info=context.error)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    logger.info("✅ Database ready")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu",  start_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Callbacks — admin pattern first, then general
    app.add_handler(CallbackQueryHandler(admin_callback,  pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # All text messages (non-command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_message_handler))
    # Photo messages (for admin broadcast with image)
    app.add_handler(MessageHandler(filters.PHOTO, combined_message_handler))

    # Error handler
    app.add_error_handler(error_handler)

    # Background jobs
    app.job_queue.run_repeating(job_send_reminders, interval=60, first=15)
    app.job_queue.run_repeating(job_update_scores,  interval=90, first=30)

    logger.info("🏏 CricketLive Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()

