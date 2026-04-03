import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./borafloripa.db")

# Neon retorna URLs com prefixo "postgres://" — SQLAlchemy exige "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite precisa de connect_args especial; PostgreSQL não
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
else:
    # Neon free tier pauses after inactivity — set connect_timeout so startup
    # doesn't hang forever waiting for the instance to wake up.
    connect_args = {"connect_timeout": 30}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,       # re-test connections before use
        pool_recycle=300,         # recycle connections every 5 min
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
