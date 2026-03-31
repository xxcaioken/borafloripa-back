from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/bora", tags=["bora"])


@router.post("/{event_id}", response_model=schemas.BoraReactionOut)
def toggle_bora(
    event_id: int,
    session_id: str = Query(..., description="ID anônimo do browser"),
    db: Session = Depends(get_db),
):
    existing = db.query(models.BoraReaction).filter(
        models.BoraReaction.event_id == event_id,
        models.BoraReaction.session_id == session_id,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        reacted = False
    else:
        db.add(models.BoraReaction(event_id=event_id, session_id=session_id))
        db.commit()
        reacted = True

    count = db.query(func.count(models.BoraReaction.id)).filter(
        models.BoraReaction.event_id == event_id
    ).scalar()

    return {"event_id": event_id, "count": count, "reacted": reacted}


@router.get("/counts")
def bora_counts(
    event_ids: str = Query(..., description="IDs separados por vírgula"),
    session_id: str = Query(..., description="ID anônimo do browser"),
    db: Session = Depends(get_db),
):
    """Retorna {event_id: {count, reacted}} para uma lista de eventos."""
    ids = [int(i) for i in event_ids.split(",") if i.strip().isdigit()]
    if not ids:
        return {}

    counts = (
        db.query(models.BoraReaction.event_id, func.count(models.BoraReaction.id).label("cnt"))
        .filter(models.BoraReaction.event_id.in_(ids))
        .group_by(models.BoraReaction.event_id)
        .all()
    )
    reacted = (
        db.query(models.BoraReaction.event_id)
        .filter(
            models.BoraReaction.event_id.in_(ids),
            models.BoraReaction.session_id == session_id,
        )
        .all()
    )
    reacted_set = {r[0] for r in reacted}
    count_map = {r[0]: r[1] for r in counts}

    return {
        eid: {"count": count_map.get(eid, 0), "reacted": eid in reacted_set}
        for eid in ids
    }
