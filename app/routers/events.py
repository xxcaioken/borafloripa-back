from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
import json
from app import models, schemas
from app.database import get_db

VALID_CATEGORIES = {"rua", "bar", "balada", "cultura", "temporario"}
VALID_PERIODS = {"manha", "tarde", "noite"}
VALID_SORTS = {"date", "popular", "featured"}

HOT_WINDOW_MINUTES = 60


def _get_checkin_counts(db: Session, venue_ids: list) -> dict:
    if not venue_ids:
        return {}
    cutoff = datetime.utcnow() - timedelta(minutes=HOT_WINDOW_MINUTES)
    rows = (
        db.query(models.Checkin.venue_id, func.count(models.Checkin.id).label("cnt"))
        .filter(models.Checkin.venue_id.in_(venue_ids), models.Checkin.created_at >= cutoff)
        .group_by(models.Checkin.venue_id)
        .all()
    )
    return {r[0]: r[1] for r in rows}

router = APIRouter(prefix="/api/events", tags=["events"])


def _is_open_now(hours_json: str) -> bool:
    if not hours_json:
        return False
    try:
        hours = json.loads(hours_json)
        days = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
        now = datetime.now()
        day_idx = now.isoweekday() % 7
        today = days[day_idx]
        slot = hours.get(today, 'Fechado')
        if not slot or slot == 'Fechado':
            return False
        parts = slot.replace('–', '-').split('-')
        if len(parts) < 2:
            return False
        open_h, open_m = map(int, parts[0].strip().split(':'))
        close_h, close_m = map(int, parts[1].strip().split(':'))
        current = now.hour * 60 + now.minute
        open_min = open_h * 60 + open_m
        close_min = close_h * 60 + close_m
        if close_min < open_min:
            return current >= open_min or current <= close_min
        return open_min <= current <= close_min
    except Exception:
        return False


@router.get("/feed", response_model=List[schemas.EventOut])
def get_feed(
    city: str = "Florianópolis",
    tag: Optional[str] = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    open_now: bool = False,
    accessible: bool = False,
    temporary: bool = False,
    today: bool = False,
    sort: Optional[str] = None,  # "date" | "popular" | "featured" (default: featured+date)
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Categoria inválida. Use: {', '.join(VALID_CATEGORIES)}")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit deve estar entre 1 e 100")
    if sort and sort not in VALID_SORTS:
        raise HTTPException(status_code=400, detail=f"sort inválido. Use: {', '.join(VALID_SORTS)}")

    query = (
        db.query(models.Event)
        .join(models.Venue)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .filter(models.Venue.city == city)
    )
    if today:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        query = query.filter(models.Event.date >= today_start, models.Event.date < today_end)
    if category:
        query = query.filter(models.Event.category == category)
    if temporary:
        query = query.filter(models.Event.is_temporary == True)
    if tag:
        query = query.join(models.Event.tags).filter(models.Tag.name == tag)
    if q:
        q_like = f"%{q}%"
        query = query.filter(
            models.Event.title.ilike(q_like) | models.Venue.name.ilike(q_like)
        )
    if accessible:
        query = query.filter(models.Venue.wheelchair == True)

    if sort == "date":
        query = query.order_by(models.Event.date.asc())
    elif sort == "popular":
        query = query.order_by(models.Event.view_count.desc(), models.Event.date.asc())
    else:
        query = query.order_by(models.Event.is_featured.desc(), models.Event.date.asc())

    # open_now requires Python-side filtering, so paginate after
    if open_now:
        events = [e for e in query.all() if _is_open_now(e.venue.hours)]
        events = events[offset: offset + limit]
    else:
        events = query.offset(offset).limit(limit).all()

    venue_ids = list({e.venue_id for e in events})
    counts = _get_checkin_counts(db, venue_ids)
    result = []
    for e in events:
        out = schemas.EventOut.model_validate(e)
        out.venue.checkin_count = counts.get(e.venue_id, 0)
        result.append(out)
    return result


