#!/bin/bash
# Azure App Service startup script para Python FastAPI
# Configurar no portal: Settings > Configuration > Startup Command
# Valor: bash startup.sh

pip install -r requirements.txt
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --timeout 120
