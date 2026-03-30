import sqlite3
from config import DB_FILE


def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        username   TEXT,
        first_name TEXT,
        language   TEXT DEFAULT 'en',
        joined_at  TEXT DEFAULT (datetime('now')),
        last_seen  TEXT DEFAULT (datetime('now')),
        is_blocked INTEGER DEFAULT 0
    )""")

    # Matches — synced from CricAPI automatically
    c.execute("""CREATE TABLE IF NOT EXISTS matches (
        api_id      TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        team1       TEXT,
        team2       TEXT,
        match_type  TEXT DEFAULT 'T20',
        venue       TEXT,
        start_time  TEXT,
        start_display TEXT,
        status      TEXT DEFAULT 'upcoming',
        score       TEXT DEFAULT '',
        is_ipl      INTEGER DEFAULT 0,
        updated_at  TEXT DEFAULT (datetime('now'))
    )""")

    # Stream links — ONLY thing admin needs to add
    c.execute("""CREATE TABLE IF NOT EXISTS stream_links (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        api_id     TEXT NOT NULL,
        language   TEXT NOT NULL,
        url        TEXT NOT NULL,
        is_active  INTEGER DEFAULT 1,
        added_at   TEXT DEFAULT (datetime('now')),
        UNIQUE(api_id, language)
    )""")

    # Reminders
    c.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        api_id    TEXT NOT NULL,
        remind_at TEXT NOT NULL,
        sent      INTEGER DEFAULT 0,
        UNIQUE(user_id, api_id)
    )""")

    # Click tracking
    c.execute("""CREATE TABLE IF NOT EXISTS clicks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        api_id     TEXT,
        language   TEXT,
        clicked_at TEXT DEFAULT (datetime('now'))
    )""")

    conn.commit()
    conn.close()


# ── Users ────────────────────────────────────────────────────────────────────

def upsert_user(user_id, username, first_name):
    conn = get_conn()
    conn.execute("""INSERT INTO users (user_id, username, first_name)
        VALUES (?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_seen=datetime('now')""",
        (user_id, username or "", first_name or "User"))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_user_language(user_id, lang):
    conn = get_conn()
    conn.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
    conn.commit()
    conn.close()


def get_all_user_ids():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users WHERE is_blocked=0").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


def get_user_stats():
    conn = get_conn()
    total  = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    today  = conn.execute("SELECT COUNT(*) as n FROM users WHERE date(joined_at)=date('now')").fetchone()["n"]
    active = conn.execute("SELECT COUNT(*) as n FROM users WHERE last_seen>=datetime('now','-1 day')").fetchone()["n"]
    conn.close()
    return {"total": total, "today": today, "active": active}


# ── Matches — synced from CricAPI ────────────────────────────────────────────

def upsert_match(m):
    """Insert or update a match from CricAPI data."""
    conn = get_conn()
    conn.execute("""INSERT INTO matches
        (api_id, title, team1, team2, match_type, venue, start_time, start_display, status, score, is_ipl)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(api_id) DO UPDATE SET
            title=excluded.title,
            team1=excluded.team1,
            team2=excluded.team2,
            venue=excluded.venue,
            start_time=excluded.start_time,
            start_display=excluded.start_display,
            status=excluded.status,
            score=excluded.score,
            is_ipl=excluded.is_ipl,
            updated_at=datetime('now')""",
        (m["api_id"], m["title"], m["team1"], m["team2"],
         m["match_type"], m["venue"], m["start_time"], m["start_display"],
         m["status"], m["score"], m["is_ipl"]))
    conn.commit()
    conn.close()


def get_match(api_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM matches WHERE api_id=?", (api_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_live_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE status='live' ORDER BY start_time ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ipl_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE is_ipl=1 ORDER BY status DESC, start_time ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE status='upcoming' ORDER BY start_time ASC LIMIT 12"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_other_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE is_ipl=0 ORDER BY status DESC, start_time ASC LIMIT 12"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_matches_for_admin():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches ORDER BY status DESC, start_time ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Stream links — admin managed ─────────────────────────────────────────────

def set_stream_link(api_id, language, url):
    conn = get_conn()
    conn.execute("""INSERT INTO stream_links (api_id, language, url)
        VALUES (?,?,?)
        ON CONFLICT(api_id, language) DO UPDATE SET
            url=excluded.url, is_active=1, added_at=datetime('now')""",
        (api_id, language, url))
    conn.commit()
    conn.close()


def get_stream_link(api_id, language):
    conn = get_conn()
    row = conn.execute(
        "SELECT url FROM stream_links WHERE api_id=? AND language=? AND is_active=1",
        (api_id, language)
    ).fetchone()
    conn.close()
    return row["url"] if row else None


def get_all_links_for_match(api_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT language, url, is_active FROM stream_links WHERE api_id=?", (api_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_stream_link(api_id, language):
    conn = get_conn()
    conn.execute("DELETE FROM stream_links WHERE api_id=? AND language=?", (api_id, language))
    conn.commit()
    conn.close()


def get_matches_needing_links():
    """Return live/upcoming matches that have NO stream links at all."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.* FROM matches m
        WHERE m.status IN ('live','upcoming')
        AND NOT EXISTS (
            SELECT 1 FROM stream_links s WHERE s.api_id=m.api_id AND s.is_active=1
        )
        ORDER BY m.status DESC, m.start_time ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Reminders ─────────────────────────────────────────────────────────────────

def add_reminder(user_id, api_id, remind_at):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO reminders (user_id, api_id, remind_at) VALUES (?,?,?)",
            (user_id, api_id, remind_at))
        conn.commit()
        result = conn.execute(
            "SELECT changes() as c").fetchone()["c"] > 0
    except Exception:
        result = False
    conn.close()
    return result


def get_pending_reminders():
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.*, m.title FROM reminders r
        JOIN matches m ON r.api_id=m.api_id
        WHERE r.sent=0 AND r.remind_at <= datetime('now')
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_reminder_sent(reminder_id):
    conn = get_conn()
    conn.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def get_user_reminders(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.*, m.title, m.start_display FROM reminders r
        JOIN matches m ON r.api_id=m.api_id
        WHERE r.user_id=? AND r.sent=0
        ORDER BY r.remind_at ASC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_reminder(user_id, api_id):
    conn = get_conn()
    conn.execute("DELETE FROM reminders WHERE user_id=? AND api_id=?", (user_id, api_id))
    conn.commit()
    conn.close()


# ── Clicks ────────────────────────────────────────────────────────────────────

def log_click(user_id, api_id, language):
    conn = get_conn()
    conn.execute(
        "INSERT INTO clicks (user_id, api_id, language) VALUES (?,?,?)",
        (user_id, api_id, language))
    conn.commit()
    conn.close()


def get_top_matches_today():
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.title, COUNT(*) as clicks
        FROM clicks c JOIN matches m ON c.api_id=m.api_id
        WHERE date(c.clicked_at)=date('now')
        GROUP BY c.api_id ORDER BY clicks DESC LIMIT 5
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
