"""
admin.py — Endpoints protegidos por X-Admin-Key para operações de backoffice.

Usado pelo pipeline de extração local para enviar venues scraped para o banco de prod.
A chave é definida via env var ADMIN_API_KEY.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from app import models
from app.database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

CATEGORY_MAP = {
    "night_club": "balada", "bar": "bar", "restaurant": "bar",
    "cafe": "bar", "pub": "bar", "lounge": "bar",
    "beach_club": "balada", "music_venue": "balada",
    "cultural_center": "cultura", "theater": "cultura",
    "park": "rua", "street_food": "rua",
}
VALID_CATEGORIES = {"bar", "balada", "cultura", "rua", "temporario"}


def _require_admin(x_admin_key: Optional[str] = Header(None)):
    secret = os.getenv("ADMIN_API_KEY", "")
    if not secret:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY não configurada no servidor")
    if x_admin_key != secret:
        raise HTTPException(status_code=401, detail="Chave de admin inválida")
    return True


# ── Schemas de entrada ────────────────────────────────────────────────────

class VenueBulkItem(BaseModel):
    name: str
    city: str = "Florianópolis"
    lat: float = 0.0
    lng: float = 0.0
    address: Optional[str] = None
    instagram: Optional[str] = None
    whatsapp: Optional[str] = None
    hours: Optional[str] = None          # JSON string "{Seg: '18:00–02:00', ...}"
    category: Optional[str] = "bar"
    logo_url: Optional[str] = None
    place_id: Optional[str] = None       # Google Place ID (para dedup futuro)
    rating: Optional[float] = None
    reviews: Optional[int] = None
    is_new: bool = False


class EnrichItem(BaseModel):
    name: str                            # chave de busca
    city: str = "Florianópolis"
    hours: Optional[str] = None
    address: Optional[str] = None
    neighborhood: Optional[str] = None
    instagram: Optional[str] = None
    whatsapp: Optional[str] = None
    logo_url: Optional[str] = None
    photo_url: Optional[str] = None
    rating: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _normalize_category(raw: Optional[str]) -> str:
    if not raw:
        return "bar"
    lower = raw.lower().replace(" ", "_")
    return CATEGORY_MAP.get(lower, raw if raw in VALID_CATEGORIES else "bar")


def _extract_neighborhood(address: Optional[str]) -> Optional[str]:
    """Extrai bairro de endereço no formato Google Maps: "Rua X - Bairro, Cidade - UF"."""
    if not address or ' - ' not in address:
        return None
    after_dash = address.split(' - ', 1)[1]
    bairro = after_dash.split(',')[0].strip()
    _ignore = {'florianópolis', 'florianopolis', 'sc', 'brasil', 'brazil', ''}
    return bairro if bairro.lower() not in _ignore else None


def _clean_instagram(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    slug = raw.strip().lstrip("@").split("/")[-1].rstrip("/")
    return f"@{slug}" if slug else None


def _find_admin(db: Session) -> models.User:
    admin = db.query(models.User).filter(models.User.role == "admin").first()
    if not admin:
        raise HTTPException(status_code=500, detail="Usuário admin não encontrado no banco")
    return admin


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/venues/bulk")
def bulk_import_venues(
    venues: List[VenueBulkItem],
    db: Session = Depends(get_db),
    _auth=Depends(_require_admin),
):
    """
    Importa/atualiza venues em lote a partir do pipeline de extração.

    - Upsert por (name, city): insere novo ou atualiza campos vazios.
    - Retorna contagem de inserted / updated / skipped.
    """
    if not venues:
        return {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}

    if len(venues) > 500:
        raise HTTPException(status_code=400, detail="Máximo 500 venues por request")

    admin = _find_admin(db)

    # Carrega nomes existentes em memória para lookup O(1)
    existing: dict[tuple, models.Venue] = {
        (v.name.strip().lower(), v.city.lower()): v
        for v in db.query(models.Venue).filter(models.Venue.city == "Florianópolis").all()
    }

    inserted, updated, skipped, errors = 0, 0, 0, []

    for item in venues:
        try:
            key = (item.name.strip().lower(), item.city.lower())
            category = _normalize_category(item.category)
            instagram = _clean_instagram(item.instagram)

            if key in existing:
                # Atualiza apenas campos ainda vazios (não sobrescreve dados manuais)
                venue = existing[key]
                if venue is None:  # inserido no mesmo lote — não há objeto para atualizar
                    skipped += 1
                    continue
                changed = False
                if not venue.hours and item.hours:
                    venue.hours = item.hours;    changed = True
                if not venue.address and item.address:
                    venue.address = item.address; changed = True
                if not venue.neighborhood and item.address:
                    nb = _extract_neighborhood(item.address)
                    if nb:
                        venue.neighborhood = nb; changed = True
                if not venue.instagram and instagram:
                    venue.instagram = instagram;  changed = True
                if not venue.whatsapp and item.whatsapp:
                    venue.whatsapp = item.whatsapp; changed = True
                if not venue.logo_url and item.logo_url:
                    venue.logo_url = item.logo_url; changed = True
                if venue.lat == 0.0 and item.lat:
                    venue.lat = item.lat; changed = True
                if venue.lng == 0.0 and item.lng:
                    venue.lng = item.lng; changed = True

                if changed:
                    updated += 1
                else:
                    skipped += 1
            else:
                db.add(models.Venue(
                    owner_id=admin.id,
                    name=item.name.strip(),
                    city=item.city,
                    lat=item.lat,
                    lng=item.lng,
                    address=item.address,
                    neighborhood=_extract_neighborhood(item.address),
                    instagram=instagram,
                    whatsapp=item.whatsapp,
                    hours=item.hours,
                    category=category,
                    is_new=item.is_new,
                    logo_url=item.logo_url,
                ))
                inserted += 1
                existing[key] = None  # marca como existente (sem objeto real) para o lote atual

        except Exception as e:
            errors.append({"name": item.name, "error": str(e)[:120]})

    db.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total": len(venues),
    }


@router.patch("/venues/enrich")
def enrich_venues(
    items: List[EnrichItem],
    db: Session = Depends(get_db),
    _auth=Depends(_require_admin),
):
    """
    Enriquece venues existentes com dados do scraper (horários, address, instagram).
    Só preenche campos que estão vazios — nunca sobrescreve dados manuais.
    """
    if not items:
        return {"updated": 0, "not_found": 0}

    updated, not_found = 0, []

    for item in items:
        venue = db.query(models.Venue).filter(
            models.Venue.name.ilike(item.name.strip()),
            models.Venue.city == item.city,
        ).first()

        if not venue:
            not_found.append(item.name)
            continue

        changed = False
        if not venue.hours and item.hours:
            venue.hours = item.hours; changed = True
        if not venue.address and item.address:
            venue.address = item.address; changed = True
        if item.neighborhood and venue.neighborhood != item.neighborhood:
            venue.neighborhood = item.neighborhood; changed = True
        elif not venue.neighborhood and item.address:
            nb = _extract_neighborhood(item.address)
            if nb:
                venue.neighborhood = nb; changed = True
        if not venue.instagram and item.instagram:
            venue.instagram = _clean_instagram(item.instagram); changed = True
        if not venue.whatsapp and item.whatsapp:
            venue.whatsapp = item.whatsapp; changed = True
        if not venue.logo_url and item.logo_url:
            venue.logo_url = item.logo_url; changed = True
        if not venue.photo_url and item.photo_url:
            venue.photo_url = item.photo_url; changed = True

        if changed:
            updated += 1

    db.commit()
    return {"updated": updated, "not_found": not_found}


@router.get("/venues/stats")
def admin_venue_stats(
    db: Session = Depends(get_db),
    _auth=Depends(_require_admin),
):
    """Overview rápido do banco para monitorar imports."""
    total = db.query(models.Venue).count()
    with_hours = db.query(models.Venue).filter(models.Venue.hours != None).count()
    with_coords = db.query(models.Venue).filter(
        models.Venue.lat != 0.0, models.Venue.lng != 0.0
    ).count()
    with_instagram = db.query(models.Venue).filter(models.Venue.instagram != None).count()
    total_events = db.query(models.Event).count()
    return {
        "venues": {
            "total": total,
            "with_hours": with_hours,
            "with_coords": with_coords,
            "with_instagram": with_instagram,
            "missing_hours": total - with_hours,
            "missing_coords": total - with_coords,
        },
        "events": {"total": total_events},
    }
