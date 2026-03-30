import httpx
import logging
from datetime import datetime, timedelta
from config import CRICAPI_KEY, CRICAPI_BASE

logger = logging.getLogger(__name__)


async def _get(endpoint, params):
    params["apikey"] = CRICAPI_KEY
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(f"{CRICAPI_BASE}/{endpoint}", params=params)
            data = resp.json()
            if data.get("status") == "success":
                return data
            logger.warning(f"[CricAPI] {endpoint}: {data.get('reason','unknown error')}")
    except Exception as e:
        logger.error(f"[CricAPI] {endpoint} error: {e}")
    return {}


async def fetch_current_matches():
    data = await _get("currentMatches", {"offset": 0})
    return [_normalise(m) for m in data.get("data", [])]


async def fetch_upcoming_matches():
    data = await _get("matches", {"offset": 0})
    result = []
    for m in data.get("data", []):
        if not m.get("matchStarted", False):
            result.append(_normalise(m))
    return result[:15]


async def fetch_match_detail(api_id):
    data = await _get("match_info", {"id": api_id})
    raw = data.get("data", {})
    return _normalise(raw) if raw else {}


def _normalise(m):
    started = m.get("matchStarted", False)
    ended   = m.get("matchEnded",   False)
    if ended:
        status = "ended"
    elif started:
        status = "live"
    else:
        status = "upcoming"

    date_str = m.get("dateTimeGMT") or m.get("date") or ""
    teams = m.get("teams", [])
    team1 = teams[0] if len(teams) > 0 else m.get("team1", "TBA")
    team2 = teams[1] if len(teams) > 1 else m.get("team2", "TBA")
    name_lower = (m.get("name", "") + " " + str(m.get("series_id", ""))).lower()
    is_ipl = any(k in name_lower for k in ["ipl", "indian premier league"])

    return {
        "api_id":        m.get("id", ""),
        "title":         m.get("name", f"{team1} vs {team2}"),
        "team1":         team1,
        "team2":         team2,
        "match_type":    m.get("matchType", "T20").upper(),
        "venue":         m.get("venue", "TBA"),
        "start_time":    date_str,
        "start_display": _fmt_time(date_str),
        "status":        status,
        "score":         _fmt_score(m.get("score", [])),
        "is_ipl":        1 if is_ipl else 0,
    }


def _fmt_score(scores):
    if not scores:
        return ""
    parts = []
    for s in scores:
        inning = s.get("inning", "")
        r = s.get("r", 0)
        w = s.get("w", 0)
        o = s.get("o", 0)
        short = inning.replace(" Inning", "").replace(" innings", "")
        parts.append(f"{short}: {r}/{w} ({o} ov)")
    return "  |  ".join(parts)


def _fmt_time(date_str):
    if not date_str:
        return "TBA"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        ist = dt + timedelta(hours=5, minutes=30)
        return ist.strftime("%d %b, %I:%M %p IST")
    except Exception:
        return date_str
