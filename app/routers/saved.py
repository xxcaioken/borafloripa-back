from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from app import models, schemas
from app.database import get_db
from app.routers.partners import _require_auth

router = APIRouter(prefix="/api/saved", tags=["saved"])


@router.get("", response_model=List[schemas.EventOut])
def get_saved(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_require_auth),
):
    events = (
        db.query(models.Event)
        .join(models.user_saved_events, models.user_saved_events.c.event_id == models.Event.id)
        .filter(models.user_saved_events.c.user_id == current_user.id)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .all()
    )
    return events


@router.post("/{event_id}")
def save_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_require_auth),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if event not in current_user.saved_events:
        current_user.saved_events.append(event)
        db.commit()
    return {"saved": True}


@router.delete("/{event_id}")
def unsave_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_require_auth),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if event and event in current_user.saved_events:
        current_user.saved_events.remove(event)
        db.commit()
    return {"saved": False}
