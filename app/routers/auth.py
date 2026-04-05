import os
import json as json_mod
import secrets
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from app import models, schemas
from app.database import get_db

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.sendgrid.net")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "apikey")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SENDER_EMAIL  = os.getenv("SENDER_EMAIL", "noreply@borafloripa.com")
FRONTEND_URL  = os.getenv("FRONTEND_URL", "http://localhost:5173")
RESET_EXPIRE_HOURS = 1


def _send_reset_email(to_email: str, token: str):
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Redefinir sua senha — Bora Floripa"
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(
        f"Clique no link para redefinir sua senha:\n{reset_link}\n\nExpira em 1 hora.",
        "plain"
    ))
    msg.attach(MIMEText(f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2 style="color:#00e676">Bora Floripa</h2>
      <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
      <a href="{reset_link}" style="display:inline-block;background:#00e676;color:#000;
         padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;margin:16px 0">
        Redefinir senha
      </a>
      <p style="color:#888;font-size:13px">O link expira em 1 hora. Se não foi você, ignore este email.</p>
    </div>
    """, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "bora-floripa-secret-dev-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


@router.post("/register", response_model=schemas.Token)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="user",
        pref_music=payload.pref_music,
        pref_vibes=payload.pref_vibes,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return schemas.Token(
        access_token=create_token(user.id),
        token_type="bearer",
        user=user,
    )


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    return schemas.Token(
        access_token=create_token(user.id),
        token_type="bearer",
        user=user,
    )


@router.get("/me", response_model=schemas.UserOut)
def me(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return current_user


@router.post("/forgot-password")
def forgot_password(body: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    # Sempre 200 — não revela se o email existe (proteção contra enumeração)
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=RESET_EXPIRE_HOURS)
        db.commit()
        try:
            _send_reset_email(user.email, token)
        except Exception as e:
            print(f"[EMAIL ERROR] {e}")
    return {"message": "Se este email estiver cadastrado, você receberá um link em breve."}


@router.post("/reset-password")
def reset_password(body: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.reset_token == body.token,
        models.User.reset_token_expires > datetime.utcnow(),
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Link inválido ou expirado.")
    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return {"message": "Senha redefinida com sucesso."}


@router.post("/google", response_model=schemas.Token)
def google_login(body: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    """Sign in / register via Google One Tap. Verifies the GSI credential (ID token) with Google."""
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google login não configurado no servidor")

    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={body.credential}"
        with urllib.request.urlopen(url, timeout=8) as resp:
            info = json_mod.loads(resp.read())
    except urllib.error.HTTPError:
        raise HTTPException(status_code=400, detail="Token Google inválido")
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível verificar o token Google")

    if info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Token não corresponde a este aplicativo")
    if info.get("email_verified") not in ("true", True):
        raise HTTPException(status_code=400, detail="E-mail Google não verificado")

    google_id = info["sub"]
    email = info["email"]
    name = info.get("name") or email.split("@")[0]

    # Busca por google_id → fallback por email → cria novo
    user = db.query(models.User).filter(models.User.google_id == google_id).first()
    if not user:
        user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        if not user.google_id:
            user.google_id = google_id
    else:
        user = models.User(
            name=name,
            email=email,
            google_id=google_id,
            hashed_password=None,
            role="user",
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return schemas.Token(access_token=create_token(user.id), token_type="bearer", user=user)


@router.put("/me/preferences", response_model=schemas.UserOut)
def update_preferences(
    pref_music: str = None,
    pref_vibes: str = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    if pref_music is not None:
        current_user.pref_music = pref_music
    if pref_vibes is not None:
        current_user.pref_vibes = pref_vibes
    db.commit()
    db.refresh(current_user)
    return current_user
