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


async def check_membership(bot, user_id):
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(f"@{ch['username']}", user_id)
            if member.status in ("left", "kicked", "banned"):
                return False, ch
        except Exception:
            return False, ch
    return True, None


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    u    = db.get_user(user.id)

    # First-time user → ask language
    if not u or not u.get("language"):
        await update.message.reply_text(
            "🌐 <b>Choose your language / भाषा चुनें:</b>",
            parse_mode="HTML",
            reply_markup=first_language_keyboard()
        )
        return

    lang = u["language"]
    await send_welcome_gate(context, user.id, lang)


async def send_welcome_gate(context, user_id, lang):
    text = f"<b>{BOT_NAME}</b>\n\n{t(lang, 'welcome_body')}"
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


async def send_main_menu(context, user_id, lang):
    live      = db.get_live_matches()
    live_info = t(lang, "live_info_yes", count=len(live)) if live else t(lang, "live_info_no")
    u         = db.get_user(user_id)
    name      = (u["first_name"] if u else None) or "Cricket Fan"
    text      = t(lang, "main_menu", name=name, live_info=live_info)
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


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    user  = query.from_user
    db.upsert_user(user.id, user.username, user.first_name)
    u     = db.get_user(user.id)
    lang  = (u["language"] if u else None) or "en"

    # First-time language selection
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
        await send_welcome_gate(context, user.id, code)
        return

    # Verify channel join
    if data == "verify_join":
        ok, missing = await check_membership(context.bot, user.id)
        if ok:
            _safe_edit(query, t(lang, "joined_ok"))
            await send_main_menu(context, user.id, lang)
        else:
            ch_name = missing["name"] if missing else "our channel"
            msg = t(lang, "not_joined") + f"\n\n👉 Still need to join: <b>{ch_name}</b>"
            _safe_edit(query, msg, reply_markup=welcome_keyboard(lang))
        return

    # All further actions require membership
    ok, missing = await check_membership(context.bot, user.id)
    if not ok:
        ch_name = missing["name"] if missing else "our channel"
        await query.answer(f"⚠️ Please join {ch_name} first!", show_alert=True)
        return

    if data == "back_main":
        await send_main_menu(context, user.id, lang)
        return

    if data.startswith("list_"):
        await show_match_list(query, data[5:], lang)
        return

    if data.startswith("match_"):
        # format: match_{api_id}_{category}
        # api_id may have dashes/underscores — split from right
        rest     = data[6:]  # strip "match_"
        parts    = rest.rsplit("_", 1)
        api_id   = parts[0]
        category = parts[1] if len(parts) > 1 else "live"
        await show_match_detail(query, api_id, category, lang)
        return

    if data.startswith("stream_"):
        # format: stream_{api_id}_{lang_code}  (lang_code is always 2 chars)
        rest      = data[7:]
        lang_code = rest[-2:]
        api_id    = rest[:-3]  # strip _xx
        await deliver_stream(query, context, api_id, lang_code, lang, user.id)
        return

    if data.startswith("remind_"):
        api_id = data[7:]
        m = db.get_match(api_id)
        if not m:
            await query.answer("Match not found.", show_alert=True)
            return
        try:
            start     = datetime.fromisoformat(m["start_time"].replace("Z", "+00:00"))
            remind_at = (start - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            added     = db.add_reminder(user.id, api_id, remind_at)
            await query.answer(
                t(lang, "reminder_set") if added else t(lang, "reminder_exists"),
                show_alert=True
            )
        except Exception:
            await query.answer("Could not set reminder.", show_alert=True)
        return

    if data.startswith("cancelremind_"):
        api_id = data[13:]
        db.delete_reminder(user.id, api_id)
        await query.answer(t(lang, "reminder_cancelled"), show_alert=True)
        reminders = db.get_user_reminders(user.id)
        if reminders:
            txt = t(lang, "reminder_list_hd")
            for r in reminders:
                txt += t(lang, "reminder_item", title=r["title"], remind_at=r.get("start_display",""))
            _safe_edit(query, txt, reply_markup=reminders_keyboard(reminders, lang))
        else:
            _safe_edit(query, t(lang, "no_reminders"),
                       reply_markup=InlineKeyboardMarkup([[
                           InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
                       ]]))
        return

    if data.startswith("changelang_"):
        code      = data[11:]
        lang_name = LANGUAGES.get(code, code)
        db.set_user_language(user.id, code)
        _safe_edit(query, t(code, "lang_set", language=lang_name))
        await send_main_menu(context, user.id, code)
        return


def _safe_edit(query, text, reply_markup=None):
    """Edit message caption if photo, else edit text."""
    import asyncio
    async def _do():
        try:
            await query.edit_message_caption(
                caption=text, parse_mode="HTML", reply_markup=reply_markup
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text, parse_mode="HTML", reply_markup=reply_markup
                )
            except Exception:
                pass
    return _do()


async def show_match_list(query, category, lang):
    if category == "live":
        matches   = db.get_live_matches()
        empty_key = "no_live"
        title     = "🔴 <b>लाइव मैच</b>" if lang=="hi" else "🔴 <b>Live Matches</b>"
    elif category == "ipl":
        matches   = db.get_ipl_matches()
        empty_key = "no_ipl"
        title     = "🏆 <b>IPL 2025</b>"
    elif category == "other":
        matches   = db.get_other_matches()
        empty_key = "no_other"
        title     = "🌍 <b>अन्य क्रिकेट</b>" if lang=="hi" else "🌍 <b>Other Cricket</b>"
    else:
        matches   = db.get_upcoming_matches()
        empty_key = "no_schedule"
        title     = "📅 <b>आगामी मैच</b>" if lang=="hi" else "📅 <b>Upcoming Matches</b>"

    if not matches:
        await query.edit_message_text(
            t(lang, empty_key), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
            ]])
        )
        return

    sub = "देखने के लिए मैच चुनें 👇" if lang=="hi" else "Tap a match to watch 👇"
    await query.edit_message_text(
        f"{title}\n<i>{sub}</i>",
        parse_mode="HTML",
        reply_markup=match_list_keyboard(matches, category, lang)
    )


