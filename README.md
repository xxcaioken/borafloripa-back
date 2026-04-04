# Bora Floripa — Backend

API REST do Bora Floripa. Construída com FastAPI + SQLAlchemy. Roda em Azure App Service (prod) com banco PostgreSQL no Neon.

---

## Stack

- **Python 3.11+**
- **FastAPI 0.135** + Uvicorn / Gunicorn
- **SQLAlchemy 2.0** (ORM)
- **Neon PostgreSQL** (prod) / SQLite (dev fallback automático)
- **JWT** com `python-jose` — tokens de 7 dias
- **Passlib** `sha256_crypt` — **não bcrypt** (conflito de versão)

---

## Rodar localmente

```bash
# 1. Clone e entre no diretório
git clone https://github.com/xxcaioken/borafloripa-back.git
cd borafloripa-back

# 2. Crie e ative o virtualenv
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Crie o arquivo .env
cp .env.example .env            # edite com suas chaves
```

### Variáveis de ambiente

| Variável | Padrão (dev) | Produção |
|----------|-------------|----------|
| `DATABASE_URL` | SQLite automático | `postgresql://...@neon.tech/borafloripa?sslmode=require` |
| `SECRET_KEY` | `bora-floripa-secret-dev-2026` | string hex de 64 chars |
| `ADMIN_API_KEY` | *(sem restrição)* | string hex de 64 chars |
| `ALLOWED_ORIGINS` | `*` | URL do frontend em prod |

> Sem `DATABASE_URL` no `.env`, o banco cai para `sqlite:///./borafloripa.db` automaticamente.

```bash
# 5. Inicie o servidor
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

# Verificar saúde
curl http://localhost:8000/health
# {"status":"ok","db":"connected","version":"1.0.0"}
```

---

## Endpoints

### Públicos / Autenticados

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status da API e banco |
| `POST` | `/api/auth/register` | Cadastro de usuário |
| `POST` | `/api/auth/login` | Login — retorna JWT |
| `GET` | `/api/auth/me` | Perfil do usuário logado |
| `PUT` | `/api/auth/me/preferences` | Atualiza preferências musicais |
| `GET` | `/api/events/feed` | Feed principal (paginado, filtros) |
| `GET` | `/api/events/venues` | Lista de venues |
| `GET` | `/api/events/map` | Venues com coordenadas para o mapa |
| `GET` | `/api/events/featured` | Eventos em destaque |
| `GET` | `/api/events/trending` | Eventos com mais reações |
| `GET` | `/api/events/nearby` | Eventos próximos (lat/lng) |
| `GET` | `/api/events/tourist` | Eventos para turistas |
| `GET` | `/api/events/{id}` | Detalhe do evento |
| `GET` | `/api/events/tags` | Tags / vibes disponíveis |
| `GET` | `/api/search?q=` | Busca global |
| `GET` | `/api/communities` | Comunidades por estilo musical |
| `POST` | `/api/communities/{id}/join` | Entrar numa comunidade |
| `POST` | `/api/bora/{event_id}` | Reação "Bora!" |
| `GET` | `/api/bora/counts` | Contagem de reações |
| `POST` | `/api/checkins` | Check-in num venue |
| `GET` | `/api/checkins/hot` | Venues lotados agora (últimos 60min) |
| `GET` | `/api/saved` | Eventos salvos do usuário |
| `POST` | `/api/saved/{event_id}` | Salvar evento |
| `DELETE` | `/api/saved/{event_id}` | Remover dos salvos |
| `GET` | `/api/follows/venues` | Venues que o usuário segue |
| `POST` | `/api/follows/venues/{id}` | Seguir venue |
| `DELETE` | `/api/follows/venues/{id}` | Deixar de seguir |

### Parceiros (requer JWT de parceiro)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/partners/claim-venue/{id}` | Reivindicar um venue |
| `GET` | `/api/partners/events` | Eventos do parceiro |
| `POST` | `/api/partners/events` | Criar evento |
| `PUT` | `/api/partners/events/{id}` | Editar evento |
| `DELETE` | `/api/partners/events/{id}` | Deletar evento |
| `GET` | `/api/partners/analytics` | Analytics do dashboard |
| `PUT` | `/api/partners/venues/{id}` | Atualizar info do venue |

### Admin (requer header `X-Admin-Key`)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/admin/venues/bulk` | Importação em massa via scraper |
| `PATCH` | `/api/admin/venues/enrich` | Enriquecer venues (tel, horários, Instagram) |
| `GET` | `/api/admin/venues/stats` | Estatísticas do banco |

#### Parâmetros do feed (`GET /api/events/feed`)

| Param | Tipo | Exemplo |
|-------|------|---------|
| `city` | string | `Florianópolis` |
| `neighborhood` | string | `Lagoa da Conceição` |
| `category` | string | `balada`, `bar`, `cultura`, `rua` |
| `tag` | string | `eletrônico`, `sertanejo` |
| `open_now` | bool | `true` |
| `period` | string | `hoje`, `amanha`, `semana` |
| `sort` | string | `popular`, `recent` |
| `limit` | int | `20` |
| `offset` | int | `0` |

---

## Estrutura do projeto

```
borafloripa-back/
├── app/
│   ├── main.py          # entry point, startup, CORS, seed
│   ├── database.py      # engine SQLAlchemy (Neon + SQLite fallback)
│   ├── models.py        # modelos ORM + indexes
│   ├── schemas.py       # schemas Pydantic v2
│   ├── rate_limiter.py  # rate limiting em memória
│   └── routers/
│       ├── auth.py
│       ├── events.py
│       ├── partners.py
│       ├── admin.py
│       ├── communities.py
│       ├── checkins.py
│       ├── bora.py
│       ├── saved.py
│       ├── vibes.py
│       ├── follows.py
│       └── search.py
├── requirements.txt
└── startup.sh           # gunicorn para produção
```

---

## Deploy (produção)

Push em `main` → GitHub Actions executa zip deploy para Azure App Service.

```bash
# Verificar estado do app
az webapp show --name bora-floripa-api --resource-group rg-borafloripa --query state

# Ver variáveis de ambiente no Azure
az webapp config appsettings list --name bora-floripa-api --resource-group rg-borafloripa
```

> **Atenção no Windows (dev):** processos uvicorn podem travar a porta após Ctrl+C.
> ```bash
> netstat -ano | grep ":8000"
> cmd //c "taskkill /F /PID <pid>"
> ```

---

## Banco de dados

- `create_all()` no startup cria tabelas novas automaticamente.
- **Não usa Alembic.** Para adicionar colunas em produção: `ALTER TABLE` manual.
- Neon free tier pausa após 5min de inatividade — a primeira query pode demorar até 30s (normal).
- Seed automático no primeiro startup: usuário admin, 16 tags, 7 comunidades.
  - Admin padrão: `admin@borafloripa.com` / `admin123`