@router.get("/categories")
def get_categories(response: Response):
    response.headers["Cache-Control"] = "public, max-age=3600"
    return [
        {"id": "rua",       "label": "Rolê na Rua", "emoji": "🌆"},
        {"id": "bar",       "label": "Barzinho",    "emoji": "🍺"},
        {"id": "balada",    "label": "Balada",      "emoji": "💃"},
        {"id": "cultura",   "label": "Cultura",     "emoji": "🎭"},
        {"id": "temporario","label": "Especial",    "emoji": "⚡"},
    ]


@router.get("/venues", response_model=List[schemas.VenueOut])
def get_venues(
    city: str = "Florianópolis",
    q: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Venue).filter(models.Venue.city == city)
    if q:
        query = query.filter(models.Venue.name.ilike(f"%{q}%"))
    return query.order_by(models.Venue.name).all()


@router.get("/new-venues", response_model=List[schemas.VenueOut])
def get_new_venues(city: str = "Florianópolis", response: Response = None, db: Session = Depends(get_db)):
    if response:
        response.headers["Cache-Control"] = "public, max-age=300"
    return db.query(models.Venue).filter(
        models.Venue.city == city, models.Venue.is_new == True
    ).all()


@router.get("/map")
def get_map_events(city: str = "Florianópolis", response: Response = None, db: Session = Depends(get_db)):
    """Returns venues with their upcoming events and checkin counts for the map view."""
    if response:
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"
    from datetime import date as date_cls
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = today_start + timedelta(days=7)

    venues = db.query(models.Venue).filter(models.Venue.city == city).all()
    venue_ids = [v.id for v in venues]
    counts = _get_checkin_counts(db, venue_ids)

    # Events in the next 7 days per venue
    events_by_venue: dict = {}
    rows = (
        db.query(models.Event)
        .filter(
            models.Event.venue_id.in_(venue_ids),
            models.Event.date >= today_start,
            models.Event.date <= week_end,
        )
        .order_by(models.Event.date.asc())
        .all()
    )
    for e in rows:
        events_by_venue.setdefault(e.venue_id, []).append({
            "id": e.id,
            "title": e.title,
            "date": e.date.isoformat(),
            "vibe_status": e.vibe_status,
            "category": e.category,
            "is_featured": e.is_featured,
            "tags": [t.name for t in e.tags],
        })

    result = []
    for v in venues:
        result.append({
            "id": v.id,
            "name": v.name,
            "lat": v.lat,
            "lng": v.lng,
            "address": v.address,
            "instagram": v.instagram,
            "category": v.category or "bar",
            "checkin_count": counts.get(v.id, 0),
            "events": events_by_venue.get(v.id, []),
        })
    return result


