from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timedelta

import database as db
from config import REQUIRED_CHANNELS, MAIN_MENU_IMG_URL, WELCOME_IMG_URL, LINK_COMING_MINUTES, BOT_NAME
from strings import t, STATUS_EMOJI
from keyboards import (
    welcome_keyboard, first_language_keyboard, main_menu_keyboard,
    match_list_keyboard, match_detail_keyboard, stream_keyboard,
    no_link_keyboard, reminders_keyboard, change_language_keyboard,
)


# ─── Check channel membership ────────────────────────────────────────────────

async def check_membership(bot, user_id):
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(f"@{ch['username']}", user_id)
            if member.status in ("left", "kicked", "banned"):
                return False, ch
        except Exception:
            return False, ch
    return True, None


# ─── /start ──────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    u = db.get_user(user.id)
    lang = u["language"] if u else "en"

    # If user hasn't set language yet, ask
    if not u or u["language"] == "en":
        await update.message.reply_text(
            "🌐 <b>Choose your language / भाषा चुनें:</b>",
            parse_mode="HTML",
            reply_markup=first_language_keyboard()
        )
        return

    # Send welcome gate
    await send_welcome_gate(update.message, lang)


async def send_welcome_gate(message_obj, lang):
    text = (
        f"<b>{BOT_NAME}</b>\n\n"
        f"{t(lang, 'welcome_body')}"
    )
    try:
        await message_obj.reply_photo(
            photo=WELCOME_IMG_URL,
            caption=text,
            parse_mode="HTML",
            reply_markup=welcome_keyboard(lang)
        )
    except Exception:
        await message_obj.reply_text(
            text, parse_mode="HTML", reply_markup=welcome_keyboard(lang)
        )


# ─── Send main menu ──────────────────────────────────────────────────────────

async def send_main_menu(target, context, user_id, lang, edit=False):
    live = db.get_live_matches()
    live_info = t(lang, "live_info_yes", count=len(live)) if live else t(lang, "live_info_no")
    u = db.get_user(user_id)
    name = u["first_name"] if u else "Cricket Fan"
    text = t(lang, "main_menu", name=name, live_info=live_info)

    try:
        if edit and hasattr(target, "edit_message_caption"):
            await target.edit_message_caption(caption=text, parse_mode="HTML")
        else:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=MAIN_MENU_IMG_URL,
                caption=text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(lang)
            )
    except Exception:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(lang)
            )
        except Exception as e:
            print(f"[send_main_menu] error: {e}")


# ─── Callback query handler ──────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    db.upsert_user(user.id, user.username, user.first_name)
    u = db.get_user(user.id)
    lang = u["language"] if u else "en"

    # ── First time language selection ──
    if data.startswith("setlang_"):
        code = data.split("_")[1]
        db.set_user_language(user.id, code)
        await query.edit_message_text(
            f"✅ Language set!\n\nWelcome to <b>{BOT_NAME}</b>!",
            parse_mode="HTML"
        )
        # Now show welcome gate
        await send_welcome_gate(query.message, code)
        return

    # ── Verify channel membership ──
    if data == "verify_join":
        ok, missing_ch = await check_membership(context.bot, user.id)
        if ok:
            await query.edit_message_caption(
                caption=t(lang, "joined_ok"), parse_mode="HTML"
            ) if query.message.caption else await query.edit_message_text(
                t(lang, "joined_ok"), parse_mode="HTML"
            )
            await send_main_menu(query, context, user.id, lang)
        else:
            ch_name = missing_ch["name"] if missing_ch else "the channel"
            text = t(lang, "not_joined") + f"\n\n👉 Still need to join: <b>{ch_name}</b>"
            try:
                await query.edit_message_caption(
                    caption=text, parse_mode="HTML",
                    reply_markup=welcome_keyboard(lang)
                )
            except Exception:
                await query.edit_message_text(
                    text, parse_mode="HTML", reply_markup=welcome_keyboard(lang)
                )
        return

    # ── All subsequent actions require channel membership ──
    ok, missing_ch = await check_membership(context.bot, user.id)
    if not ok:
        ch_name = missing_ch["name"] if missing_ch else "our channel"
        await query.answer(
            f"⚠️ Please join {ch_name} to continue!", show_alert=True
        )
        return

    # ── Back to main ──
    if data == "back_main":
        await send_main_menu(query, context, user.id, lang)
        return

    # ── Match list by category ──
    if data.startswith("list_"):
        category = data.split("_", 1)[1]
        await show_match_list(query, category, lang)
        return

    # ── Match detail ──
    if data.startswith("match_"):
        parts = data.split("_")
        match_id = int(parts[1])
        category = parts[2] if len(parts) > 2 else "live"
        await show_match_detail(query, match_id, category, lang)
        return

    # ── Stream link request ──
    if data.startswith("stream_"):
        parts = data.split("_")
        match_id = int(parts[1])
        lang_code = parts[2]
        await deliver_stream(query, context, match_id, lang_code, lang, user.id)
        return

    # ── Set reminder ──
    if data.startswith("remind_"):
        match_id = int(data.split("_")[1])
        m = db.get_match(match_id)
        if not m:
            await query.answer("Match not found.", show_alert=True)
            return
        try:
            start = datetime.strptime(m["start_time"], "%Y-%m-%d %H:%M")
            remind_at = start - timedelta(minutes=15)
            added = db.add_reminder(user.id, match_id, remind_at.strftime("%Y-%m-%d %H:%M:%S"))
            if added:
                await query.answer(t(lang, "reminder_set"), show_alert=True)
            else:
                await query.answer(t(lang, "reminder_exists"), show_alert=True)
        except Exception:
            await query.answer("Could not set reminder — invalid match time.", show_alert=True)
        return

    # ── Cancel reminder ──
    if data.startswith("cancelremind_"):
        match_id = int(data.split("_")[1])
        db.delete_reminder(user.id, match_id)
        await query.answer(t(lang, "reminder_cancelled"), show_alert=True)
        reminders = db.get_user_reminders(user.id)
        if reminders:
            text = t(lang, "reminder_list_hd")
            for r in reminders:
                text += t(lang, "reminder_item", title=r["title"], remind_at=r["remind_at"])
            await query.edit_message_text(
                text, parse_mode="HTML",
                reply_markup=reminders_keyboard(reminders, lang)
            )
        else:
            await query.edit_message_text(t(lang, "no_reminders"), parse_mode="HTML",
                                          reply_markup=InlineKeyboardMarkup([[
                                              InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
                                          ]]))
        return

    # ── Change language ──
    if data.startswith("changelang_"):
        code = data.split("_")[1]
        from config import LANGUAGES
        lang_name = LANGUAGES.get(code, code)
        db.set_user_language(user.id, code)
        await query.edit_message_text(
            t(code, "lang_set", language=lang_name), parse_mode="HTML"
        )
        await send_main_menu(query, context, user.id, code)
        return


