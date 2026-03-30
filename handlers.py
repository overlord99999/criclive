from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timedelta

import database as db
from config import REQUIRED_CHANNELS, MAIN_MENU_IMG_URL, WELCOME_IMG_URL, LINK_COMING_MINUTES, BOT_NAME, LANGUAGES
from strings import t, STATUS_EMOJI
from keyboards import (
    welcome_keyboard, first_language_keyboard, main_menu_keyboard,
    match_list_keyboard, match_detail_keyboard, stream_keyboard,
    no_link_keyboard, reminders_keyboard, change_language_keyboard,
)


# ── Channel membership check ─────────────────────────────────────────────────

async def check_membership(bot, user_id):
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(f"@{ch['username']}", user_id)
            if member.status in ("left", "kicked", "banned"):
                return False, ch
        except Exception:
            return False, ch
    return True, None


# ── /start ───────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    u = db.get_user(user.id)
    lang = u["language"] if u else "en"

    # New user — ask language first
    if not u or u.get("language") is None:
        await update.message.reply_text(
            "🌐 <b>Choose your language / भाषा चुनें:</b>",
            parse_mode="HTML",
            reply_markup=first_language_keyboard()
        )
        return

    await send_welcome_gate(update.message, context, user.id, lang)


async def send_welcome_gate(msg_obj, context, user_id, lang):
    text = (
        f"<b>{BOT_NAME}</b>\n\n"
        f"{t(lang, 'welcome_body')}"
    )
    try:
        await context.bot.send_photo(
            chat_id=user_id, photo=WELCOME_IMG_URL,
            caption=text, parse_mode="HTML",
            reply_markup=welcome_keyboard(lang)
        )
    except Exception:
        await context.bot.send_message(
            chat_id=user_id, text=text,
            parse_mode="HTML", reply_markup=welcome_keyboard(lang)
        )


# ── Main menu ────────────────────────────────────────────────────────────────

async def send_main_menu(context, user_id, lang):
    live = db.get_live_matches()
    live_info = t(lang, "live_info_yes", count=len(live)) if live else t(lang, "live_info_no")
    u = db.get_user(user_id)
    name = (u["first_name"] if u else None) or "Cricket Fan"
    text = t(lang, "main_menu", name=name, live_info=live_info)
    try:
        await context.bot.send_photo(
            chat_id=user_id, photo=MAIN_MENU_IMG_URL,
            caption=text, parse_mode="HTML",
            reply_markup=main_menu_keyboard(lang)
        )
    except Exception:
        await context.bot.send_message(
            chat_id=user_id, text=text,
            parse_mode="HTML", reply_markup=main_menu_keyboard(lang)
        )


