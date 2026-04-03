import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as sa_text
from app import models, database
from app.routers import events, partners, auth, checkins, communities, bora, saved, vibes, follows, search, admin
from app.routers.auth import hash_password
from datetime import datetime, timedelta
import json

try:
    models.Base.metadata.create_all(bind=database.engine)
except Exception as _e:
    print(f"[startup] create_all warning: {_e}")


def _ensure_indexes():
    """Create performance indexes idempotently (safe to run on already-populated DBs)."""
    stmts = [
        "CREATE INDEX IF NOT EXISTS ix_checkins_venue_created ON checkins (venue_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_bora_event_session ON bora_reactions (event_id, session_id)",
        "CREATE INDEX IF NOT EXISTS ix_events_featured_date ON events (is_featured DESC, date ASC)",
        "CREATE INDEX IF NOT EXISTS ix_events_venue_id ON events (venue_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_followed_venues_user ON user_followed_venues (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_saved_events_user ON user_saved_events (user_id)",
    ]
    with database.engine.connect() as conn:
        for stmt in stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception:
                pass  # index may already exist under a different name
        conn.commit()


try:
    _ensure_indexes()
except Exception as _idx_err:
    print(f"[startup] _ensure_indexes skipped: {_idx_err}")

app = FastAPI(title="Bora Floripa API")

# Em produção, definir ALLOWED_ORIGINS como CSV (ex: "https://bora.azurestaticapps.net")
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(partners.router)
app.include_router(checkins.router)
app.include_router(communities.router)
app.include_router(bora.router)
app.include_router(saved.router)
app.include_router(vibes.router)
app.include_router(follows.router)
app.include_router(search.router)
app.include_router(admin.router)

@app.get("/health")
def health():
    from sqlalchemy import text as _t
    db_ok = False
    try:
        with database.engine.connect() as conn:
            conn.execute(_t("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "error",
        "version": "1.0.0",
    }


@app.on_event("startup")
def seed():
    """Cria apenas usuários de sistema e tags. Venues são importados via scripts/import_venues.py."""
    db = database.SessionLocal()
    try:
        if db.query(models.User).first():
            return

        admin = models.User(name="Admin", email="admin@borafloripa.com", role="admin",
                           hashed_password=hash_password("admin123"))
        db.add(admin)
        db.commit()

        tag_names = [
            "Eletrônico", "Funk", "Pagode", "Sertanejo", "Rock",
            "MPB", "Reggae", "Instagramável", "Pet Friendly", "Rooftop",
            "Dance Floor", "Música ao Vivo", "Happy Hour", "Chopp Artesanal",
            "Comer e Beber", "TV com Esportes",
        ]
        db.add_all([models.Tag(name=n) for n in tag_names])
        db.commit()

        communities_seed = [
            models.Community(tag_name="Eletrônico",  name="Galera do Eletrônico", description="Fãs de música eletrônica e baladas em Floripa",     discount_code="ELETRO10"),
            models.Community(tag_name="Funk",        name="Baile do Funk",        description="Quem curte Funk sabe: a festa é aqui",               discount_code="FUNK15"),
            models.Community(tag_name="Pagode",      name="Pagode da Ilha",       description="Saudade, pagode e cerveja gelada",                   discount_code="PAGODE10"),
            models.Community(tag_name="MPB",         name="MPB & Cia",            description="Música brasileira de verdade",                       discount_code="MPB20"),
            models.Community(tag_name="Reggae",      name="Reggae Roots",         description="Paz, amor e reggae na beira da lagoa",               discount_code="REGGAE10"),
            models.Community(tag_name="Rooftop",     name="Clube do Rooftop",     description="Vista linda, drinks gelados e vibe boa",             discount_code="ROOF15"),
            models.Community(tag_name="Pet Friendly",name="Pet & Bier",           description="Para quem não sai sem o melhor amigo",               discount_code="PET20"),
        ]
        db.add_all(communities_seed)
        db.commit()
    finally:
        db.close()
