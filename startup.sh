#!/bin/bash
# startup.sh — Bora Floripa API (Azure App Service F1)
#
# F1 limits: 1 vCPU shared, 1 GB RAM, 60 CPU-min/day
# Strategy:
#   - 1 worker only (F1 is single-core)
#   - --preload: loads app ONCE before forking — saves memory and avoids
#     duplicate DB connections on cold start
#   - --timeout 120: allows Neon PostgreSQL ~30s cold-start + margin
#   - --graceful-timeout 30: fast restart on deploy without dropped requests
#   - --keep-alive 5: reuses connections (Azure load balancer friendly)

exec gunicorn app.main:app \
  --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --preload \
  --access-logfile - \
  --error-logfile -
