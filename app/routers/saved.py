from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.database import get_db
from app.routers.partners import _require_auth

router = APIRouter(prefix="/api/saved", tags=["saved"])


@router.get("", response_model=List[schemas.EventOut])
def get_saved(
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    return user.saved_events


@router.post("/{event_id}")
def save_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if event not in user.saved_events:
        user.saved_events.append(event)
        db.commit()
    return {"saved": True}


@router.delete("/{event_id}")
def unsave_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if event in user.saved_events:
        user.saved_events.remove(event)
        db.commit()
    return {"saved": False}
