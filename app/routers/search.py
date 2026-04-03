from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def global_search(
    q: str,
    city: str = "Florianópolis",
    limit: int = 8,
    response: Response = None,
    db: Session = Depends(get_db),
):
    """Busca global — retorna eventos e locais que correspondem à query."""
    if not q or len(q.strip()) < 2:
        return {"events": [], "venues": []}

    like = f"%{q.strip()}%"

    events = (
        db.query(models.Event)
        .join(models.Venue)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .filter(
            models.Venue.city == city,
            models.Event.title.ilike(like) | models.Venue.name.ilike(like),
        )
        .order_by(models.Event.is_featured.desc(), models.Event.date.asc())
        .limit(limit)
        .all()
    )

    venues = (
        db.query(models.Venue)
        .filter(
            models.Venue.city == city,
            models.Venue.name.ilike(like) | models.Venue.address.ilike(like),
        )
        .limit(limit)
        .all()
    )

    if response:
        response.headers["Cache-Control"] = "private, max-age=10"

    return {
        "events": [schemas.EventOut.model_validate(e) for e in events],
        "venues": [schemas.VenueOut.model_validate(v) for v in venues],
    }