# ─── Show match list ─────────────────────────────────────────────────────────

async def show_match_list(query, category, lang):
    if category == "live":
        matches = db.get_live_matches()
        empty_key = "no_live"
        title = "🔴 <b>Live Matches</b>" if lang == "en" else "🔴 <b>लाइव मैच</b>"
    elif category == "ipl":
        matches = db.get_ipl_matches()
        empty_key = "no_ipl"
        title = "🏆 <b>IPL 2025</b>"
    elif category == "other":
        all_m = db.get_all_matches()
        matches = [m for m in all_m if not m["is_ipl"]]
        empty_key = "no_other"
        title = "🌍 <b>Other Cricket</b>" if lang == "en" else "🌍 <b>अन्य क्रिकेट</b>"
    elif category == "schedule":
        matches = db.get_upcoming_matches()
        empty_key = "no_schedule"
        title = "📅 <b>Schedule</b>" if lang == "en" else "📅 <b>शेड्यूल</b>"
    else:
        matches = []
        empty_key = "no_live"
        title = "Matches"

    if not matches:
        await query.edit_message_text(
            t(lang, empty_key), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")
            ]])
        )
        return

    await query.edit_message_text(
        f"{title}\n\n<i>Tap a match to watch:</i>",
        parse_mode="HTML",
        reply_markup=match_list_keyboard(matches, category, lang)
    )


# ─── Show match detail card ──────────────────────────────────────────────────

async def show_match_detail(query, match_id, category, lang):
    m = db.get_match(match_id)
    if not m:
        await query.edit_message_text("❌ Match not found.")
        return

    status_emoji = STATUS_EMOJI.get(m["status"], "📅")
    score_line = t(lang, "score_line", score=m["score"]) if m.get("score") else ""
    text = t(
        lang, "match_card",
        title=m["title"],
        venue=m.get("venue") or "TBA",
        start_time=m.get("start_time") or "TBA",
        status_emoji=status_emoji,
        status=m["status"].upper(),
        score_line=score_line,
    ) + t(lang, "select_language")

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=match_detail_keyboard(match_id, category, lang)
    )


# ─── Deliver stream ──────────────────────────────────────────────────────────

