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
    await _send_admin_home(update.message.reply_text)


async def _send_admin_home(send_fn):
    stats = db.get_user_stats()
    await send_fn(
        f"👑 <b>CricketLive Admin Panel</b>\n\n"
        f"👥 Users: <b>{stats['total']}</b>  |  "
        f"🆕 Today: <b>{stats['today']}</b>  |  "
        f"🔥 Active: <b>{stats['active']}</b>\n\n"
        f"Matches sync automatically from CricAPI.\n"
        f"<b>Your only job: paste stream links.</b>",
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
        top_text = "\n".join([f"  • {m['title'][:32]}: {m['clicks']} clicks" for m in top]) or "  No data yet"
        all_m    = db.get_all_matches_for_admin()
        live_c   = sum(1 for m in all_m if m["status"]=="live")
        up_c     = sum(1 for m in all_m if m["status"]=="upcoming")
        await query.edit_message_text(
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total users: <b>{stats['total']}</b>\n"
            f"🆕 New today: <b>{stats['today']}</b>\n"
            f"🔥 Active (24h): <b>{stats['active']}</b>\n\n"
            f"🏏 Matches in DB: <b>{len(all_m)}</b> "
            f"({live_c} live, {up_c} upcoming)\n\n"
            f"📈 Top matches today:\n{top_text}",
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
                "📋 No matches in DB yet.\n\nMatches are auto-synced from CricAPI every 2 minutes.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="admin_back")
                ]])
            )
            return

        lines = []
        for m in matches:
            emoji  = "🔴" if m["status"]=="live" else "📅" if m["status"]=="upcoming" else "✅"
            ipl    = " [IPL]" if m["is_ipl"] else ""
            links  = db.get_all_links_for_match(m["api_id"])
            linked = f" ✅{len(links)}" if links else " ➕"
            lines.append(f"{emoji}{ipl} {m['title'][:32]}{linked}")

        await query.edit_message_text(
            "📋 <b>All Matches</b>\n"
            "<i>✅N = N links added  |  ➕ = no links yet</i>\n\n"
            + "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Add Stream Link", callback_data="admin_addlink")],
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
            ])
        )

    # ── Add link — step 1: pick category ──
    elif data == "admin_addlink":
        await query.edit_message_text(
            "🔗 <b>Add Stream Link</b>\n\nWhich type of match?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏆 IPL Matches",        callback_data="admin_filtermatches_ipl")],
                [InlineKeyboardButton("🌍 Other Cricket",      callback_data="admin_filtermatches_other")],
                [InlineKeyboardButton("🔴 All Live Now",       callback_data="admin_filtermatches_live")],
                [InlineKeyboardButton("📅 All Upcoming",       callback_data="admin_filtermatches_upcoming")],
                [InlineKeyboardButton("⬅️ Back",              callback_data="admin_back")],
            ])
        )

    # ── Add link — step 2: show filtered match list ──
    elif data.startswith("admin_filtermatches_"):
        ftype   = data.split("_")[2]
        all_m   = db.get_all_matches_for_admin()

        if ftype == "ipl":
            matches = [m for m in all_m if m["is_ipl"]]
            label   = "IPL"
        elif ftype == "other":
            matches = [m for m in all_m if not m["is_ipl"]]
            label   = "Other"
        elif ftype == "live":
            matches = [m for m in all_m if m["status"]=="live"]
            label   = "Live"
        else:
            matches = [m for m in all_m if m["status"]=="upcoming"]
            label   = "Upcoming"

        if not matches:
            await query.edit_message_text(
                f"📋 No {label} matches found in DB.\n\n"
                f"Matches sync every 2 min from CricAPI.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="admin_addlink")
                ]])
            )
            return

        await query.edit_message_text(
            f"🔗 <b>{label} Matches</b>\n\nPick match to add/edit stream link:",
            parse_mode="HTML",
            reply_markup=admin_match_links_keyboard(matches)
        )

    # ── Add link — step 3: pick language ──
    elif data.startswith("admin_pickmatch_"):
        api_id = data[16:]
        m      = db.get_match(api_id)
        if not m:
            await query.edit_message_text("❌ Match not found.")
            return
        links  = db.get_all_links_for_match(api_id)

        existing_text = ""
        if links:
            existing_text = "\n<b>Existing links:</b>\n" + "\n".join(
                [f"  • {l['language'].upper()}: <code>{l['url'][:40]}...</code>" for l in links]
            )

        await query.edit_message_text(
            f"🔗 <b>{m['title']}</b>\n"
            f"📌 Status: {m['status'].upper()}\n"
            f"{existing_text}\n\n"
            f"Pick language to add/update link:",
            parse_mode="HTML",
            reply_markup=admin_pick_language_keyboard(api_id, links)
        )

    # ── Add link — step 4: enter URL ──
    elif data.startswith("admin_setlink_"):
        parts     = data.split("_")
        lang_code = parts[-1]
        api_id    = "_".join(parts[2:-1])
        context.user_data["pending_link_api_id"] = api_id
        context.user_data["pending_link_lang"]   = lang_code
        context.user_data["admin_state"]         = "awaiting_link_url"

        m        = db.get_match(api_id)
        existing = db.get_stream_link(api_id, lang_code)
        msg = (
            f"🔗 <b>Set Stream Link</b>\n\n"
            f"📺 Match: <b>{m['title']}</b>\n"
            f"🌐 Language: <b>{lang_code.upper()}</b>\n\n"
        )
        if existing:
            msg += f"Current URL:\n<code>{existing}</code>\n\n"
        msg += "Send the new stream URL now:"

        await query.edit_message_text(msg, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"admin_pickmatch_{api_id}")
            ]])
        )

    # ── Broadcast ──
    elif data == "admin_broadcast":
        stats = db.get_user_stats()
        await query.edit_message_text(
            f"📢 <b>Broadcast Message</b>\n\n"
            f"Will send to <b>{stats['total']}</b> users.\n\n"
            f"Send your message now (text or photo + caption):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin_back")
            ]])
        )
        context.user_data["admin_state"] = "awaiting_broadcast"

    elif data == "admin_back":
        stats = db.get_user_stats()
        await query.edit_message_text(
            f"👑 <b>Admin Panel</b>\n\n"
            f"👥 Users: <b>{stats['total']}</b>  |  "
            f"🆕 Today: <b>{stats['today']}</b>  |  "
            f"🔥 Active: <b>{stats['active']}</b>",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )


