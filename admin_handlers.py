from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import ADMIN_IDS
import database as db
from keyboards import admin_main_keyboard, admin_match_links_keyboard, admin_pick_language_keyboard


def is_admin(user_id):
    return user_id in ADMIN_IDS


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    await update.message.reply_text(
        "👑 <b>CricketLive Admin Panel</b>\n\n"
        "Matches & scores are fetched automatically from CricAPI.\n"
        "<b>Your only job: add stream links per match.</b>",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    if not is_admin(uid):
        await query.edit_message_text("❌ Unauthorized.")
        return

    # ── Stats ──
    if data == "admin_stats":
        stats = db.get_user_stats()
        top   = db.get_top_matches_today()
        top_text = "\n".join([f"  • {m['title'][:30]}: {m['clicks']} clicks" for m in top]) or "  No data yet"
        total_matches = len(db.get_all_matches_for_admin())
        await query.edit_message_text(
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total users: <b>{stats['total']}</b>\n"
            f"🆕 New today: <b>{stats['today']}</b>\n"
            f"🔥 Active (24h): <b>{stats['active']}</b>\n"
            f"🏏 Matches in DB: <b>{total_matches}</b>\n\n"
            f"🔥 Top matches today:\n{top_text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="admin_back")
            ]])
        )

    # ── List all matches ──
    elif data == "admin_listmatches":
        matches = db.get_all_matches_for_admin()
        if not matches:
            await query.edit_message_text(
                "📋 No matches yet.\n\nMatches are synced automatically from CricAPI every 2 minutes.\n"
                "If empty, CricAPI may have no current data.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="admin_back")
                ]])
            )
            return
        lines = []
        for m in matches:
            emoji  = "🔴" if m["status"]=="live" else "📅" if m["status"]=="upcoming" else "✅"
            links  = db.get_all_links_for_match(m["api_id"])
            linked = f" [{len(links)} links]" if links else " [no links]"
            lines.append(f"{emoji} {m['title'][:35]}{linked}")
        await query.edit_message_text(
            "📋 <b>All Matches</b>\n\n" + "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Add Stream Link", callback_data="admin_addlink")],
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
            ])
        )

    # ── Add link — step 1: pick match ──
    elif data == "admin_addlink":
        matches = db.get_all_matches_for_admin()
        live_upcoming = [m for m in matches if m["status"] in ("live","upcoming")]
        if not live_upcoming:
            await query.edit_message_text(
                "📋 No live or upcoming matches found in DB.\n\n"
                "Matches sync automatically from CricAPI. Try again in a minute.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="admin_back")
                ]])
            )
            return
        await query.edit_message_text(
            "🔗 <b>Add Stream Link</b>\n\nPick the match:",
            parse_mode="HTML",
            reply_markup=admin_match_links_keyboard(live_upcoming)
        )

    # ── Add link — step 2: pick language ──
    elif data.startswith("admin_pickmatch_"):
        api_id = data[16:]
        m      = db.get_match(api_id)
        links  = db.get_all_links_for_match(api_id)
        await query.edit_message_text(
            f"🔗 <b>{m['title']}</b>\n\nPick language to add/update stream link:",
            parse_mode="HTML",
            reply_markup=admin_pick_language_keyboard(api_id, links)
        )

    # ── Add link — step 3: enter URL ──
    elif data.startswith("admin_setlink_"):
        parts    = data.split("_")
        # admin_setlink_{api_id}_{lang_code}
        # api_id may contain underscores — so take last part as lang, rest as api_id
        lang_code = parts[-1]
        api_id    = "_".join(parts[2:-1])
        context.user_data["pending_link_api_id"]  = api_id
        context.user_data["pending_link_lang"]     = lang_code
        context.user_data["admin_state"]           = "awaiting_link_url"
        m = db.get_match(api_id)
        existing = db.get_stream_link(api_id, lang_code)
        msg = (
            f"🔗 <b>Set stream link</b>\n"
            f"Match: <b>{m['title']}</b>\n"
            f"Language: <b>{lang_code.upper()}</b>\n\n"
        )
        if existing:
            msg += f"Current: <code>{existing}</code>\n\n"
        msg += "Send the new stream URL now (must start with http):"
        await query.edit_message_text(msg, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"admin_pickmatch_{api_id}")
            ]])
        )

    # ── Broadcast ──
    elif data == "admin_broadcast":
        stats = db.get_user_stats()
        await query.edit_message_text(
            f"📢 <b>Broadcast</b>\n\n"
            f"Will send to <b>{stats['total']}</b> users.\n\n"
            f"Send your message now (text or photo+caption):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin_back")
            ]])
        )
        context.user_data["admin_state"] = "awaiting_broadcast"

    # ── Back ──
    elif data == "admin_back":
        await query.edit_message_text(
            "👑 <b>Admin Panel</b>",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )


async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    if not is_admin(uid):
        return
    state = context.user_data.get("admin_state")
    text  = update.message.text or ""

    # ── Receive stream URL ──
    if state == "awaiting_link_url":
        api_id    = context.user_data.get("pending_link_api_id")
        lang_code = context.user_data.get("pending_link_lang")
        if not text.startswith("http"):
            await update.message.reply_text("❌ Send a valid URL starting with https://")
            return
        db.set_stream_link(api_id, lang_code, text.strip())
        context.user_data["admin_state"] = None
        m = db.get_match(api_id)
        await update.message.reply_text(
            f"✅ <b>Link saved!</b>\n"
            f"Match: <b>{m['title']}</b>\n"
            f"Language: <b>{lang_code.upper()}</b>\n"
            f"URL: <code>{text.strip()}</code>",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )

    # ── Broadcast ──
    elif state == "awaiting_broadcast":
        context.user_data["admin_state"] = None
        users = db.get_all_user_ids()
        await update.message.reply_text(f"📢 Sending to {len(users)} users...")
        sent = failed = 0
        for user_id in users:
            try:
                if update.message.photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=update.message.photo[-1].file_id,
                        caption=update.message.caption or "",
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=user_id, text=text, parse_mode="HTML"
                    )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Done!\n✅ Sent: {sent}\n❌ Failed: {failed}",
            reply_markup=admin_main_keyboard()
        )
