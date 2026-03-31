from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/checkins", tags=["checkins"])

HOT_WINDOW_MINUTES = 60


@router.post("", status_code=201)
def checkin(payload: schemas.CheckinCreate, db: Session = Depends(get_db)):
    venue = db.query(models.Venue).filter(models.Venue.id == payload.venue_id).first()
    if not venue:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Local não encontrado")
    db.add(models.Checkin(venue_id=payload.venue_id))
    db.commit()
    cutoff = datetime.utcnow() - timedelta(minutes=HOT_WINDOW_MINUTES)
    count = db.query(func.count(models.Checkin.id)).filter(
        models.Checkin.venue_id == payload.venue_id,
        models.Checkin.created_at >= cutoff,
    ).scalar()
    return {"venue_id": payload.venue_id, "checkin_count": count}


@router.get("/hot", response_model=List[schemas.HotVenue])
def hot_venues(city: str = "Florianópolis", db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(minutes=HOT_WINDOW_MINUTES)
    rows = (
        db.query(models.Venue.id, models.Venue.name, func.count(models.Checkin.id).label("cnt"))
        .join(models.Checkin, models.Checkin.venue_id == models.Venue.id, isouter=True)
        .filter(models.Venue.city == city)
        .filter(
            (models.Checkin.created_at >= cutoff) | (models.Checkin.id == None)
        )
        .group_by(models.Venue.id)
        .order_by(func.count(models.Checkin.id).desc())
        .all()
    )
    return [{"venue_id": r[0], "venue_name": r[1], "checkin_count": r[2]} for r in rows]


@router.get("/counts")
def checkin_counts(city: str = "Florianópolis", db: Session = Depends(get_db)):
    """Retorna dict {venue_id: count} para a última hora."""
    cutoff = datetime.utcnow() - timedelta(minutes=HOT_WINDOW_MINUTES)
    rows = (
        db.query(models.Checkin.venue_id, func.count(models.Checkin.id).label("cnt"))
        .join(models.Venue)
        .filter(models.Venue.city == city, models.Checkin.created_at >= cutoff)
        .group_by(models.Checkin.venue_id)
        .all()
    )
    return {r[0]: r[1] for r in rows}