async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    if not is_admin(uid):
        return
    state = context.user_data.get("admin_state")
    text  = update.message.text or ""

    if state == "awaiting_link_url":
        api_id    = context.user_data.get("pending_link_api_id")
        lang_code = context.user_data.get("pending_link_lang")
        if not text.startswith("http"):
            await update.message.reply_text(
                "❌ Invalid URL. Must start with https://\nSend again or /admin to cancel."
            )
            return
        db.set_stream_link(api_id, lang_code, text.strip())
        context.user_data["admin_state"] = None
        m = db.get_match(api_id)
        await update.message.reply_text(
            f"✅ <b>Stream link saved!</b>\n\n"
            f"📺 <b>{m['title']}</b>\n"
            f"🌐 Language: <b>{lang_code.upper()}</b>\n"
            f"🔗 URL: <code>{text.strip()}</code>\n\n"
            f"Users can now watch in {lang_code.upper()}!",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )

    elif state == "awaiting_broadcast":
        context.user_data["admin_state"] = None
        users = db.get_all_user_ids()
        status_msg = await update.message.reply_text(f"📢 Sending to {len(users)} users...")
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
        await status_msg.edit_text(
            f"✅ <b>Broadcast done!</b>\n\n"
            f"✅ Sent: <b>{sent}</b>\n"
            f"❌ Failed: <b>{failed}</b>",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard()
        )
