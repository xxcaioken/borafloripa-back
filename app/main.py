import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import models, database
from app.routers import events, partners, auth, checkins, communities, bora, saved, vibes
from app.routers.auth import hash_password
from datetime import datetime, timedelta
import json

models.Base.metadata.create_all(bind=database.engine)

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