@router.get("/trending", response_model=List[schemas.EventOut])
def get_trending(
    city: str = "Florianópolis",
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """Events with most Bora reactions in the last 24 hours."""
    from datetime import date as _date
    cutoff = datetime.utcnow() - timedelta(hours=24)
    bora_counts = dict(
        db.query(models.BoraReaction.event_id, func.count(models.BoraReaction.id).label("cnt"))
        .filter(models.BoraReaction.created_at >= cutoff)
        .group_by(models.BoraReaction.event_id)
        .order_by(func.count(models.BoraReaction.id).desc())
        .limit(limit * 2)
        .all()
    )
    if not bora_counts:
        return []
    events = (
        db.query(models.Event)
        .join(models.Venue)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .filter(models.Event.id.in_(bora_counts.keys()), models.Venue.city == city)
        .all()
    )
    events.sort(key=lambda e: bora_counts.get(e.id, 0), reverse=True)
    venue_ids = list({e.venue_id for e in events})
    counts = _get_checkin_counts(db, venue_ids)
    result = []
    for event in events[:limit]:
        out = schemas.EventOut.model_validate(event)
        out.venue.checkin_count = counts.get(event.venue_id, 0)
        result.append(out)
    return result


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.get("/nearby", response_model=List[schemas.EventOut])
def get_nearby_events(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    limit: int = 10,
    response: Response = None,
    db: Session = Depends(get_db),
):
    """Eventos próximos a uma coordenada, ordenados por distância."""
    if radius_km < 0.1 or radius_km > 50:
        raise HTTPException(status_code=400, detail="radius_km deve estar entre 0.1 e 50")
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit deve estar entre 1 e 50")

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = today_start + timedelta(days=7)

    events = (
        db.query(models.Event)
        .join(models.Venue)
        .options(joinedload(models.Event.venue), joinedload(models.Event.tags))
        .filter(models.Event.date >= today_start, models.Event.date <= week_end)
        .all()
    )

    with_dist = [
        (e, _haversine_km(lat, lng, e.venue.lat, e.venue.lng))
        for e in events
        if e.venue.lat and e.venue.lng
    ]
    with_dist = [(e, d) for e, d in with_dist if d <= radius_km]
    with_dist.sort(key=lambda x: x[1])

    nearby = [e for e, _ in with_dist[:limit]]
    venue_ids = list({e.venue_id for e in nearby})
    counts = _get_checkin_counts(db, venue_ids)
    result = []
    for event in nearby:
        out = schemas.EventOut.model_validate(event)
        out.venue.checkin_count = counts.get(event.venue_id, 0)
        result.append(out)

    if response:
        response.headers["Cache-Control"] = "public, max-age=60"
    return result


@router.get("/tags")
def get_tags(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=3600"
    return [t.name for t in db.query(models.Tag).all()]


@router.get("/tags-full", response_model=List[schemas.TagOut])
def get_tags_full(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=3600"
    return db.query(models.Tag).order_by(models.Tag.name).all()


@router.get("/tourist", response_model=List[schemas.EventOut])
def get_tourist_events(
    date_from: str,
    date_to: str,
    period: Optional[str] = None,  # "manha" | "tarde" | "noite" | None (all day)
    city: str = "Florianópolis",
    db: Session = Depends(get_db),
):
    """Retorna eventos para o roteiro do turista por período e intervalo de datas."""
    PERIOD_HOURS = {
        "manha": (6, 12),
        "tarde": (12, 18),
        "noite": (18, 24),
    }
    if period and period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"Período inválido. Use: {', '.join(VALID_PERIODS)}")
    try:
        dt_from = datetime.fromisoformat(date_from)
        dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD.")
    if dt_to - dt_from > timedelta(days=31):
        raise HTTPException(status_code=400, detail="Intervalo máximo de 31 dias.")

    query = (
        db.query(models.Event)
        .join(models.Venue)
        .filter(
            models.Venue.city == city,
            models.Event.date >= dt_from,
            models.Event.date < dt_to,
        )
        .order_by(models.Event.date)
    )
    events = query.all()

    if period and period in PERIOD_HOURS:
        h_start, h_end = PERIOD_HOURS[period]
        events = [e for e in events if h_start <= e.date.hour < h_end]

    venue_ids = list({e.venue_id for e in events})
    counts = _get_checkin_counts(db, venue_ids)
    result = []
    for event in events:
        out = schemas.EventOut.model_validate(event)
        out.venue.checkin_count = counts.get(event.venue_id, 0)
        result.append(out)
    return result


@router.get("/{event_id}", response_model=schemas.EventOut)
def get_event(
    event_id: int,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Deduplicate view counts by session_id (one view per session per event)
    from app.rate_limiter import _check as _rate_check, HTTPException as _RL_HTTPException
    count_view = True
    if session_id:
        try:
            _rate_check(f"view:{session_id}:{event_id}", max_calls=1, window=3600)
        except Exception:
            count_view = False

    if count_view:
        event.view_count = (event.view_count or 0) + 1
        db.commit()

    counts = _get_checkin_counts(db, [event.venue_id])
    out = schemas.EventOut.model_validate(event)
    out.venue.checkin_count = counts.get(event.venue_id, 0)
    return out


@router.get("/{event_id}/stats")
def get_event_stats(
    event_id: int,
    response: Response,
    db: Session = Depends(get_db),
):
    """Retorna estatísticas públicas leves de um evento (views, boras, checkins)."""
    event = db.query(models.Event.view_count, models.Event.venue_id).filter(
        models.Event.id == event_id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    bora_count = db.query(func.count(models.BoraReaction.id)).filter(
        models.BoraReaction.event_id == event_id
    ).scalar()

    counts = _get_checkin_counts(db, [event.venue_id])
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return {
        "event_id": event_id,
        "view_count": event.view_count or 0,
        "bora_count": bora_count,
        "checkin_count": counts.get(event.venue_id, 0),
    }
