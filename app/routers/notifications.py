from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas, database
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=List[schemas.NotificationOut])
def get_notifications(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id)
        .order_by(models.Notification.created_at.desc())
        .limit(20)
        .all()
    )


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id, models.Notification.read == False)  # noqa: E712
        .count()
    )
    return {"count": count}


@router.post("/read-all", status_code=204)
def mark_all_read(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id,
        models.Notification.read == False,  # noqa: E712
    ).update({"read": True})
    db.commit()


@router.post("/{notification_id}/read", status_code=204)
def mark_one_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user.id,
    ).update({"read": True})
    db.commit()


def create_notification(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    body: str,
    url: str | None = None,
):
    """Helper para criar notificação in-app — chamado por outros routers."""
    n = models.Notification(user_id=user_id, type=type, title=title, body=body, url=url)
    db.add(n)
    # não faz commit — deixa para o caller commitar junto com outras operações
