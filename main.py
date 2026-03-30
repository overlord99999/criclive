#!/usr/bin/env python3
"""CricketLive Bot v2 — Auto match sync from CricAPI"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import BOT_TOKEN, ADMIN_IDS
import database as db
from strings import t
from handlers import start_cmd, callback_handler, message_handler
from admin_handlers import admin_cmd, admin_callback, admin_message_handler, is_admin

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ── Combined text handler ─────────────────────────────────────────────────────

async def combined_message(update: Update, context):
    if not update.effective_user:
        return
    uid   = update.effective_user.id
    state = context.user_data.get("admin_state")
    if is_admin(uid) and state:
        await admin_message_handler(update, context)
    else:
        await message_handler(update, context)


# ── Background: sync matches from CricAPI every 2 minutes ────────────────────

async def job_sync_matches(context):
    """Auto-fetch all live + upcoming matches from CricAPI and upsert to DB."""
    try:
        from cricapi import fetch_current_matches, fetch_upcoming_matches
        live_matches = await fetch_current_matches()
        for m in live_matches:
            if m["api_id"]:
                db.upsert_match(m)

        upcoming = await fetch_upcoming_matches()
        for m in upcoming:
            if m["api_id"]:
                db.upsert_match(m)

        total = len(live_matches) + len(upcoming)
        if total:
            logger.info(f"[Sync] Updated {len(live_matches)} live + {len(upcoming)} upcoming matches")
    except Exception as e:
        logger.error(f"[Sync] Error: {e}")


# ── Background: send reminders ────────────────────────────────────────────────

async def job_reminders(context):
    pending = db.get_pending_reminders()
    for r in pending:
        try:
            u    = db.get_user(r["user_id"])
            lang = u["language"] if u else "en"
            text = t(lang, "reminder_alert", title=r["title"])
            await context.bot.send_message(
                chat_id=r["user_id"], text=text, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "▶️ Watch Now" if lang=="en" else "▶️ अभी देखें",
                        callback_data=f"match_{r['api_id']}_ipl"
                    )
                ]])
            )
            db.mark_reminder_sent(r["id"])
        except Exception as e:
            logger.error(f"[Reminder] user {r['user_id']}: {e}")


# ── Error handler ─────────────────────────────────────────────────────────────

async def on_error(update, context):
    logger.error(f"Error: {context.error}", exc_info=context.error)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    logger.info("✅ Database ready")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu",  start_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))

    app.add_handler(CallbackQueryHandler(admin_callback,  pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.add_handler(MessageHandler(filters.TEXT  & ~filters.COMMAND, combined_message))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, combined_message))

    app.add_error_handler(on_error)

    # Sync matches every 2 min, start immediately
    app.job_queue.run_repeating(job_sync_matches, interval=120, first=5)
    # Check reminders every minute
    app.job_queue.run_repeating(job_reminders,    interval=60,  first=15)

    logger.info("🏏 CricketLive Bot v2 running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
