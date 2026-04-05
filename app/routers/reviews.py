from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas, database
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/venues/{venue_id}", response_model=List[schemas.ReviewOut])
def get_venue_reviews(venue_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Review)
        .filter(models.Review.venue_id == venue_id)
        .order_by(models.Review.created_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for r in rows:
        out = schemas.ReviewOut(
            id=r.id,
            rating=r.rating,
            text=r.text,
            created_at=r.created_at,
            user_name=r.user.name.split()[0] if r.user else "Anônimo",
        )
        result.append(out)
    return result


@router.post("/venues/{venue_id}", response_model=schemas.ReviewOut, status_code=201)
def upsert_review(
    venue_id: int,
    body: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not (1 <= body.rating <= 5):
        raise HTTPException(400, "Rating deve ser entre 1 e 5")

    venue = db.query(models.Venue).filter(models.Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue não encontrado")

    existing = (
        db.query(models.Review)
        .filter(models.Review.user_id == user.id, models.Review.venue_id == venue_id)
        .first()
    )
    if existing:
        existing.rating = body.rating
        existing.text = body.text
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = models.Review(
            user_id=user.id,
            venue_id=venue_id,
            rating=body.rating,
            text=body.text,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    return schemas.ReviewOut(
        id=row.id,
        rating=row.rating,
        text=row.text,
        created_at=row.created_at,
        user_name=user.name.split()[0],
    )


@router.get("/venues/{venue_id}/summary")
def get_venue_review_summary(venue_id: int, db: Session = Depends(get_db)):
    rows = db.query(models.Review).filter(models.Review.venue_id == venue_id).all()
    if not rows:
        return {"count": 0, "avg": None, "distribution": {}}
    avg = sum(r.rating for r in rows) / len(rows)
    dist = {str(i): sum(1 for r in rows if r.rating == i) for i in range(1, 6)}
    return {"count": len(rows), "avg": round(avg, 1), "distribution": dist}
