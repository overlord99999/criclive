from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from config import REQUIRED_CHANNELS, LANGUAGES
from strings import t


def welcome_keyboard(lang="en"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "join_btn1"), url=REQUIRED_CHANNELS[0]["url"]),
            InlineKeyboardButton(t(lang, "join_btn2"), url=REQUIRED_CHANNELS[1]["url"]),
        ],
        [InlineKeyboardButton(t(lang, "verify_btn"), callback_data="verify_join")],
    ])


def first_language_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English",       callback_data="setlang_en"),
        InlineKeyboardButton("🇮🇳 Hindi / हिंदी", callback_data="setlang_hi"),
    ]])


def main_menu_keyboard(lang="en"):
    return ReplyKeyboardMarkup(
        [
            [t(lang, "btn_live"),     t(lang, "btn_ipl")],
            [t(lang, "btn_other"),    t(lang, "btn_schedule")],
            [t(lang, "btn_reminder"), t(lang, "btn_language")],
            [t(lang, "btn_help")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Choose an option...",
    )


def match_list_keyboard(matches, category, lang="en"):
    buttons = []
    for m in matches:
        if m["status"] == "live":
            emoji = "🔴"
        elif m["status"] == "upcoming":
            emoji = "📅"
        else:
            emoji = "✅"
        # Use api_id with category — split on last underscore in callback handler
        label = f"{emoji}  {m['title'][:36]}"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"match_{m['api_id']}_{category}"
        )])
    buttons.append([InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def match_detail_keyboard(api_id, category, lang="en"):
    hi = lang == "hi"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇮🇳 Hindi",   callback_data=f"stream_{api_id}_hi"),
            InlineKeyboardButton("🇬🇧 English", callback_data=f"stream_{api_id}_en"),
        ],
        [
            InlineKeyboardButton("Tamil",       callback_data=f"stream_{api_id}_ta"),
            InlineKeyboardButton("Telugu",      callback_data=f"stream_{api_id}_te"),
        ],
        [
            InlineKeyboardButton("Bengali",     callback_data=f"stream_{api_id}_bn"),
            InlineKeyboardButton("Kannada",     callback_data=f"stream_{api_id}_kn"),
            InlineKeyboardButton("Marathi",     callback_data=f"stream_{api_id}_mr"),
        ],
        [
            InlineKeyboardButton(
                "🔔 " + ("रिमाइंडर" if hi else "Set Reminder"),
                callback_data=f"remind_{api_id}"
            ),
            InlineKeyboardButton(
                "🔄 " + ("रिफ्रेश" if hi else "Refresh"),
                callback_data=f"match_{api_id}_{category}"
            ),
        ],
        [InlineKeyboardButton(t(lang, "back_btn"), callback_data=f"list_{category}")],
    ])


def stream_keyboard(url, api_id, lang_code, category, user_lang="en"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_lang, "stream_url_btn"), url=url)],
        [
            InlineKeyboardButton(
                t(user_lang, "refresh_btn"),
                callback_data=f"stream_{api_id}_{lang_code}"
            ),
            InlineKeyboardButton(
                t(user_lang, "back_btn"),
                callback_data=f"match_{api_id}_{category}"
            ),
        ],
    ])


def no_link_keyboard(api_id, lang_code, category, user_lang="en"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            t(user_lang, "refresh_btn"),
            callback_data=f"stream_{api_id}_{lang_code}"
        )],
        [InlineKeyboardButton(
            t(user_lang, "back_btn"),
            callback_data=f"match_{api_id}_{category}"
        )],
    ])


def reminders_keyboard(reminders, lang="en"):
    buttons = [[InlineKeyboardButton(
        f"❌  {r['title'][:30]}",
        callback_data=f"cancelremind_{r['api_id']}"
    )] for r in reminders]
    buttons.append([InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def change_language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English",  callback_data="changelang_en"),
            InlineKeyboardButton("🇮🇳 Hindi",    callback_data="changelang_hi"),
        ],
        [
            InlineKeyboardButton("Tamil",        callback_data="changelang_ta"),
            InlineKeyboardButton("Telugu",       callback_data="changelang_te"),
        ],
        [
            InlineKeyboardButton("Bengali",      callback_data="changelang_bn"),
            InlineKeyboardButton("Kannada",      callback_data="changelang_kn"),
        ],
        [InlineKeyboardButton("Marathi",         callback_data="changelang_mr")],
    ])


# ── Admin keyboards ───────────────────────────────────────────────────────────

def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 View All Matches",  callback_data="admin_listmatches")],
        [
            InlineKeyboardButton("🔗 Add Stream Link", callback_data="admin_addlink"),
            InlineKeyboardButton("📊 Stats",           callback_data="admin_stats"),
        ],
        [InlineKeyboardButton("📢 Broadcast",          callback_data="admin_broadcast")],
    ])


def admin_match_links_keyboard(matches):
    buttons = []
    for m in matches:
        emoji  = "🔴" if m["status"]=="live" else "📅"
        ipl    = "🏆" if m["is_ipl"] else "  "
        links  = db_link_count(m["api_id"])
        linked = f" ✅" if links else ""
        buttons.append([InlineKeyboardButton(
            f"{emoji}{ipl} {m['title'][:33]}{linked}",
            callback_data=f"admin_pickmatch_{m['api_id']}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_addlink")])
    return InlineKeyboardMarkup(buttons)


def admin_pick_language_keyboard(api_id, existing_links):
    existing = {l["language"] for l in existing_links}
    lang_list = [
        ("hi","🇮🇳 Hindi"),("en","🇬🇧 English"),
        ("ta","Tamil"),("te","Telugu"),
        ("bn","Bengali"),("kn","Kannada"),("mr","Marathi"),
    ]
    buttons = []
    for code, name in lang_list:
        tick = "✅ " if code in existing else "➕ "
        buttons.append([InlineKeyboardButton(
            f"{tick}{name}", callback_data=f"admin_setlink_{api_id}_{code}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_addlink")])
    return InlineKeyboardMarkup(buttons)


def db_link_count(api_id):
    import database as db
    return len(db.get_all_links_for_match(api_id))
