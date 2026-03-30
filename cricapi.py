import httpx
import logging
from datetime import datetime, timedelta
from config import CRICAPI_KEY, CRICAPI_BASE

logger = logging.getLogger(__name__)

# STRICT IPL team names — must match exactly as full words
# PSL teams (Peshawar, Lahore, Karachi etc.) are NOT here
IPL_TEAMS = {
    "mumbai indians", "chennai super kings", "royal challengers bengaluru",
    "royal challengers bangalore", "kolkata knight riders",
    "sunrisers hyderabad", "delhi capitals", "rajasthan royals",
    "punjab kings", "lucknow super giants", "gujarat titans",
}

# Short codes only valid when paired with IPL series name
IPL_SHORT = {"mi", "csk", "rcb", "kkr", "srh", "dc", "rr", "pbks", "lsg", "gt"}


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
    data = await _get("currentMatches", {"offset": 0})
    return [_normalise(m) for m in data.get("data", []) if m.get("id")]


async def fetch_upcoming_matches():
    data = await _get("matches", {"offset": 0})
    result = []
    for m in data.get("data", []):
        if not m.get("matchStarted", False) and m.get("id"):
            result.append(_normalise(m))
    return result[:20]


async def fetch_match_detail(api_id):
    data = await _get("match_info", {"id": api_id})
    raw  = data.get("data", {})
    return _normalise(raw) if raw else {}


def _is_ipl(name: str, teams: list) -> bool:
    """
    Strict IPL detection:
    - Match name must explicitly contain 'ipl' or 'indian premier league'
    - OR both teams must be known IPL franchises by full name
    """
    name_lower = name.lower()

    # Most reliable: name contains ipl or indian premier league
    if "ipl" in name_lower or "indian premier league" in name_lower:
        return True

    # Both teams are known IPL franchises (full name match)
    teams_lower = [t.lower().strip() for t in teams]
    if len(teams_lower) >= 2:
        if teams_lower[0] in IPL_TEAMS and teams_lower[1] in IPL_TEAMS:
            return True

    return False


def _normalise(m: dict) -> dict:
    started = m.get("matchStarted", False)
    ended   = m.get("matchEnded",   False)
    status  = "ended" if ended else ("live" if started else "upcoming")

    teams = m.get("teams", [])
    team1 = teams[0] if len(teams) > 0 else m.get("team1", "TBA")
    team2 = teams[1] if len(teams) > 1 else m.get("team2", "TBA")
    name  = m.get("name", f"{team1} vs {team2}")
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
        "is_ipl":        1 if _is_ipl(name, teams) else 0,
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
        short = inning.split(" Inning")[0].split(" innings")[0]
        if len(short) > 20:
            words = short.split()
            short = "".join(w[0] for w in words if w)
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
