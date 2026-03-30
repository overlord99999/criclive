# ─── CricketLive Bot — Configuration ───────────────────────────────────────
BOT_TOKEN = "7978157216:AAHCCtfirrhYQa2wNcA6bs-dJ9nwCezLiR4"
CRICAPI_KEY = "9018af37-db87-42aa-8d1a-730fb7977a41"

# Your 2 required channels (without @)
REQUIRED_CHANNELS = [
    {"username": "MoviesInfoBotx",    "name": "Movies Info",        "url": "https://t.me/MoviesInfoBotx"},
    {"username": "darktechsociety",   "name": "DarkTech Society",   "url": "https://t.me/darktechsociety"},
]

# Admin Telegram user IDs — add your Telegram numeric ID here
# Get yours by messaging @userinfobot on Telegram
ADMIN_IDS = [-1002572963956]  # REPLACE with your actual Telegram user ID

# Bot branding
BOT_NAME        = "CricketLive Bot"
BOT_TAGLINE_EN  = "Watch IPL & All Live Cricket — Free, Fast & Multi-Language!"
BOT_TAGLINE_HI  = "IPL और सभी लाइव क्रिकेट देखें — मुफ़्त, तेज़ और बहुभाषी!"

WELCOME_IMG_URL = "https://t.me/photouploadhere/18"   # Replace with your banner image URL
MAIN_MENU_IMG_URL = "https://t.me/photouploadhere/18" # Replace with your main menu banner URL

# CricAPI base
CRICAPI_BASE = "https://api.cricapi.com/v1"

# Languages supported
LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "kn": "Kannada",
    "mr": "Marathi",
}

# How many minutes before match to show "link coming soon" message
LINK_COMING_MINUTES = 10

# DB file
DB_FILE = "cricketlive.db"
