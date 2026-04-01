from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/partners", tags=["partners"])


def _require_auth(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return current_user


def _owner_venue_ids(current_user, db: Session) -> list[int]:
    return [
        v.id for v in
        db.query(models.Venue.id).filter(models.Venue.owner_id == current_user.id).all()
    ]


@router.get("/stats", response_model=schemas.PartnerStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
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
    current_user=Depends(_require_auth),
):
    venue_ids = _owner_venue_ids(current_user, db)
    if not venue_ids:
        return []
    return (
        db.query(models.Event)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .filter(models.Event.venue_id.in_(venue_ids))
        .all()
    )


@router.post("/events", response_model=schemas.EventOut)
def create_event(
    payload: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
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
        price_info=payload.price_info,
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
    current_user=Depends(_require_auth),
):
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
    event.price_info = payload.price_info
    event.tags = db.query(models.Tag).filter(models.Tag.id.in_(payload.tag_ids)).all()
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}/feature")
def toggle_feature(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    venue = db.query(models.Venue).filter(
        models.Venue.id == event.venue_id,
        models.Venue.owner_id == current_user.id,
    ).first()
    if not venue:
        raise HTTPException(status_code=403, detail="Sem permissão")
    event.is_featured = not event.is_featured
    db.commit()
    return {"is_featured": event.is_featured}


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
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


@router.get("/analytics", response_model=List[schemas.EventAnalytics])
def get_analytics(
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
    venue_ids = _owner_venue_ids(current_user, db)
    if not venue_ids:
        return []
    events = db.query(models.Event).filter(models.Event.venue_id.in_(venue_ids)).all()
    event_ids = [e.id for e in events]
    bora_counts = dict(
        db.query(models.BoraReaction.event_id, func.count(models.BoraReaction.id))
        .filter(models.BoraReaction.event_id.in_(event_ids))
        .group_by(models.BoraReaction.event_id)
        .all()
    ) if event_ids else {}
    return [
        schemas.EventAnalytics(
            event_id=e.id,
            title=e.title,
            date=e.date,
            view_count=e.view_count or 0,
            bora_count=bora_counts.get(e.id, 0),
        )
        for e in events
    ]


@router.post("/claim-venue/{venue_id}", response_model=schemas.VenueOut)
def claim_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_require_auth),
):
    venue = db.query(models.Venue).filter(models.Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue não encontrado")
    ADMIN_ID = 1
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
    current_user=Depends(_require_auth),
):
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
