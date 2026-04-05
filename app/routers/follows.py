import os
import json as json_mod
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime
from app import models, schemas
from app.database import get_db
from app.routers.partners import _require_auth

router = APIRouter(prefix="/api/follows", tags=["follows"])


# ── Followed venues list ──────────────────────────────────────────────────────

@router.get("/venues", response_model=List[schemas.VenueOut])
def list_followed_venues(
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Venue)
        .join(models.user_followed_venues, models.user_followed_venues.c.venue_id == models.Venue.id)
        .filter(models.user_followed_venues.c.user_id == current_user.id)
        .all()
    )


@router.post("/venues/{venue_id}")
def follow_venue(
    venue_id: int,
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    venue = db.query(models.Venue).filter(models.Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Local não encontrado")
    if venue not in current_user.followed_venues:
        current_user.followed_venues.append(venue)
        db.commit()
    return {"following": True, "venue_id": venue_id}


@router.delete("/venues/{venue_id}")
def unfollow_venue(
    venue_id: int,
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    venue = db.query(models.Venue).filter(models.Venue.id == venue_id).first()
    if venue and venue in current_user.followed_venues:
        current_user.followed_venues.remove(venue)
        db.commit()
    return {"following": False, "venue_id": venue_id}


# ── Feed de eventos dos locais seguidos ───────────────────────────────────────

@router.get("/venues/feed", response_model=List[schemas.EventOut])
def followed_venues_feed(
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    """Próximos eventos de todos os venues que o usuário segue."""
    venue_ids = [v.id for v in current_user.followed_venues]
    if not venue_ids:
        return []
    return (
        db.query(models.Event)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .filter(
            models.Event.venue_id.in_(venue_ids),
            models.Event.date >= datetime.utcnow(),
        )
        .order_by(models.Event.date.asc())
        .limit(20)
        .all()
    )


# ── Push notifications ────────────────────────────────────────────────────────

VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL       = os.getenv("VAPID_EMAIL", "mailto:admin@borafloripa.com")


def _send_push(endpoint: str, p256dh: str, auth: str, title: str, body: str, url: str = "/") -> None:
    if not VAPID_PRIVATE_KEY:
        return
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
            data=json_mod.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_EMAIL},
        )
    except Exception as ex:
        print(f"[PUSH] send failed: {ex}")


def notify_venue_followers(db: Session, venue_id: int, title: str, body: str, url: str = "/") -> None:
    """Envia push + notificação in-app para todos os seguidores de um venue."""
    follower_ids = (
        db.query(models.user_followed_venues.c.user_id)
        .filter(models.user_followed_venues.c.venue_id == venue_id)
        .all()
    )
    if not follower_ids:
        return
    user_ids = [r[0] for r in follower_ids]

    # In-app notifications (sempre, independente de VAPID)
    for uid in user_ids:
        n = models.Notification(user_id=uid, type="new_event", title=title, body=body, url=url)
        db.add(n)
    db.commit()

    # Push notifications (só se VAPID configurado)
    if VAPID_PRIVATE_KEY:
        subs = db.query(models.PushSubscription).filter(
            models.PushSubscription.user_id.in_(user_ids)
        ).all()
        for sub in subs:
            _send_push(sub.endpoint, sub.p256dh, sub.auth, title, body, url)


@router.get("/vapid-key")
def get_vapid_public_key():
    """Retorna a chave pública VAPID para o frontend assinar subscriptions."""
    return {"public_key": VAPID_PUBLIC_KEY or None}


class PushSubscriptionBody(schemas.BaseModel if hasattr(schemas, 'BaseModel') else object):
    endpoint: str
    p256dh: str
    auth: str


from pydantic import BaseModel as _PydanticBase

class PushSubBody(_PydanticBase):
    endpoint: str
    p256dh: str
    auth: str


@router.post("/push-subscription", status_code=201)
def save_push_subscription(
    body: PushSubBody,
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    existing = db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == body.endpoint
    ).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = body.p256dh
        existing.auth = body.auth
    else:
        sub = models.PushSubscription(
            user_id=current_user.id,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
        )
        db.add(sub)
    db.commit()
    return {"ok": True}


@router.delete("/push-subscription")
def remove_push_subscription(
    body: PushSubBody,
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == body.endpoint,
        models.PushSubscription.user_id == current_user.id,
    ).delete()
    db.commit()
    return {"ok": True}
