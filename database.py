import sqlite3
import json
from datetime import datetime
from config import DB_FILE


def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            language    TEXT DEFAULT 'en',
            joined_at   TEXT DEFAULT (datetime('now')),
            last_seen   TEXT DEFAULT (datetime('now')),
            is_blocked  INTEGER DEFAULT 0
        )
    """)

    # Matches table (admin managed)
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            team1       TEXT,
            team2       TEXT,
            match_type  TEXT DEFAULT 'T20',
            venue       TEXT,
            start_time  TEXT,
            status      TEXT DEFAULT 'upcoming',
            score       TEXT,
            is_ipl      INTEGER DEFAULT 0,
            is_visible  INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # Stream links table (admin adds per match per language)
    c.execute("""
        CREATE TABLE IF NOT EXISTS stream_links (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id    INTEGER NOT NULL,
            language    TEXT NOT NULL,
            url         TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1,
            added_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)

    # Reminders table
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            match_id    INTEGER NOT NULL,
            remind_at   TEXT NOT NULL,
            sent        INTEGER DEFAULT 0,
            UNIQUE(user_id, match_id)
        )
    """)

    # Broadcast log
    c.execute("""
        CREATE TABLE IF NOT EXISTS broadcasts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            message     TEXT,
            sent_to     INTEGER DEFAULT 0,
            sent_at     TEXT DEFAULT (datetime('now'))
        )
    """)

    # Click tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            match_id    INTEGER,
            language    TEXT,
            clicked_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# ─── User helpers ────────────────────────────────────────────────────────────

def upsert_user(user_id, username, first_name):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name,
            last_seen  = datetime('now')
    """, (user_id, username, first_name))
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


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users WHERE is_blocked=0").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


def get_user_stats():
    conn = get_conn()
    total   = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    today   = conn.execute("SELECT COUNT(*) as n FROM users WHERE date(joined_at)=date('now')").fetchone()["n"]
    active  = conn.execute("SELECT COUNT(*) as n FROM users WHERE last_seen >= datetime('now','-1 day')").fetchone()["n"]
    conn.close()
    return {"total": total, "today": today, "active": active}


# ─── Match helpers ───────────────────────────────────────────────────────────

def add_match(title, team1, team2, match_type, venue, start_time, is_ipl=0):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO matches (title, team1, team2, match_type, venue, start_time, is_ipl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, team1, team2, match_type, venue, start_time, is_ipl))
    match_id = c.lastrowid
    conn.commit()
    conn.close()
    return match_id


def get_all_matches(only_visible=True):
    conn = get_conn()
    q = "SELECT * FROM matches"
    if only_visible:
        q += " WHERE is_visible=1"
    q += " ORDER BY start_time ASC"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_match(match_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_match_status(match_id, status, score=None):
    conn = get_conn()
    if score:
        conn.execute("UPDATE matches SET status=?, score=? WHERE id=?", (status, score, match_id))
    else:
        conn.execute("UPDATE matches SET status=? WHERE id=?", (status, match_id))
    conn.commit()
    conn.close()


def update_match(match_id, **kwargs):
    conn = get_conn()
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [match_id]
    conn.execute(f"UPDATE matches SET {fields} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete_match(match_id):
    conn = get_conn()
    conn.execute("DELETE FROM matches WHERE id=?", (match_id,))
    conn.execute("DELETE FROM stream_links WHERE match_id=?", (match_id,))
    conn.commit()
    conn.close()


def get_live_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE status='live' AND is_visible=1 ORDER BY start_time ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ipl_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE is_ipl=1 AND is_visible=1 ORDER BY start_time ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_matches():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM matches WHERE status='upcoming' AND is_visible=1 ORDER BY start_time ASC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Stream link helpers ─────────────────────────────────────────────────────

def add_stream_link(match_id, language, url):
    conn = get_conn()
    conn.execute("""
        INSERT INTO stream_links (match_id, language, url)
        VALUES (?, ?, ?)
        ON CONFLICT DO NOTHING
    """, (match_id, language, url))
    conn.commit()
    conn.close()


def update_stream_link(match_id, language, url):
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM stream_links WHERE match_id=? AND language=?", (match_id, language)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE stream_links SET url=?, is_active=1 WHERE match_id=? AND language=?",
            (url, match_id, language)
        )
    else:
        conn.execute(
            "INSERT INTO stream_links (match_id, language, url) VALUES (?,?,?)",
            (match_id, language, url)
        )
    conn.commit()
    conn.close()


def get_stream_link(match_id, language):
    conn = get_conn()
    row = conn.execute(
        "SELECT url FROM stream_links WHERE match_id=? AND language=? AND is_active=1",
        (match_id, language)
    ).fetchone()
    conn.close()
    return row["url"] if row else None


def get_all_stream_links(match_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT language, url, is_active FROM stream_links WHERE match_id=?", (match_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_stream_link(match_id, language):
    conn = get_conn()
    conn.execute("DELETE FROM stream_links WHERE match_id=? AND language=?", (match_id, language))
    conn.commit()
    conn.close()


# ─── Reminder helpers ────────────────────────────────────────────────────────

def add_reminder(user_id, match_id, remind_at):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO reminders (user_id, match_id, remind_at) VALUES (?,?,?)",
            (user_id, match_id, remind_at)
        )
        conn.commit()
        result = True
    except Exception:
        result = False
    conn.close()
    return result


def get_pending_reminders():
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.*, m.title, m.team1, m.team2
        FROM reminders r JOIN matches m ON r.match_id=m.id
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
        SELECT r.*, m.title, m.start_time
        FROM reminders r JOIN matches m ON r.match_id=m.id
        WHERE r.user_id=? AND r.sent=0
        ORDER BY r.remind_at ASC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_reminder(user_id, match_id):
    conn = get_conn()
    conn.execute("DELETE FROM reminders WHERE user_id=? AND match_id=?", (user_id, match_id))
    conn.commit()
    conn.close()


# ─── Click tracking ──────────────────────────────────────────────────────────

def log_click(user_id, match_id, language):
    conn = get_conn()
    conn.execute(
        "INSERT INTO clicks (user_id, match_id, language) VALUES (?,?,?)",
        (user_id, match_id, language)
    )
    conn.commit()
    conn.close()


def get_top_matches_today():
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.title, COUNT(*) as clicks
        FROM clicks c JOIN matches m ON c.match_id=m.id
        WHERE date(c.clicked_at)=date('now')
        GROUP BY c.match_id ORDER BY clicks DESC LIMIT 5
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
