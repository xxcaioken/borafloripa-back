from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/communities", tags=["communities"])


def _is_member(community: models.Community, user: models.User | None) -> bool:
    if not user:
        return False
    prefs = set()
    try:
        prefs.update(json.loads(user.pref_music or '[]'))
        prefs.update(json.loads(user.pref_vibes or '[]'))
    except Exception:
        pass
    # map community tag_name to pref ids
    MUSIC_MAP = {
        'Funk': 'funk', 'Eletrônico': 'eletronico', 'Pagode': 'pagode',
        'Sertanejo': 'sertanejo', 'Rock': 'rock', 'MPB': 'mpb', 'Reggae': 'reggae',
    }
    VIBE_MAP = {
        'Rooftop': 'rooftop', 'Pet Friendly': 'pet-friendly', 'Happy Hour': 'happy-hour',
        'Chopp Artesanal': 'chopp', 'Comer e Beber': 'comer-beber', 'TV com Esportes': 'tv-esportes',
    }
    pref_id = MUSIC_MAP.get(community.tag_name) or VIBE_MAP.get(community.tag_name)
    if pref_id and pref_id in prefs:
        return True
    return user in community.members


@router.get("", response_model=List[schemas.CommunityOut])
def list_communities(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    communities = db.query(models.Community).all()
    result = []
    for c in communities:
        result.append(schemas.CommunityOut(
            id=c.id,
            tag_name=c.tag_name,
            name=c.name,
            description=c.description,
            discount_code=c.discount_code if _is_member(c, current_user) else None,
            member_count=len(c.members),
            is_member=_is_member(c, current_user),
        ))
    return result


@router.post("/{community_id}/join", response_model=schemas.CommunityOut)
def join_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    community = db.query(models.Community).filter(models.Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Comunidade não encontrada")
    if current_user not in community.members:
        community.members.append(current_user)
        db.commit()
    return schemas.CommunityOut(
        id=community.id,
        tag_name=community.tag_name,
        name=community.name,
        description=community.description,
        discount_code=community.discount_code,
        member_count=len(community.members),
        is_member=True,
    )
