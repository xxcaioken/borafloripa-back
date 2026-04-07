# Bora Floripa — Backend

API REST do Bora Floripa. FastAPI + SQLAlchemy + Neon PostgreSQL. Deploy automático no Azure App Service.

[![CI](https://github.com/xxcaioken/borafloripa-back/actions/workflows/backend.yml/badge.svg)](https://github.com/xxcaioken/borafloripa-back/actions/workflows/backend.yml)

**Produção:** [bora-floripa-api.azurewebsites.net](https://bora-floripa-api.azurewebsites.net)

---

## Stack

| Tech | Versão | Decisão |
|------|--------|---------|
| Python | 3.11 | Runtime do Azure App Service |
| FastAPI | 0.135 | — |
| SQLAlchemy | 2.0 | ORM |
| Pydantic | v2 | `from_attributes = True` |
| Neon PostgreSQL | free tier | Pausa após 5min — `connect_timeout=30` |
| SQLite | — | Fallback automático em dev (sem `DATABASE_URL`) |
| passlib sha256_crypt | — | **Não bcrypt** — conflito de versão com passlib 1.7 |
| python-jose | — | JWT 7 dias |
| pywebpush | 2.0 | Push notifications VAPID |
| azure-storage-blob | 12+ | Upload de fotos de venues |
| pytest + httpx | — | Testes com SQLite in-memory |

---

## Setup local

```bash
git clone https://github.com/xxcaioken/borafloripa-back.git
cd borafloripa-back

python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate      # Linux/Mac

pip install -r requirements-dev.txt  # inclui pytest + httpx
```

Crie `.env`:

```env
DATABASE_URL=postgresql://neondb_owner:SENHA@ep-xxx.neon.tech/borafloripa?sslmode=require
SECRET_KEY=string-hex-64-chars
ADMIN_API_KEY=string-hex-64-chars
ALLOWED_ORIGINS=http://localhost:5173
```

> Sem `DATABASE_URL`, cai automaticamente para `sqlite:///./borafloripa.db`.

```bash
uvicorn app.main:app --reload --port 8000

# Verificar saúde
curl http://localhost:8000/health
# {"status":"ok","db":"connected","version":"1.0.0"}
```

**Atenção Windows:** processos uvicorn podem travar a porta após Ctrl+C.
```bash
netstat -ano | findstr ":8000"
taskkill /F /PID <pid>
```

---

## Testes

```bash
source venv/Scripts/activate
python -m pytest          # roda todos (27 testes)
python -m pytest -v       # verbose
python -m pytest tests/test_auth.py  # só um arquivo
```

Os testes usam **SQLite in-memory com StaticPool** — zero dependência externa, zero risco de tocar o banco de produção.

| Arquivo | O que cobre |
|---------|-------------|
| `tests/test_auth.py` | Register, login, senha errada, email desconhecido, rotas protegidas sem token |
| `tests/test_events.py` | Feed, lista de venues, filtros, 404 em venue inexistente |
| `tests/test_partners.py` | Guards de ownership (403/401), analytics com parâmetro inválido |

**Regra:** toda feature nova exige testes. Testes falhos bloqueiam o deploy (CI gate).

---

## Estrutura

```
app/
├── main.py          # Entry point: CORS, routers, startup (seed + migrations DDL)
├── database.py      # Engine SQLAlchemy (Neon + SQLite fallback), pool config
├── models.py        # Modelos ORM + índices compostos
├── schemas.py       # Schemas Pydantic v2 (Input/Output)
└── routers/
    ├── auth.py          # /api/auth — register, login, forgot/reset, Google OAuth
    ├── events.py        # /api/events — feed, venues, nearby, trending, tourist, map, tags
    ├── partners.py      # /api/partners — dashboard, CRUD eventos, foto upload, analytics
    ├── admin.py         # /api/admin — bulk import, enrich (X-Admin-Key)
    ├── communities.py   # /api/communities — list, join, leave
    ├── bora.py          # /api/bora — toggle reação "Bora!"
    ├── saved.py         # /api/saved — salvar/dessalvar evento
    ├── vibes.py         # /api/vibes — voto de vibe em venue
    ├── follows.py       # /api/follows — follow/unfollow venue, VAPID push
    ├── reviews.py       # /api/reviews — avaliações 1-5 estrelas
    ├── notifications.py # /api/notifications — in-app, unread count, mark read
    ├── coupons.py       # /api/coupons — CRUD cupons, redeem
    ├── checkins.py      # /api/checkins — check-in anônimo, hot zones
    └── search.py        # /api/search — busca global venues + eventos

tests/
├── conftest.py      # SQLite in-memory, StaticPool, override get_db
├── test_auth.py
├── test_events.py
└── test_partners.py

requirements.txt         # Produção
requirements-dev.txt     # + pytest + httpx
pytest.ini
startup.sh               # gunicorn -w 1 -k uvicorn.workers.UvicornWorker
```

---

## Endpoints

### Públicos / Autenticados (JWT opcional)

| Método | Rota | Params relevantes |
|--------|------|-------------------|
| `GET` | `/health` | — |
| `POST` | `/api/auth/register` | `name, email, password` |
| `POST` | `/api/auth/login` | `email, password` |
| `POST` | `/api/auth/google` | `credential` (Google ID token) |
| `POST` | `/api/auth/forgot-password` | `email` |
| `POST` | `/api/auth/reset-password` | `token, new_password` |
| `GET` | `/api/auth/me` | — |
| `GET` | `/api/events/feed` | `city, today, free, neighborhood, category, open_now, sort, limit` |
| `GET` | `/api/events/venues` | `city, category, neighborhood, q, open_now` |
| `GET` | `/api/events/venues/:id` | — |
| `GET` | `/api/events/map` | `city` |
| `GET` | `/api/events/trending` | `city` |
| `GET` | `/api/events/tourist` | `city, date_from, date_to` |
| `GET` | `/api/events/tags-full` | — |
| `GET` | `/api/search` | `q` |
| `POST` | `/api/bora/:event_id` | — |
| `POST` | `/api/checkins` | `venue_id, session_id` |
| `GET` | `/api/checkins/hot` | — |
| `GET` | `/api/communities` | — |

### Requerem JWT

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET/POST/DELETE` | `/api/saved/:event_id` | Salvar/remover evento |
| `GET/POST/DELETE` | `/api/follows/venues/:id` | Follow/unfollow venue |
| `GET` | `/api/follows/venues/feed` | Feed dos venues seguidos |
| `POST/DELETE` | `/api/follows/push-subscription` | Subscribe/unsubscribe push |
| `GET` | `/api/reviews/venues/:id` | Reviews de um venue |
| `POST` | `/api/reviews/venues/:id` | Criar/atualizar review (upsert) |
| `GET` | `/api/notifications` | Notificações do usuário |
| `POST` | `/api/notifications/read-all` | Marcar todas como lidas |
| `GET` | `/api/communities/:id/coupons` | Cupons da comunidade (só membros) |

### Parceiro (JWT)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/partners/stats` | Totais: eventos, destaques, venues |
| `GET` | `/api/partners/events` | Lista de eventos do parceiro |
| `POST` | `/api/partners/events` | Criar evento |
| `PUT` | `/api/partners/events/:id` | Editar evento |
| `DELETE` | `/api/partners/events/:id` | Remover evento |
| `PATCH` | `/api/partners/events/:id/vibe` | Atualizar vibe do evento |
| `PATCH` | `/api/partners/events/:id/feature` | Toggle destaque |
| `GET` | `/api/partners/analytics` | Views e boras por evento (`?days=7\|30\|90`) |
| `POST` | `/api/partners/claim-venue/:id` | Vincular venue ao parceiro |
| `PUT` | `/api/partners/venues/:id` | Atualizar info do venue |
| `POST` | `/api/partners/venues/:id/photo` | Upload de foto (multipart) |

### Admin (`X-Admin-Key` header)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/admin/venues/bulk` | Importação em massa (até 500 venues) |
| `PATCH` | `/api/admin/venues/enrich` | Enriquecer venues (horários, tel, Instagram, foto) |
| `GET` | `/api/admin/venues/stats` | Contadores do banco |

---

## Banco de dados

- **Schema:** gerenciado por `SQLAlchemy create_all()` + DDL manual em `_ensure_indexes()` no `main.py`
- **Migrations:** sem Alembic — novas colunas via `ALTER TABLE` em `_ensure_indexes()` (com try/except idempotente)
- **Neon free tier:** pausa após 5min de inatividade. A primeira query pode demorar 10-30s (normal)
- **Seed automático** no primeiro startup: admin, 16 tags, 7 comunidades

### Principais modelos

| Modelo | Campos chave |
|--------|-------------|
| `User` | id, name, email, hashed_password, role, google_id, reset_token, onboarding_completed |
| `Venue` | id, owner_id, name, city, lat, lng, category, hours (JSON), photo_url, pet_friendly, wheelchair/... |
| `Event` | id, venue_id, title, date, vibe_status, is_featured, category, recurrence, cover_url, view_count |
| `Review` | id, user_id, venue_id, rating (1-5), text — unique (user_id, venue_id) |
| `Notification` | id, user_id, type, title, body, url, read |
| `Coupon` | id, code (unique), discount_pct, venue_id, community_id, max_uses, used_count, active |
| `PushSubscription` | id, user_id, endpoint, p256dh, auth |

---

## Deploy

Push em `main` → GitHub Actions → testes → zip deploy → Azure App Service.

**Fluxo do workflow:**
1. Setup Python 3.11
2. `pip install -r requirements-dev.txt && pytest` — falha aqui = deploy cancelado
3. `pip install -r requirements.txt --target=.python_packages/...` (bundle para Azure)
4. `zip deploy.zip .` (exclui tests, venv, .env)
5. `azure/webapps-deploy@v3`

```bash
# Verificar estado em produção
az webapp show --name bora-floripa-api --resource-group rg-borafloripa --query state

# Ver logs
az webapp log tail --name bora-floripa-api --resource-group rg-borafloripa
```

### Variáveis de ambiente (Azure App Settings)

| Variável | Obrigatório | Notas |
|----------|-------------|-------|
| `DATABASE_URL` | Sim | Connection string Neon |
| `SECRET_KEY` | Sim | 64 chars hex |
| `ADMIN_API_KEY` | Sim | Header X-Admin-Key |
| `ALLOWED_ORIGINS` | Sim | URL do frontend (CSV) |
| `AZURE_STORAGE_CONNECTION_STRING` | Para foto upload | Container `venues` |
| `AZURE_STORAGE_CONTAINER` | Para foto upload | Default: `venues` |
| `GOOGLE_CLIENT_ID` | Não | Login Google |
| `VAPID_PUBLIC_KEY` | Não | Push notifications |
| `VAPID_PRIVATE_KEY` | Não | Push notifications |
| `VAPID_EMAIL` | Não | Push notifications |
| `SENDGRID_API_KEY` | Não | Reset password email |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Sim | Deve ser `true` |

---

## Limites conhecidos (Azure F1 free)

- **60 CPU min/dia** — cada deploy consome ~3-5min. Múltiplos deploys falhos em sequência podem esgotar a cota (app para até meia-noite UTC)
- **Sem always-on** — app "adormece" após 20min sem requisição (cold start de ~5s)
- **Upgrade recomendado:** B1 (~R$70/mês) elimina quota e ativa always-on

```bash
az appservice plan update --name plan-borafloripa --resource-group rg-borafloripa --sku B1
```
