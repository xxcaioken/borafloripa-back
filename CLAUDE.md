# CLAUDE.md — borafloripa-back

> Contexto completo para qualquer sessão futura. Leia antes de tocar em código.

---

## Stack

| Tech | Versão | Obs |
|------|--------|-----|
| Python | 3.11 | |
| FastAPI | 0.135+ | |
| SQLAlchemy | 2.x | ORM + `engine.connect()` para DDL |
| Pydantic | v2 | `from_attributes = True` nas schemas |
| PostgreSQL | Neon free tier | Pausa após 5min — `connect_timeout=30` |
| Auth | JWT 7 dias + sha256_crypt | NÃO bcrypt — conflito passlib |
| Deploy | Azure App Service F1 | GitHub Actions zip deploy |

---

## Estrutura

```
app/
├── main.py          ← entry point, _ensure_indexes() com migrations DDL, seed()
├── database.py      ← engine Neon, pool_pre_ping, pool_recycle=300
├── models.py        ← todos os modelos SQLAlchemy + índices compostos
├── schemas.py       ← Pydantic v2 schemas (Input/Output)
└── routers/
    ├── events.py        ← /api/events/* — feed, nearby, trending, tourist, map, tags
    ├── auth.py          ← /api/auth/* — register, login, forgot/reset password, Google
    ├── partners.py      ← /api/partners/* — dashboard, criar/editar evento, analytics
    ├── checkins.py      ← /api/checkins — POST check-in anônimo por venue
    ├── communities.py   ← /api/communities — list, join, leave
    ├── bora.py          ← /api/bora — toggle reação "Bora!" em evento
    ├── saved.py         ← /api/saved — salvar/dessalvar evento
    ├── vibes.py         ← /api/vibes — voto de vibe em venue, tags disponíveis
    ├── follows.py       ← /api/follows — follow/unfollow venue, feed, push/VAPID
    ├── reviews.py       ← /api/reviews — avaliações 1-5 estrelas em venues (novo)
    ├── notifications.py ← /api/notifications — in-app, unread-count, mark-read (novo)
    ├── search.py        ← /api/search?q= — busca global venues+eventos
    └── admin.py         ← /api/admin/* — bulk import, enrich, stats (X-Admin-Key)
```

---

## Modelos (models.py)

| Modelo | Campos chave |
|--------|-------------|
| `User` | id, name, email, hashed_password, role, pref_music, pref_vibes, google_id, reset_token |
| `Venue` | id, owner_id, name, city, lat, lng, address, instagram, whatsapp, hours, category, wheelchair/hearing_loop/visual_aid/adapted_wc/parking |
| `Event` | id, venue_id, title, description, date, vibe_status, is_featured, category, is_temporary, cover_url, price_info, view_count |
| `Tag` | id, name |
| `Checkin` | id, venue_id, created_at |
| `BoraReaction` | id, event_id, session_id |
| `VenueVibeVote` | id, venue_id, tag_name, session_id |
| `Community` | id, tag_name, name, description, discount_code |
| `PushSubscription` | id, user_id, endpoint, p256dh, auth |
| `Review` | id, user_id, venue_id, rating (1-5), text (280), created_at — unique (user_id, venue_id) |
| `Notification` | id, user_id, type, title, body, url, read, created_at |

**Tabelas de associação:** `event_tags`, `community_members`, `user_saved_events`, `user_followed_venues`

---

## Convenções

- **Migrations**: sempre via DDL em `_ensure_indexes()` no `main.py` (sem Alembic)
  - Cada statement tem `try/except` + `conn.rollback()` — idempotente
  - `CREATE TABLE IF NOT EXISTS` para novas tabelas
  - `ALTER TABLE ... ADD COLUMN` para colunas novas
- **Upsert de venues**: lookup por `(name.strip().lower(), city.lower())`
- **Auth admin**: header `X-Admin-Key` via `Depends(_require_admin)` em `admin.py`
- **Rate limiting**: em memória — `/bora` 30/min, `/vibes` 20/min, `/checkins` 5/10min
- **`open_now`**: filtrado em Python após query (JSON de horários), não em SQL
- **Instagram**: sempre salvo como `@slug` via `_clean_instagram()`
- **Categoria**: normalizada via `CATEGORY_MAP` → `{bar, balada, cultura, rua, temporario}`

---

## Endpoints principais

### Events
- `GET /api/events/feed` — params: `today`, `venue_id`, `free`, `neighborhood`, `limit`, `sort`
- `GET /api/events/venues` — params: `category`, `neighborhood`, `q`
- `GET /api/events/venues/:id` — venue com checkin_count
- `GET /api/events/trending` — top eventos por boras
- `GET /api/events/tourist` — params: `date_from`, `date_to`, `period`
- `GET /api/events/map` — venues com eventos para o mapa
- `GET /api/events/:id/stats` — view_count, bora_count, checkin_count