async def deliver_stream(query, context, match_id, lang_code, user_lang, user_id):
    from config import LANGUAGES, LINK_COMING_MINUTES
    m = db.get_match(match_id)
    if not m:
        await query.answer("Match not found.", show_alert=True)
        return

    url = db.get_stream_link(match_id, lang_code)
    lang_name = LANGUAGES.get(lang_code, lang_code.upper())
    category = "ipl" if m["is_ipl"] else "live"

    db.log_click(user_id, match_id, lang_code)

    if url:
        text = t(user_lang, "stream_ready", title=m["title"], language=lang_name)
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=stream_keyboard(url, match_id, lang_code, category, user_lang)
        )
    else:
        # No link yet — check if match time is known
        minutes_msg = str(LINK_COMING_MINUTES)
        try:
            start = datetime.strptime(m["start_time"], "%Y-%m-%d %H:%M")
            diff = (start - datetime.now()).total_seconds() / 60
            if diff > LINK_COMING_MINUTES:
                minutes_msg = str(int(diff - LINK_COMING_MINUTES))
        except Exception:
            pass

        text = t(user_lang, "link_coming", minutes=minutes_msg)
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=no_link_keyboard(match_id, lang_code, category, user_lang)
        )


# ─── Reply keyboard message handler ─────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    u = db.get_user(user.id)
    lang = u["language"] if u else "en"
    text = update.message.text or ""

    # Check membership on every message
    ok, missing_ch = await check_membership(context.bot, user.id)
    if not ok:
        ch_name = missing_ch["name"] if missing_ch else "our channel"
        await update.message.reply_text(
            f"⚠️ You must stay in <b>{ch_name}</b> to use this bot!\n"
            f"Please rejoin and come back.",
            parse_mode="HTML",
            reply_markup=welcome_keyboard(lang)
        )
        return

    btn = lambda key: t(lang, key)

    if text == btn("btn_live"):
        live = db.get_live_matches()
        if not live:
            await update.message.reply_text(t(lang, "no_live"), parse_mode="HTML")
        else:
            await update.message.reply_text(
                "🔴 <b>Live Matches</b>\n\n<i>Tap to watch:</i>" if lang == "en"
                else "🔴 <b>लाइव मैच</b>\n\n<i>देखने के लिए टैप करें:</i>",
                parse_mode="HTML",
                reply_markup=match_list_keyboard(live, "live", lang)
            )

    elif text == btn("btn_ipl"):
        ipl = db.get_ipl_matches()
        if not ipl:
            await update.message.reply_text(t(lang, "no_ipl"), parse_mode="HTML")
        else:
            await update.message.reply_text(
                "🏆 <b>IPL 2025 Matches</b>\n\n<i>Tap to watch:</i>" if lang == "en"
                else "🏆 <b>IPL 2025 मैच</b>\n\n<i>देखने के लिए टैप करें:</i>",
                parse_mode="HTML",
                reply_markup=match_list_keyboard(ipl, "ipl", lang)
            )

    elif text == btn("btn_other"):
        all_m = db.get_all_matches()
        other = [m for m in all_m if not m["is_ipl"]]
        if not other:
            await update.message.reply_text(t(lang, "no_other"), parse_mode="HTML")
        else:
            await update.message.reply_text(
                "🌍 <b>Other Matches</b>\n\n<i>Tap to watch:</i>" if lang == "en"
                else "🌍 <b>अन्य मैच</b>",
                parse_mode="HTML",
                reply_markup=match_list_keyboard(other, "other", lang)
            )

    elif text == btn("btn_schedule"):
        upcoming = db.get_upcoming_matches()
        if not upcoming:
            await update.message.reply_text(t(lang, "no_schedule"), parse_mode="HTML")
        else:
            await update.message.reply_text(
                "📅 <b>Upcoming Matches</b>" if lang == "en" else "📅 <b>आगामी मैच</b>",
                parse_mode="HTML",
                reply_markup=match_list_keyboard(upcoming, "schedule", lang)
            )

    elif text == btn("btn_reminder"):
        reminders = db.get_user_reminders(user.id)
        if not reminders:
            await update.message.reply_text(t(lang, "no_reminders"), parse_mode="HTML",
                                            reply_markup=InlineKeyboardMarkup([[
                                                InlineKeyboardButton(t(lang, "back_btn"),
                                                                     callback_data="back_main")
                                            ]]))
        else:
            txt = t(lang, "reminder_list_hd")
            for r in reminders:
                txt += t(lang, "reminder_item", title=r["title"], remind_at=r["remind_at"])
            await update.message.reply_text(txt, parse_mode="HTML",
                                            reply_markup=reminders_keyboard(reminders, lang))

    elif text == btn("btn_language"):
        await update.message.reply_text(t(lang, "choose_lang"), parse_mode="HTML",
                                        reply_markup=change_language_keyboard())

    elif text == btn("btn_help"):
        await update.message.reply_text(t(lang, "help_text"), parse_mode="HTML")

    else:
        await send_main_menu(update.message, context, user.id, lang)
