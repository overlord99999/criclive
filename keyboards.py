from telegram import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import REQUIRED_CHANNELS, LANGUAGES
from strings import t


# ─── Welcome gate keyboard ───────────────────────────────────────────────────

def welcome_keyboard(lang="en"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "join_btn1"), url=REQUIRED_CHANNELS[0]["url"]),
            InlineKeyboardButton(t(lang, "join_btn2"), url=REQUIRED_CHANNELS[1]["url"]),
        ],
        [InlineKeyboardButton(t(lang, "verify_btn"), callback_data="verify_join")],
    ])


# ─── Language selection (first time) ────────────────────────────────────────

def first_language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"),
            InlineKeyboardButton("🇮🇳 Hindi / हिंदी", callback_data="setlang_hi"),
        ]
    ])


# ─── Main menu reply keyboard ────────────────────────────────────────────────

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


# ─── Match list inline keyboard ──────────────────────────────────────────────

def match_list_keyboard(matches, category, lang="en"):
    buttons = []
    for m in matches:
        status_emoji = "🔴" if m["status"] == "live" else "📅" if m["status"] == "upcoming" else "✅"
        label = f"{status_emoji} {m['title']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"match_{m['id']}_{category}")])
    buttons.append([InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# ─── Match detail + language selector keyboard ───────────────────────────────

def match_detail_keyboard(match_id, category, lang="en"):
    lang_buttons = []
    row = []
    lang_list = [
        ("hi", "🇮🇳 Hindi"),
        ("en", "🇬🇧 English"),
        ("ta", "🏴 Tamil"),
        ("te", "🏴 Telugu"),
        ("bn", "🏴 Bengali"),
        ("kn", "🏴 Kannada"),
        ("mr", "🏴 Marathi"),
    ]
    for i, (code, label) in enumerate(lang_list):
        row.append(InlineKeyboardButton(label, callback_data=f"stream_{match_id}_{code}"))
        if len(row) == 2:
            lang_buttons.append(row)
            row = []
    if row:
        lang_buttons.append(row)

    # Bottom action buttons
    lang_buttons.append([
        InlineKeyboardButton("🔔 Set Reminder" if lang == "en" else "🔔 रिमाइंडर",
                             callback_data=f"remind_{match_id}"),
        InlineKeyboardButton("🔄 Refresh" if lang == "en" else "🔄 रिफ्रेश",
                             callback_data=f"match_{match_id}_{category}"),
    ])
    lang_buttons.append([
        InlineKeyboardButton(t(lang, "back_btn"), callback_data=f"list_{category}"),
    ])
    return InlineKeyboardMarkup(lang_buttons)


# ─── Stream delivered keyboard ───────────────────────────────────────────────

def stream_keyboard(stream_url, match_id, lang_code, category, user_lang="en"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_lang, "stream_url_btn"), url=stream_url)],
        [
            InlineKeyboardButton(t(user_lang, "refresh_btn"),
                                 callback_data=f"stream_{match_id}_{lang_code}"),
            InlineKeyboardButton(t(user_lang, "back_btn"),
                                 callback_data=f"match_{match_id}_{category}"),
        ],
    ])


# ─── No link yet keyboard ────────────────────────────────────────────────────

def no_link_keyboard(match_id, lang_code, category, user_lang="en"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_lang, "refresh_btn"),
                              callback_data=f"stream_{match_id}_{lang_code}")],
        [InlineKeyboardButton(t(user_lang, "back_btn"),
                              callback_data=f"match_{match_id}_{category}")],
    ])


# ─── Reminder list keyboard ──────────────────────────────────────────────────

def reminders_keyboard(reminders, lang="en"):
    buttons = []
    for r in reminders:
        buttons.append([
            InlineKeyboardButton(
                f"❌ {r['title'][:25]}",
                callback_data=f"cancelremind_{r['match_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(t(lang, "back_btn"), callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# ─── Change language keyboard ────────────────────────────────────────────────

def change_language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English",       callback_data="changelang_en"),
            InlineKeyboardButton("🇮🇳 Hindi",          callback_data="changelang_hi"),
        ],
        [
            InlineKeyboardButton("🏴 Tamil",           callback_data="changelang_ta"),
            InlineKeyboardButton("🏴 Telugu",          callback_data="changelang_te"),
        ],
        [
            InlineKeyboardButton("🏴 Bengali",         callback_data="changelang_bn"),
            InlineKeyboardButton("🏴 Kannada",         callback_data="changelang_kn"),
        ],
        [InlineKeyboardButton("🏴 Marathi",            callback_data="changelang_mr")],
    ])


# ─── Admin keyboards ─────────────────────────────────────────────────────────

def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Match",        callback_data="admin_addmatch"),
            InlineKeyboardButton("📋 All Matches",      callback_data="admin_listmatches"),
        ],
        [
            InlineKeyboardButton("🔗 Add Stream Link",  callback_data="admin_addlink"),
            InlineKeyboardButton("📊 Bot Stats",        callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast",        callback_data="admin_broadcast"),
        ],
    ])


def admin_match_actions_keyboard(match_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Add/Edit Links",   callback_data=f"admin_links_{match_id}"),
            InlineKeyboardButton("✏️ Edit Match",       callback_data=f"admin_edit_{match_id}"),
        ],
        [
            InlineKeyboardButton("🔴 Set Live",         callback_data=f"admin_status_live_{match_id}"),
            InlineKeyboardButton("📅 Set Upcoming",     callback_data=f"admin_status_upcoming_{match_id}"),
            InlineKeyboardButton("✅ Set Ended",        callback_data=f"admin_status_ended_{match_id}"),
        ],
        [
            InlineKeyboardButton("🗑️ Delete Match",     callback_data=f"admin_delete_{match_id}"),
            InlineKeyboardButton("⬅️ Back",             callback_data="admin_listmatches"),
        ],
    ])


def admin_links_keyboard(match_id, existing_links):
    existing = {l["language"]: l["url"] for l in existing_links}
    buttons = []
    lang_list = [
        ("hi", "Hindi"), ("en", "English"), ("ta", "Tamil"),
        ("te", "Telugu"), ("bn", "Bengali"), ("kn", "Kannada"), ("mr", "Marathi"),
    ]
    for code, name in lang_list:
        has = "✅" if code in existing else "➕"
        buttons.append([InlineKeyboardButton(
            f"{has} {name}", callback_data=f"admin_setlink_{match_id}_{code}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_match_{match_id}")])
    return InlineKeyboardMarkup(buttons)
