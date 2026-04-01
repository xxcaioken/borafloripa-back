from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import json
from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/communities", tags=["communities"])


def _is_member_fast(community: models.Community, user, user_community_ids: set) -> bool:
    if not user:
        return False
    if community.id in user_community_ids:
        return True
    return _is_member_by_prefs(community, user)


def _is_member_by_prefs(community: models.Community, user) -> bool:
    prefs = set()
    try:
        prefs.update(json.loads(user.pref_music or '[]'))
        prefs.update(json.loads(user.pref_vibes or '[]'))
    except Exception:
        pass
    MUSIC_MAP = {
        'Funk': 'funk', 'Eletrônico': 'eletronico', 'Pagode': 'pagode',
        'Sertanejo': 'sertanejo', 'Rock': 'rock', 'MPB': 'mpb', 'Reggae': 'reggae',
    }
    VIBE_MAP = {
        'Rooftop': 'rooftop', 'Pet Friendly': 'pet-friendly', 'Happy Hour': 'happy-hour',
        'Chopp Artesanal': 'chopp', 'Comer e Beber': 'comer-beber', 'TV com Esportes': 'tv-esportes',
    }
    pref_id = MUSIC_MAP.get(community.tag_name) or VIBE_MAP.get(community.tag_name)
    return bool(pref_id and pref_id in prefs)


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
    community_ids = [c.id for c in communities]

    # Batch member counts in one query
    counts = dict(
        db.query(models.community_members.c.community_id, func.count())
        .filter(models.community_members.c.community_id.in_(community_ids))
        .group_by(models.community_members.c.community_id)
        .all()
    ) if community_ids else {}

    # Batch check current user membership
    user_community_ids: set = set()
    if current_user:
        rows = db.query(models.community_members.c.community_id).filter(
            models.community_members.c.user_id == current_user.id
        ).all()
        user_community_ids = {r[0] for r in rows}

    result = []
    for c in communities:
        is_member = _is_member_fast(c, current_user, user_community_ids)
        result.append(schemas.CommunityOut(
            id=c.id,
            tag_name=c.tag_name,
            name=c.name,
            description=c.description,
            discount_code=c.discount_code if is_member else None,
            member_count=counts.get(c.id, 0),
            is_member=is_member,
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
