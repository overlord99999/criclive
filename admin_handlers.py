from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import ADMIN_IDS
import database as db
from keyboards import admin_main_keyboard, admin_match_actions_keyboard, admin_links_keyboard

# Conversation states
(
    ADMIN_MATCH_TITLE, ADMIN_MATCH_TEAM1, ADMIN_MATCH_TEAM2,
    ADMIN_MATCH_TYPE, ADMIN_MATCH_VENUE, ADMIN_MATCH_TIME, ADMIN_MATCH_IPL,
    ADMIN_LINK_URL,
    ADMIN_BROADCAST_MSG,
    ADMIN_EDIT_FIELD, ADMIN_EDIT_VALUE,
    ADMIN_SCORE_INPUT,
) = range(12)


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ─── /admin command ──────────────────────────────────────────────────────────

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized.")
        return
    await update.message.reply_text(
        "👑 <b>CricketLive Bot — Admin Panel</b>\n\nChoose an action:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )


# ─── Admin callback router ───────────────────────────────────────────────────

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if not is_admin(uid):
        await query.edit_message_text("❌ Unauthorized.")
        return

    # ── Stats ──
    if data == "admin_stats":
        stats = db.get_user_stats()
        top = db.get_top_matches_today()
        top_text = "\n".join([f"  • {m['title']}: {m['clicks']} clicks" for m in top]) or "  No data yet"
        text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total users: <b>{stats['total']}</b>\n"
            f"🆕 New today: <b>{stats['today']}</b>\n"
            f"🔥 Active (24h): <b>{stats['active']}</b>\n\n"
            f"🏏 Top matches today:\n{top_text}"
        )
        await query.edit_message_text(text, parse_mode="HTML",
                                      reply_markup=InlineKeyboardMarkup([[
                                          InlineKeyboardButton("⬅️ Back", callback_data="admin_back")
                                      ]]))

    # ── List all matches ──
    elif data == "admin_listmatches":
        matches = db.get_all_matches(only_visible=False)
        if not matches:
            await query.edit_message_text(
                "📋 No matches yet. Add one first.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Add Match", callback_data="admin_addmatch"),
                    InlineKeyboardButton("⬅️ Back", callback_data="admin_back"),
                ]])
            )
            return
        buttons = []
        for m in matches:
            vis = "👁️" if m["is_visible"] else "🚫"
            status_icons = {"live": "🔴", "upcoming": "📅", "ended": "✅"}
            s = status_icons.get(m["status"], "❓")
            buttons.append([InlineKeyboardButton(
                f"{vis} {s} {m['title'][:30]}",
                callback_data=f"admin_match_{m['id']}"
            )])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_back")])
        await query.edit_message_text(
            "📋 <b>All Matches:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ── Single match actions ──
    elif data.startswith("admin_match_"):
        match_id = int(data.split("_")[2])
        m = db.get_match(match_id)
        if not m:
            await query.edit_message_text("❌ Match not found.")
            return
        links = db.get_all_stream_links(match_id)
        links_text = "\n".join([f"  • {l['language'].upper()}: {'✅' if l['is_active'] else '❌'}" for l in links]) or "  None added"
        text = (
            f"🏏 <b>{m['title']}</b>\n"
            f"📍 {m.get('venue','—')} | 🕐 {m.get('start_time','—')}\n"
            f"Status: <b>{m['status'].upper()}</b> | IPL: {'Yes' if m['is_ipl'] else 'No'}\n\n"
            f"🔗 Stream links:\n{links_text}"
        )
        await query.edit_message_text(text, parse_mode="HTML",
                                      reply_markup=admin_match_actions_keyboard(match_id))

    # ── Set match status ──
    elif data.startswith("admin_status_"):
        parts = data.split("_")
        status = parts[2]
        match_id = int(parts[3])
        db.update_match_status(match_id, status)
        await query.answer(f"✅ Status set to {status}", show_alert=True)
        m = db.get_match(match_id)
        await query.edit_message_text(
            f"✅ Match <b>{m['title']}</b> status → <b>{status.upper()}</b>",
            parse_mode="HTML",
            reply_markup=admin_match_actions_keyboard(match_id)
        )

    # ── Delete match ──
    elif data.startswith("admin_delete_"):
        match_id = int(data.split("_")[2])
        m = db.get_match(match_id)
        await query.edit_message_text(
            f"⚠️ Delete <b>{m['title']}</b>?\nThis will also remove all stream links.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, delete", callback_data=f"admin_confirmdelete_{match_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"admin_match_{match_id}"),
                ]
            ])
        )

    elif data.startswith("admin_confirmdelete_"):
        match_id = int(data.split("_")[2])
        db.delete_match(match_id)
        await query.edit_message_text("🗑️ Match deleted.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to matches", callback_data="admin_listmatches")
        ]]))

    # ── Links management ──
    elif data.startswith("admin_links_"):
        match_id = int(data.split("_")[2])
        links = db.get_all_stream_links(match_id)
        m = db.get_match(match_id)
        await query.edit_message_text(
            f"🔗 <b>Stream links for:</b>\n{m['title']}\n\nTap a language to add/update its link:",
            parse_mode="HTML",
            reply_markup=admin_links_keyboard(match_id, links)
        )

    elif data.startswith("admin_setlink_"):
        parts = data.split("_")
        match_id = int(parts[2])
        lang_code = parts[3]
        context.user_data["pending_link_match"] = match_id
        context.user_data["pending_link_lang"] = lang_code
        m = db.get_match(match_id)
        existing = db.get_stream_link(match_id, lang_code)
        msg = (
            f"🔗 <b>Set stream link</b>\n"
            f"Match: {m['title']}\n"
            f"Language: <b>{lang_code.upper()}</b>\n\n"
        )
        if existing:
            msg += f"Current: <code>{existing}</code>\n\n"
        msg += "Send the new stream URL now:"
        await query.edit_message_text(msg, parse_mode="HTML",
                                      reply_markup=InlineKeyboardMarkup([[
                                          InlineKeyboardButton("❌ Cancel", callback_data=f"admin_links_{match_id}")
                                      ]]))
        context.user_data["admin_state"] = "awaiting_link_url"

    # ── Broadcast ──
    elif data == "admin_broadcast":
        stats = db.get_user_stats()
        await query.edit_message_text(
            f"📢 <b>Broadcast Message</b>\n\n"
            f"Will be sent to <b>{stats['total']}</b> users.\n\n"
            f"Send your message now (text, photo+caption, etc.):\n"
            f"Type /cancel to abort.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin_back")
            ]])
        )
        context.user_data["admin_state"] = "awaiting_broadcast"

    # ── Add match flow — start ──
    elif data == "admin_addmatch":
        context.user_data["new_match"] = {}
        await query.edit_message_text(
            "➕ <b>Add New Match</b>\n\n"
            "Step 1/6: Send the <b>full match title</b>\n"
            "Example: <code>India vs Australia — IPL 2025 Match 34</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin_back")
            ]])
        )
        context.user_data["admin_state"] = "add_match_title"

    # ── Back ──
    elif data == "admin_back":
        await query.edit_message_text(
            "👑 <b>Admin Panel</b>\n\nChoose an action:",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )


