#!/bin/bash
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot/.packages"
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --timeout 120
