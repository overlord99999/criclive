import httpx
import logging
from datetime import datetime, timedelta
from config import CRICAPI_KEY, CRICAPI_BASE

logger = logging.getLogger(__name__)

# All known IPL-related keywords in CricAPI match names
IPL_KEYWORDS = [
    "ipl", "indian premier league",
    "mi ", "csk", "rcb", "kkr", "srh", "dc ", "rr ", "pbks", "lsg", "gt ",
    "mumbai indians", "chennai super kings", "royal challengers",
    "kolkata knight riders", "sunrisers hyderabad", "delhi capitals",
    "rajasthan royals", "punjab kings", "lucknow super giants", "gujarat titans",
]


async def _get(endpoint, params):
    params["apikey"] = CRICAPI_KEY
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{CRICAPI_BASE}/{endpoint}", params=params)
            data = resp.json()
            if data.get("status") == "success":
                return data
            logger.warning(f"[CricAPI] {endpoint}: {data.get('reason','error')}")
    except Exception as e:
        logger.error(f"[CricAPI] {endpoint}: {e}")
    return {}


async def fetch_current_matches():
    """All live/recent matches."""
    data = await _get("currentMatches", {"offset": 0})
    return [_normalise(m) for m in data.get("data", []) if m.get("id")]


async def fetch_upcoming_matches():
    """Upcoming scheduled matches."""
    data = await _get("matches", {"offset": 0})
    result = []
    for m in data.get("data", []):
        if not m.get("matchStarted", False) and m.get("id"):
            result.append(_normalise(m))
    return result[:20]


async def fetch_match_detail(api_id):
    data = await _get("match_info", {"id": api_id})
    raw = data.get("data", {})
    return _normalise(raw) if raw else {}


def _is_ipl(name: str) -> bool:
    name_lower = name.lower()
    return any(k in name_lower for k in IPL_KEYWORDS)


def _normalise(m: dict) -> dict:
    started = m.get("matchStarted", False)
    ended   = m.get("matchEnded",   False)
    status  = "ended" if ended else ("live" if started else "upcoming")

    teams = m.get("teams", [])
    team1 = teams[0] if len(teams) > 0 else m.get("team1", "TBA")
    team2 = teams[1] if len(teams) > 1 else m.get("team2", "TBA")

    name     = m.get("name", f"{team1} vs {team2}")
    date_str = m.get("dateTimeGMT") or m.get("date") or ""

    return {
        "api_id":        m.get("id", ""),
        "title":         name,
        "team1":         team1,
        "team2":         team2,
        "match_type":    (m.get("matchType") or "T20").upper(),
        "venue":         m.get("venue", "TBA"),
        "start_time":    date_str,
        "start_display": _fmt_time(date_str),
        "status":        status,
        "score":         _fmt_score(m.get("score", [])),
        "is_ipl":        1 if _is_ipl(name) else 0,
    }


def _fmt_score(scores: list) -> str:
    if not scores:
        return ""
    parts = []
    for s in scores:
        inning = s.get("inning", "")
        r = s.get("r", 0)
        w = s.get("w", 0)
        o = s.get("o", 0)
        # Shorten inning name: "Mumbai Indians Inning 1" → "MI"
        short = inning.split(" Inning")[0].split(" innings")[0]
        # Further shorten long names
        if len(short) > 20:
            words = short.split()
            short = "".join(w[0] for w in words if w)  # initials
        parts.append(f"{short}: {r}/{w} ({o}ov)")
    return "   |   ".join(parts)


def _fmt_time(date_str: str) -> str:
    if not date_str:
        return "TBA"
    try:
        dt  = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        ist = dt + timedelta(hours=5, minutes=30)
        return ist.strftime("%d %b %Y  •  %I:%M %p IST")
    except Exception:
        return date_str
