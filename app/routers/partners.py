from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/partners", tags=["partners"])


def _require_user(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return current_user


@router.get("/stats", response_model=schemas.PartnerStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    venues = db.query(models.Venue).filter(models.Venue.owner_id == current_user.id).all()
    venue_ids = [v.id for v in venues]
    total = db.query(models.Event).filter(models.Event.venue_id.in_(venue_ids)).count() if venue_ids else 0
    featured = (
        db.query(models.Event)
        .filter(models.Event.venue_id.in_(venue_ids), models.Event.is_featured == True)
        .count()
        if venue_ids else 0
    )
    return schemas.PartnerStats(total_events=total, featured_events=featured, venues=venues)


@router.get("/events", response_model=List[schemas.EventOut])
def get_partner_events(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    venues = db.query(models.Venue).filter(models.Venue.owner_id == current_user.id).all()
    venue_ids = [v.id for v in venues]
    if not venue_ids:
        return []
    return db.query(models.Event).filter(models.Event.venue_id.in_(venue_ids)).all()


@router.post("/events", response_model=schemas.EventOut)
def create_event(
    payload: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    # Verify the venue belongs to the current user
    venue = db.query(models.Venue).filter(
        models.Venue.id == payload.venue_id,
        models.Venue.owner_id == current_user.id,
    ).first()
    if not venue:
        raise HTTPException(status_code=403, detail="Venue não pertence a você")
    tags = db.query(models.Tag).filter(models.Tag.id.in_(payload.tag_ids)).all()
    event = models.Event(
        venue_id=payload.venue_id,
        title=payload.title,
        description=payload.description,
        date=payload.date,
        vibe_status=payload.vibe_status,
        is_featured=False,
        category=payload.category,
        is_temporary=payload.is_temporary,
        organizers=payload.organizers,
        tags=tags,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.put("/events/{event_id}", response_model=schemas.EventOut)
def update_event(
    event_id: int,
    payload: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    venue = db.query(models.Venue).filter(
        models.Venue.id == event.venue_id,
        models.Venue.owner_id == current_user.id,
    ).first()
    if not venue:
        raise HTTPException(status_code=403, detail="Sem permissão")
    event.title = payload.title
    event.description = payload.description
    event.date = payload.date
    event.vibe_status = payload.vibe_status
    event.category = payload.category
    event.is_temporary = payload.is_temporary
    event.organizers = payload.organizers
    event.tags = db.query(models.Tag).filter(models.Tag.id.in_(payload.tag_ids)).all()
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    venue = db.query(models.Venue).filter(
        models.Venue.id == event.venue_id,
        models.Venue.owner_id == current_user.id,
    ).first()
    if not venue:
        raise HTTPException(status_code=403, detail="Sem permissão")
    db.delete(event)
    db.commit()
    return {"ok": True}


@router.post("/claim-venue/{venue_id}", response_model=schemas.VenueOut)
def claim_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Partner claims ownership of an existing venue (imported from OSM)."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    venue = db.query(models.Venue).filter(models.Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue não encontrado")
    ADMIN_ID = 1  # venues importados ficam com owner_id=1 (admin) até um parceiro reivindicar
    if venue.owner_id and venue.owner_id != ADMIN_ID and venue.owner_id != current_user.id:
        raise HTTPException(status_code=409, detail="Venue já tem um dono cadastrado")
    venue.owner_id = current_user.id
    db.commit()
    db.refresh(venue)
    return venue


@router.put("/venues/{venue_id}", response_model=schemas.VenueOut)
def update_venue(
    venue_id: int,
    payload: schemas.VenueCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    venue = db.query(models.Venue).filter(
        models.Venue.id == venue_id,
        models.Venue.owner_id == current_user.id,
    ).first()
    if not venue:
        raise HTTPException(status_code=403, detail="Sem permissão")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    db.commit()
    db.refresh(venue)
    return venue