### Auth
- `POST /api/auth/register`, `POST /api/auth/login`
- `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`
- `POST /api/auth/google` — recebe credential GSI, upsert por google_id/email

### Follows / Push
- `GET /api/follows/venues` — venues que o usuário segue
- `POST /api/follows/venues/:id`, `DELETE /api/follows/venues/:id`
- `GET /api/follows/venues/feed` — próximos eventos dos venues seguidos
- `GET /api/follows/vapid-key`
- `POST /api/follows/push-subscription`, `DELETE /api/follows/push-subscription`

### Reviews (novo — 2026-04-05)
- `GET /api/reviews/venues/:id` — lista reviews, ordem desc, limit 20
- `POST /api/reviews/venues/:id` — upsert (1 por usuário/venue), rating 1-5
- `GET /api/reviews/venues/:id/summary` — `{count, avg, distribution}`

### Notifications (novo — 2026-04-05)
- `GET /api/notifications` — últimas 20 do usuário logado
- `GET /api/notifications/unread-count` — `{count}`
- `POST /api/notifications/read-all` — marca todas lidas (204)
- `POST /api/notifications/:id/read` — marca uma lida (204)
- Helper interno: `create_notification(db, user_id, type, title, body, url)`
  - Chamado por `notify_venue_followers()` em `follows.py`

---

## notify_venue_followers (follows.py)

Chama sempre que um evento é criado para um venue com seguidores.
- Cria `Notification` in-app para cada seguidor (independente de VAPID)
- Envia push via pywebpush **só se** `VAPID_PRIVATE_KEY` está configurado

---

## Variáveis de ambiente (Azure App Settings)

| Var | Obrigatório | Obs |
|-----|-------------|-----|
| `DATABASE_URL` | Sim | Neon PostgreSQL connection string |
| `SECRET_KEY` | Sim | 64 chars hex, JWT signing |
| `ALLOWED_ORIGINS` | Sim | URL do frontend (CSV) |
| `ADMIN_API_KEY` | Sim | X-Admin-Key para rotas admin |
| `GOOGLE_CLIENT_ID` | Não | Login Google |
| `VAPID_PUBLIC_KEY` | Não | Push notifications |
| `VAPID_PRIVATE_KEY` | Não | Push notifications |
| `VAPID_EMAIL` | Não | Push notifications |
| `SENDGRID_API_KEY` | Não | Reset password email |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Sim | `true` |

---

## Banco (Neon PostgreSQL)

- Pausa após **5min de inatividade** no free tier
- `database.py`: `connect_timeout=30`, `pool_pre_ping=True`, `pool_recycle=300`
- `create_all()` **não migra colunas existentes** — usar DDL manual em `_ensure_indexes()`
- Para inspecionar: `psql $DATABASE_URL` ou Neon dashboard

### Estado atual (2026-04-05)
```
venues:      127  (87 com endereço, 74 com telefone, 0 com horários — reexecutar scraper)
events:      0    (criar via PartnerDashboard ou seed_events.py)
users:       1    (admin)
reviews:     0    (nova tabela)
notifications: 0  (nova tabela)
```

---

## Deploy

- **Push em `main`** → GitHub Actions → `az webapp deployment source config-zip`
- Service Principal: `sp-borafloripa` (clientId: `d7eb540a-4094-4f6e-911a-b1be4a204890`)
- Verificar estado: `az webapp show --name bora-floripa-api --resource-group rg-borafloripa --query state`
- **F1 quota**: 60 CPU min/dia. Deploy falho = 11min. Múltiplos falhos = `QuotaExceeded` até meia-noite UTC.
- **Recomendação**: upgrade para B1 (`az appservice plan update --name plan-borafloripa --resource-group rg-borafloripa --sku B1`)

---

## Histórico de sessões

### Sessão 1 (2026-04-03)
- Bulk import de venues via `POST /api/admin/venues/bulk`
- Fix Neon cold start (connect_timeout, pool_pre_ping)
- Neighborhood filter + sort por checkin_count
- Hot zones (checkins reais)

### Sessão 2 (2026-04-03)
- Password reset via email (SendGrid)
- Login com Google (`POST /api/auth/google`)
- Follow venues + push notifications (pywebpush)
- Param `free=true` no feed de eventos

### Sessão 3 (2026-04-05) — atual
- `Review` model + `reviews.py` router
- `Notification` model + `notifications.py` router
- `notify_venue_followers` agora cria notificações in-app antes de tentar push
- Migrations DDL em `_ensure_indexes()` para ambas as tabelas

---

## Próximos passos recomendados

1. **Ativar push**: gerar VAPID keys, colocar no Azure
2. **Ativar Google login**: criar OAuth client no GCP
3. **Form de evento no PartnerDashboard**: back já tem POST/PUT/DELETE em `/api/partners/events`
4. **Eventos recorrentes**: campo `recurrence VARCHAR` no Event, endpoint gera instâncias semanais
5. **Reexecutar scraper**: 0/127 venues com horários — rodar em dia útil