# ─── Admin message handler ───────────────────────────────────────────────────

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    state = context.user_data.get("admin_state")
    text = update.message.text or ""

    # ── Link URL input ──
    if state == "awaiting_link_url":
        match_id = context.user_data.get("pending_link_match")
        lang_code = context.user_data.get("pending_link_lang")
        if not text.startswith("http"):
            await update.message.reply_text("❌ Please send a valid URL starting with http/https")
            return
        db.update_stream_link(match_id, lang_code, text.strip())
        context.user_data["admin_state"] = None
        m = db.get_match(match_id)
        await update.message.reply_text(
            f"✅ Stream link saved!\n"
            f"Match: <b>{m['title']}</b>\n"
            f"Language: <b>{lang_code.upper()}</b>\n"
            f"URL: <code>{text.strip()}</code>",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )

    # ── Broadcast message ──
    elif state == "awaiting_broadcast":
        users = db.get_all_users()
        context.user_data["admin_state"] = None
        sent = 0
        failed = 0
        await update.message.reply_text(f"📢 Sending to {len(users)} users...")
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
                        chat_id=user_id,
                        text=text,
                        parse_mode="HTML"
                    )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}",
            reply_markup=admin_main_keyboard()
        )

    # ── Add match flow ──
    elif state == "add_match_title":
        context.user_data["new_match"]["title"] = text
        context.user_data["admin_state"] = "add_match_team1"
        await update.message.reply_text(
            "Step 2/6: Send <b>Team 1 name</b> (e.g. India):", parse_mode="HTML"
        )

    elif state == "add_match_team1":
        context.user_data["new_match"]["team1"] = text
        context.user_data["admin_state"] = "add_match_team2"
        await update.message.reply_text(
            "Step 3/6: Send <b>Team 2 name</b> (e.g. Australia):", parse_mode="HTML"
        )

    elif state == "add_match_team2":
        context.user_data["new_match"]["team2"] = text
        context.user_data["admin_state"] = "add_match_type"
        await update.message.reply_text(
            "Step 4/6: Match type? (T20 / ODI / Test / T10):"
        )

    elif state == "add_match_type":
        context.user_data["new_match"]["match_type"] = text.upper()
        context.user_data["admin_state"] = "add_match_venue"
        await update.message.reply_text(
            "Step 5/6: <b>Venue</b> (e.g. Wankhede Stadium, Mumbai):", parse_mode="HTML"
        )

    elif state == "add_match_venue":
        context.user_data["new_match"]["venue"] = text
        context.user_data["admin_state"] = "add_match_time"
        await update.message.reply_text(
            "Step 6/6: <b>Start time</b>\nFormat: <code>2025-04-15 19:30</code>", parse_mode="HTML"
        )

    elif state == "add_match_time":
        context.user_data["new_match"]["start_time"] = text
        context.user_data["admin_state"] = "add_match_ipl"
        await update.message.reply_text(
            "Is this an <b>IPL match</b>? Reply: yes / no", parse_mode="HTML"
        )

    elif state == "add_match_ipl":
        nm = context.user_data["new_match"]
        is_ipl = 1 if text.lower() in ["yes", "y", "haan", "ha"] else 0
        mid = db.add_match(
            title=nm["title"],
            team1=nm["team1"],
            team2=nm["team2"],
            match_type=nm.get("match_type", "T20"),
            venue=nm.get("venue", ""),
            start_time=nm.get("start_time", ""),
            is_ipl=is_ipl
        )
        context.user_data["admin_state"] = None
        context.user_data["new_match"] = {}
        await update.message.reply_text(
            f"✅ <b>Match added!</b> (ID: {mid})\n\n"
            f"🏏 {nm['title']}\n"
            f"Now add stream links via Admin → All Matches → {nm['title'][:20]}",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )

    # ── Score update ──
    elif state and state.startswith("update_score_"):
        match_id = int(state.split("_")[2])
        db.update_match(match_id, score=text)
        context.user_data["admin_state"] = None
        await update.message.reply_text(f"✅ Score updated: <code>{text}</code>", parse_mode="HTML")
