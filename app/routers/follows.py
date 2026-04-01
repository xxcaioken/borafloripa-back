from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.database import get_db
from app.routers.partners import _require_auth

router = APIRouter(prefix="/api/follows", tags=["follows"])


@router.get("/venues", response_model=List[schemas.VenueOut])
def list_followed_venues(
    current_user: models.User = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    return current_user.followed_venues


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
