from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/vibes", tags=["vibes"])

VIBE_TAGS = [
    "Funk", "Eletrônico", "Pagode", "Rock", "MPB", "Reggae", "Sertanejo",
    "Rooftop", "Pet Friendly", "Happy Hour", "Dance Floor", "Música ao Vivo",
    "Instagramável", "Chopp Artesanal", "Comer e Beber", "TV com Esportes",
    "Universitário", "Alternativo", "LGBTQIA+", "Família",
]


@router.get("/tags")
def get_vibe_tags():
    return VIBE_TAGS


@router.get("/venue/{venue_id}", response_model=List[schemas.VibeTag])
def get_venue_vibes(
    venue_id: int,
    session_id: str = Query(default=""),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.VenueVibeVote.tag_name, func.count(models.VenueVibeVote.id))
        .filter(models.VenueVibeVote.venue_id == venue_id)
        .group_by(models.VenueVibeVote.tag_name)
        .order_by(func.count(models.VenueVibeVote.id).desc())
        .limit(10)
        .all()
    )
    voted_tags = set()
    if session_id:
        voted_tags = {
            v.tag_name for v in db.query(models.VenueVibeVote)
            .filter(
                models.VenueVibeVote.venue_id == venue_id,
                models.VenueVibeVote.session_id == session_id,
            ).all()
        }
    return [
        schemas.VibeTag(tag_name=tag, count=count, voted=(tag in voted_tags))
        for tag, count in rows
    ]


@router.post("/venue/{venue_id}/{tag_name}")
def vote_vibe(
    venue_id: int,
    tag_name: str,
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    if tag_name not in VIBE_TAGS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Tag de vibe inválida")
    existing = db.query(models.VenueVibeVote).filter(
        models.VenueVibeVote.venue_id == venue_id,
        models.VenueVibeVote.tag_name == tag_name,
        models.VenueVibeVote.session_id == session_id,
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"voted": False}
    db.add(models.VenueVibeVote(venue_id=venue_id, tag_name=tag_name, session_id=session_id))
    db.commit()
    return {"voted": True}