async def show_match_detail(query, api_id, category, lang):
    m = db.get_match(api_id)
    if not m:
        await query.edit_message_text("❌ Match not found.")
        return

    status_emoji = STATUS_EMOJI.get(m["status"], "📅")
    has_links    = bool(db.get_all_links_for_match(api_id))

    # Status badge
    status_map = {
        "live":     "🔴 LIVE",
        "upcoming": "📅 UPCOMING",
        "ended":    "✅ MATCH ENDED",
    }
    status_text = status_map.get(m["status"], m["status"].upper())

    # Score block
    score_block = ""
    if m.get("score"):
        score_block = f"\n📊 <b>Score</b>\n<code>{m['score']}</code>\n"

    # Link availability hint
    if has_links:
        link_hint = "✅ <i>Stream links available — choose language below</i>"
    elif m["status"] == "upcoming":
        link_hint = "⏳ <i>Stream link will be added before match starts</i>"
    else:
        link_hint = "⏳ <i>Stream link not available yet — tap Refresh</i>"

    text = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏏 <b>{m['title']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏟  {m.get('venue') or 'TBA'}\n"
        f"🕐  {m.get('start_display') or 'TBA'}\n"
        f"📌  {status_text}\n"
        f"{score_block}"
        f"\n{link_hint}\n"
        f"\n🌐 <b>{'कमेंट्री भाषा चुनें:' if lang=='hi' else 'Choose commentary language:'}</b>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=match_detail_keyboard(api_id, category, lang)
    )


async def deliver_stream(query, context, api_id, lang_code, user_lang, user_id):
    m = db.get_match(api_id)
    if not m:
        await query.answer("Match not found.", show_alert=True)
        return

    url       = db.get_stream_link(api_id, lang_code)
    lang_name = LANGUAGES.get(lang_code, lang_code.upper())
    category  = "ipl" if m["is_ipl"] else "other"
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


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    u    = db.get_user(user.id)
    lang = (u["language"] if u else None) or "en"
    text = update.message.text or ""

    ok, missing = await check_membership(context.bot, user.id)
    if not ok:
        ch_name = missing["name"] if missing else "our channel"
        await update.message.reply_text(
            f"⚠️ You must stay in <b>{ch_name}</b> to use this bot!\nPlease rejoin.",
            parse_mode="HTML", reply_markup=welcome_keyboard(lang)
        )
        return

    btn = lambda key: t(lang, key)

    async def send_list(matches, empty_key, title_en, title_hi, category):
        if not matches:
            await update.message.reply_text(t(lang, empty_key), parse_mode="HTML")
            return
        title = title_hi if lang=="hi" else title_en
        sub   = "देखने के लिए चुनें 👇" if lang=="hi" else "Tap a match to watch 👇"
        await update.message.reply_text(
            f"{title}\n<i>{sub}</i>",
            parse_mode="HTML",
            reply_markup=match_list_keyboard(matches, category, lang)
        )

    if text == btn("btn_live"):
        await send_list(db.get_live_matches(), "no_live",
                        "🔴 <b>Live Matches</b>", "🔴 <b>लाइव मैच</b>", "live")

    elif text == btn("btn_ipl"):
        await send_list(db.get_ipl_matches(), "no_ipl",
                        "🏆 <b>IPL 2025</b>", "🏆 <b>IPL 2025</b>", "ipl")

    elif text == btn("btn_other"):
        await send_list(db.get_other_matches(), "no_other",
                        "🌍 <b>Other Cricket</b>", "🌍 <b>अन्य क्रिकेट</b>", "other")

    elif text == btn("btn_schedule"):
        await send_list(db.get_upcoming_matches(), "no_schedule",
                        "📅 <b>Upcoming Matches</b>", "📅 <b>आगामी मैच</b>", "schedule")

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
