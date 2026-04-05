from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app import models, schemas, database
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_auth(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(401, "Não autenticado")
    return current_user


# ── Parceiro: gerenciar cupons ────────────────────────────────────

@router.get("/my", response_model=List[schemas.CouponOut])
def list_my_coupons(
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_auth),
):
    venue_ids = [v.id for v in db.query(models.Venue.id).filter(models.Venue.owner_id == user.id).all()]
    return db.query(models.Coupon).filter(models.Coupon.venue_id.in_(venue_ids)).all()


@router.post("/venues/{venue_id}", response_model=schemas.CouponOut, status_code=201)
def create_coupon(
    venue_id: int,
    body: schemas.CouponCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_auth),
):
    venue = db.query(models.Venue).filter(
        models.Venue.id == venue_id, models.Venue.owner_id == user.id
    ).first()
    if not venue:
        raise HTTPException(403, "Sem permissão")
    if db.query(models.Coupon).filter(models.Coupon.code == body.code.upper()).first():
        raise HTTPException(409, "Código já em uso")
    if not (0 < body.discount_pct <= 100):
        raise HTTPException(400, "discount_pct deve ser 1-100")

    coupon = models.Coupon(
        code=body.code.upper().strip(),
        description=body.description,
        discount_pct=body.discount_pct,
        venue_id=venue_id,
        community_id=body.community_id,
        max_uses=body.max_uses,
        expires_at=body.expires_at,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.patch("/venues/{venue_id}/{coupon_id}/toggle", response_model=schemas.CouponOut)
def toggle_coupon(
    venue_id: int,
    coupon_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_auth),
):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.venue_id == venue_id,
    ).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado")
    venue = db.query(models.Venue).filter(
        models.Venue.id == venue_id, models.Venue.owner_id == user.id
    ).first()
    if not venue:
        raise HTTPException(403, "Sem permissão")
    coupon.active = not coupon.active
    db.commit()
    db.refresh(coupon)
    return coupon


# ── Usuário: ver e usar cupons ────────────────────────────────────

@router.get("/community/{community_id}", response_model=List[schemas.CouponOut])
def get_community_coupons(
    community_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_auth),
):
    """Retorna cupons ativos para membros de uma comunidade específica."""
    is_member = any(c.id == community_id for c in user.communities)
    if not is_member:
        raise HTTPException(403, "Você não é membro desta comunidade")

    now = datetime.utcnow()
    return (
        db.query(models.Coupon)
        .filter(
            models.Coupon.community_id == community_id,
            models.Coupon.active == True,  # noqa: E712
            (models.Coupon.expires_at == None) | (models.Coupon.expires_at > now),  # noqa: E711
            models.Coupon.used_count < models.Coupon.max_uses,
        )
        .all()
    )


@router.post("/{code}/redeem")
def redeem_coupon(
    code: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_auth),
):
    """Registra uso de cupom — decrementa usos restantes."""
    now = datetime.utcnow()
    coupon = db.query(models.Coupon).filter(
        models.Coupon.code == code.upper(),
        models.Coupon.active == True,  # noqa: E712
    ).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado ou inativo")
    if coupon.expires_at and coupon.expires_at < now:
        raise HTTPException(410, "Cupom expirado")
    if coupon.used_count >= coupon.max_uses:
        raise HTTPException(410, "Cupom esgotado")

    # Verificar membresia se o cupom é de comunidade
    if coupon.community_id:
        is_member = any(c.id == coupon.community_id for c in user.communities)
        if not is_member:
            raise HTTPException(403, "Este cupom é exclusivo para membros da comunidade")

    coupon.used_count += 1
    db.commit()
    return {
        "code": coupon.code,
        "description": coupon.description,
        "discount_pct": coupon.discount_pct,
        "remaining": coupon.max_uses - coupon.used_count,
    }
