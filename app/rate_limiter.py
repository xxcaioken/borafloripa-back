"""Simple in-memory sliding-window rate limiter.

Suitable for single-instance deployments (Azure App Service F1/B1).
For multi-instance, replace the store with Redis.
"""
from collections import defaultdict, deque
from time import time
from fastapi import HTTPException, Query

_store: dict[str, deque] = defaultdict(deque)


def _check(key: str, max_calls: int, window: int) -> None:
    now = time()
    dq = _store[key]
    cutoff = now - window
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= max_calls:
        raise HTTPException(
            status_code=429,
            detail="Muitas requisições. Aguarde um momento e tente novamente.",
        )
    dq.append(now)


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def bora_rate_limit(session_id: str = Query(..., description="ID anônimo do browser")) -> str:
    """Max 30 bora toggles per session per minute."""
    _check(f"bora:{session_id}", max_calls=30, window=60)
    return session_id


def vibe_rate_limit(session_id: str = Query(...)) -> str:
    """Max 20 vibe votes per session per minute."""
    _check(f"vibe:{session_id}", max_calls=20, window=60)
    return session_id


def checkin_rate_limit(venue_id: int, session_id: str) -> None:
    """Max 5 checkins per session+venue per 10 minutes."""
    _check(f"checkin:{session_id}:{venue_id}", max_calls=5, window=600)