# ── Callback handler ─────────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    user  = query.from_user
    db.upsert_user(user.id, user.username, user.first_name)
    u     = db.get_user(user.id)
    lang  = u["language"] if u else "en"

    # ── First-time language pick ──
    if data.startswith("setlang_"):
        code = data.split("_")[1]
        db.set_user_language(user.id, code)
        try:
            await query.edit_message_text(
                f"✅ Language set!\n\nWelcome to <b>{BOT_NAME}</b>! 🏏",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await send_welcome_gate(query.message, context, user.id, code)
        return

    # ── Verify join ──
    if data == "verify_join":
        ok, missing = await check_membership(context.bot, user.id)
        if ok:
            try:
                await query.edit_message_caption(caption=t(lang, "joined_ok"), parse_mode="HTML")
            except Exception:
                try:
                    await query.edit_message_text(t(lang, "joined_ok"), parse_mode="HTML")
                except Exception:
                    pass
            await send_main_menu(context, user.id, lang)
        else:
            ch_name = missing["name"] if missing else "our channel"
            msg = t(lang, "not_joined") + f"\n\n👉 Still need to join: <b>{ch_name}</b>"
            try:
                await query.edit_message_caption(caption=msg, parse_mode="HTML", reply_markup=welcome_keyboard(lang))
            except Exception:
                try:
                    await query.edit_message_text(msg, parse_mode="HTML", reply_markup=welcome_keyboard(lang))
                except Exception:
                    pass
        return

    # ── All further actions require membership ──
    ok, missing = await check_membership(context.bot, user.id)
    if not ok:
        ch_name = missing["name"] if missing else "our channel"
        await query.answer(f"⚠️ Please join {ch_name} first!", show_alert=True)
        return

    # ── Back to main menu ──
    if data == "back_main":
        await send_main_menu(context, user.id, lang)
        return

    # ── Match list ──
    if data.startswith("list_"):
        category = data[5:]
        await show_match_list(query, category, lang)
        return

    # ── Match detail ──
    if data.startswith("match_"):
        parts = data.split("_", 2)
        api_id   = parts[1]
        category = parts[2] if len(parts) > 2 else "live"
        await show_match_detail(query, api_id, category, lang)
        return

    # ── Stream request ──
    if data.startswith("stream_"):
        parts    = data.split("_", 2)
        api_id   = parts[1]
        lang_code = parts[2]
        await deliver_stream(query, context, api_id, lang_code, lang, user.id)
        return

    # ── Set reminder ──
    if data.startswith("remind_"):
        api_id = data[7:]
        m = db.get_match(api_id)
        if not m:
            await query.answer("Match not found.", show_alert=True)
            return
        try:
            start = datetime.fromisoformat(m["start_time"].replace("Z", "+00:00"))
            from datetime import timezone
            remind_at = (start - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            added = db.add_reminder(user.id, api_id, remind_at)
            if added:
                await query.answer(t(lang, "reminder_set"), show_alert=True)
            else:
                await query.answer(t(lang, "reminder_exists"), show_alert=True)
        except Exception:
            await query.answer("Could not set reminder — invalid match time.", show_alert=True)
        return

    # ── Cancel reminder ──
    if data.startswith("cancelremind_"):
        api_id = data[13:]
        db.delete_reminder(user.id, api_id)
        await query.answer(t(lang, "reminder_cancelled"), show_alert=True)
        reminders = db.get_user_reminders(user.id)
        if reminders:
            txt = t(lang, "reminder_list_hd")
            for r in reminders:
                txt += t(lang, "reminder_item", title=r["title"], remind_at=r.get("start_display",""))
            await query.edit_message_text(txt, parse_mode="HTML",
                                          reply_markup=reminders_keyboard(reminders, lang))
        else:
            await query.edit_message_text(
                t(lang, "no_reminders"), parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
                ]])
            )
        return

    # ── Change language ──
    if data.startswith("changelang_"):
        code = data[11:]
        lang_name = LANGUAGES.get(code, code)
        db.set_user_language(user.id, code)
        try:
            await query.edit_message_text(t(code, "lang_set", language=lang_name), parse_mode="HTML")
        except Exception:
            pass
        await send_main_menu(context, user.id, code)
        return


# ── Match list display ────────────────────────────────────────────────────────

async def show_match_list(query, category, lang):
    if category == "live":
        matches  = db.get_live_matches()
        empty_key = "no_live"
        title_en = "🔴 <b>Live Matches</b>"
        title_hi = "🔴 <b>लाइव मैच</b>"
    elif category == "ipl":
        matches  = db.get_ipl_matches()
        empty_key = "no_ipl"
        title_en = "🏆 <b>IPL 2025</b>"
        title_hi = "🏆 <b>IPL 2025</b>"
    elif category == "other":
        matches  = db.get_other_matches()
        empty_key = "no_other"
        title_en = "🌍 <b>Other Cricket</b>"
        title_hi = "🌍 <b>अन्य क्रिकेट</b>"
    else:  # schedule
        matches  = db.get_upcoming_matches()
        empty_key = "no_schedule"
        title_en = "📅 <b>Upcoming Matches</b>"
        title_hi = "📅 <b>आगामी मैच</b>"

    title = title_hi if lang == "hi" else title_en

    if not matches:
        await query.edit_message_text(
            t(lang, empty_key), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
            ]])
        )
        return

    await query.edit_message_text(
        f"{title}\n\n{'देखने के लिए मैच चुनें 👇' if lang=='hi' else 'Select a match to watch 👇'}",
        parse_mode="HTML",
        reply_markup=match_list_keyboard(matches, category, lang)
    )


# ── Match detail card ─────────────────────────────────────────────────────────

async def show_match_detail(query, api_id, category, lang):
    m = db.get_match(api_id)
    if not m:
        await query.edit_message_text("❌ Match not found. Try refreshing.")
        return

    status_emoji = STATUS_EMOJI.get(m["status"], "📅")
    score_line   = t(lang, "score_line", score=m["score"]) if m.get("score") else ""

    text = (
        f"🏏 <b>{m['title']}</b>\n"
        f"🏟 {m.get('venue') or 'TBA'}\n"
        f"🕐 {m.get('start_display') or 'TBA'}\n"
        f"📊 {status_emoji} <b>{m['status'].upper()}</b>\n"
        f"{score_line}"
        f"\n🌐 <b>{'कमेंट्री भाषा चुनें:' if lang=='hi' else 'Choose commentary language:'}</b>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=match_detail_keyboard(api_id, category, lang)
    )


