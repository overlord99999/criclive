import httpx
from config import CRICAPI_KEY, CRICAPI_BASE


async def fetch_live_matches():
    """Fetch currently live matches from CricAPI."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{CRICAPI_BASE}/currentMatches",
                params={"apikey": CRICAPI_KEY, "offset": 0}
            )
            data = resp.json()
            if data.get("status") == "success":
                return data.get("data", [])
    except Exception as e:
        print(f"[CricAPI] Error fetching live matches: {e}")
    return []


async def fetch_match_score(match_api_id):
    """Fetch detailed score for a specific match."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{CRICAPI_BASE}/match_info",
                params={"apikey": CRICAPI_KEY, "id": match_api_id}
            )
            data = resp.json()
            if data.get("status") == "success":
                return data.get("data", {})
    except Exception as e:
        print(f"[CricAPI] Error fetching score: {e}")
    return {}


def format_score(match_data):
    """Format CricAPI match data into a score string."""
    try:
        scores = match_data.get("score", [])
        if not scores:
            return None
        parts = []
        for inning in scores:
            r = inning.get("r", 0)
            w = inning.get("w", 0)
            o = inning.get("o", 0)
            name = inning.get("inning", "")
            parts.append(f"{name}: {r}/{w} ({o} ov)")
        return " | ".join(parts)
    except Exception:
        return None
