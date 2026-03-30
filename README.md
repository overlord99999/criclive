# 🏏 CricketLive Bot — Setup & Admin Guide

## Files in this project
```
cricketlive_bot/
├── main.py            ← Run this to start the bot
├── config.py          ← Your settings (token, channels, API key)
├── database.py        ← SQLite database (auto-created)
├── handlers.py        ← User-facing bot logic
├── admin_handlers.py  ← Admin panel logic
├── keyboards.py       ← All keyboard layouts
├── strings.py         ← English + Hindi text
├── cricapi.py         ← Live score fetching
└── requirements.txt   ← Python dependencies
```

---

## Step 1 — Install Python packages
```bash
pip install -r requirements.txt
```

---

## Step 2 — Set your Admin ID in config.py

1. Message @userinfobot on Telegram
2. It will reply with your numeric user ID (e.g. 987654321)
3. Open config.py and replace `123456789` with your real ID:
```python
ADMIN_IDS = [987654321]
```

---

## Step 3 — (Optional) Set your banner images

In config.py, replace the image URLs with your own:
```python
WELCOME_IMG_URL   = "https://your-image-host.com/welcome-banner.jpg"
MAIN_MENU_IMG_URL = "https://your-image-host.com/main-menu-banner.jpg"
```
You can upload images to imgbb.com or imgur.com for free.

---

## Step 4 — Run the bot
```bash
python main.py
```

---

## Admin Commands (send these in Telegram to your bot)

| Command | What it does |
|---------|-------------|
| `/admin` | Open admin panel |

### From the admin panel you can:

**Add a match:**
- Tap ➕ Add Match
- Follow the 6-step flow (title, teams, type, venue, time, IPL yes/no)

**Add stream links:**
- Tap 📋 All Matches
- Tap the match
- Tap 🔗 Add/Edit Links
- Tap the language (Hindi, English, Tamil, etc.)
- Send the stream URL

**Update match status:**
- Tap the match → 🔴 Set Live / 📅 Set Upcoming / ✅ Set Ended

**Broadcast to all users:**
- Tap 📢 Broadcast
- Send any message (text or photo+caption)

**View stats:**
- Tap 📊 Bot Stats

---

## How the stream flow works

1. Admin adds a match (title, time, venue)
2. Admin adds stream URL per language (Hindi, English, Tamil, etc.)
3. When user selects a match and language:
   - If link exists → user gets the link immediately
   - If no link yet → user sees "Link will be added 10 minutes before match"
   - User can tap 🔄 Refresh to check again

---

## How reminders work

- User taps 🔔 Set Reminder on any match
- Bot stores the reminder
- 15 minutes before match start, bot sends notification
- User gets a "Watch Now" button in the notification

---

## Channel membership gate

- On /start, user must join both @MoviesInfoBotx and @darktechsociety
- Every message checks membership
- If user leaves a channel, bot blocks access until they rejoin

---

## Live score updates

- Every 90 seconds, bot fetches live scores from CricAPI
- Scores are shown on match cards automatically
- This uses your CricAPI key from config.py

---

## Adding the bot to a server (to keep it running 24/7)

### On a VPS (Ubuntu):
```bash
# Install screen or use systemd
screen -S cricketbot
python main.py
# Press Ctrl+A then D to detach
```

### With systemd service:
```ini
[Unit]
Description=CricketLive Bot
After=network.target

[Service]
WorkingDirectory=/path/to/cricketlive_bot
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Free hosting options

- **Railway.app** — Free tier, easy deploy
- **Render.com** — Free tier available
- **Oracle Cloud** — Free VPS forever (2 CPUs, 1GB RAM)
- **Google Cloud** — $300 free credits

---

## Troubleshooting

**Bot doesn't respond:**
- Check your BOT_TOKEN in config.py
- Make sure python main.py is running

**Channel check fails:**
- Make sure the bot is an admin in both channels
- Or at least a member so it can check user membership

**CricAPI not working:**
- Check your API key in config.py
- Free tier has limited requests — scores update every 90s to save quota

**Images not showing:**
- Replace WELCOME_IMG_URL with a direct image link (must end in .jpg/.png)
- Or use Telegram file_id by sending the image to the bot first
