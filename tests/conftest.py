"""
Test configuration.

Uses SQLite in-memory so tests are hermetic and never touch the Neon
production database. Each test session gets a fresh schema.

The DATABASE_URL env var is overridden BEFORE importing anything from app
so that database.py picks up SQLite instead of the .env PostgreSQL URL.
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "test-secret-do-not-use-in-prod")

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Patch the database module to use the in-memory engine BEFORE importing main
from app import database, models
from app.database import get_db

# StaticPool forces all connections to reuse the same underlying SQLite
# in-memory database. Without it each new connection sees an empty DB.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

database.engine = _engine
database.SessionLocal = _SessionLocal

# Create all tables from current ORM models (reflects the real schema)
models.Base.metadata.create_all(bind=_engine)

# Import app after patching — main.py's create_all and _ensure_indexes
# will run against the patched engine (SQLite). Some DDL may fail gracefully.
from app.main import app

def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session")
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Register a fresh user per test and return its Authorization headers."""
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/auth/register", json={
        "name": "Test User", "email": email, "password": "pass123",
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