# ── Stream delivery ───────────────────────────────────────────────────────────

async def deliver_stream(query, context, api_id, lang_code, user_lang, user_id):
    m = db.get_match(api_id)
    if not m:
        await query.answer("Match not found.", show_alert=True)
        return

    url       = db.get_stream_link(api_id, lang_code)
    lang_name = LANGUAGES.get(lang_code, lang_code.upper())
    category  = "ipl" if m["is_ipl"] else "live"

    db.log_click(user_id, api_id, lang_code)

    if url:
        text = t(user_lang, "stream_ready", title=m["title"], language=lang_name)
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=stream_keyboard(url, api_id, lang_code, category, user_lang)
        )
    else:
        text = t(user_lang, "link_coming", minutes=str(LINK_COMING_MINUTES))
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=no_link_keyboard(api_id, lang_code, category, user_lang)
        )


# ── Reply keyboard message handler ───────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    u    = db.get_user(user.id)
    lang = u["language"] if u else "en"
    text = update.message.text or ""

    # Membership guard
    ok, missing = await check_membership(context.bot, user.id)
    if not ok:
        ch_name = missing["name"] if missing else "our channel"
        await update.message.reply_text(
            f"⚠️ You must stay in <b>{ch_name}</b> to use this bot!\nPlease rejoin.",
            parse_mode="HTML", reply_markup=welcome_keyboard(lang)
        )
        return

    btn = lambda key: t(lang, key)

    if text == btn("btn_live"):
        live = db.get_live_matches()
        if not live:
            await update.message.reply_text(t(lang, "no_live"), parse_mode="HTML")
        else:
            title = "🔴 <b>लाइव मैच</b>" if lang == "hi" else "🔴 <b>Live Matches</b>"
            await update.message.reply_text(
                f"{title}\n\n{'देखने के लिए चुनें 👇' if lang=='hi' else 'Tap a match to watch 👇'}",
                parse_mode="HTML",
                reply_markup=match_list_keyboard(live, "live", lang)
            )

    elif text == btn("btn_ipl"):
        ipl = db.get_ipl_matches()
        if not ipl:
            await update.message.reply_text(t(lang, "no_ipl"), parse_mode="HTML")
        else:
            await update.message.reply_text(
                "🏆 <b>IPL 2025</b>",
                parse_mode="HTML",
                reply_markup=match_list_keyboard(ipl, "ipl", lang)
            )

    elif text == btn("btn_other"):
        other = db.get_other_matches()
        if not other:
            await update.message.reply_text(t(lang, "no_other"), parse_mode="HTML")
        else:
            title = "🌍 <b>अन्य क्रिकेट</b>" if lang == "hi" else "🌍 <b>Other Cricket</b>"
            await update.message.reply_text(
                title, parse_mode="HTML",
                reply_markup=match_list_keyboard(other, "other", lang)
            )

    elif text == btn("btn_schedule"):
        upcoming = db.get_upcoming_matches()
        if not upcoming:
            await update.message.reply_text(t(lang, "no_schedule"), parse_mode="HTML")
        else:
            title = "📅 <b>आगामी मैच</b>" if lang == "hi" else "📅 <b>Upcoming Matches</b>"
            await update.message.reply_text(
                title, parse_mode="HTML",
                reply_markup=match_list_keyboard(upcoming, "schedule", lang)
            )

    elif text == btn("btn_reminder"):
        reminders = db.get_user_reminders(user.id)
        if not reminders:
            await update.message.reply_text(
                t(lang, "no_reminders"), parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
                ]])
            )
        else:
            txt = t(lang, "reminder_list_hd")
            for r in reminders:
                txt += t(lang, "reminder_item", title=r["title"], remind_at=r.get("start_display",""))
            await update.message.reply_text(
                txt, parse_mode="HTML",
                reply_markup=reminders_keyboard(reminders, lang)
            )

    elif text == btn("btn_language"):
        await update.message.reply_text(
            t(lang, "choose_lang"), parse_mode="HTML",
            reply_markup=change_language_keyboard()
        )

    elif text == btn("btn_help"):
        await update.message.reply_text(t(lang, "help_text"), parse_mode="HTML")

    else:
        await send_main_menu(context, user.id, lang)
