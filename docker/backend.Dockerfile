FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Phase 12: run pending migrations before the server starts - app.main's
# lifespan no longer does Base.metadata.create_all (docs/MASTER_PLAN.md
# #2.5), so a fresh/updated database needs `alembic upgrade head` applied
# somewhere; here is the one place that always runs before the app does,
# in every environment that uses this image.
#
# Shell form (not exec-form CMD) so $PORT is actually expanded - most
# PaaS free tiers (Render, Railway, etc.) inject a $PORT env var and
# expect the app to bind to it, which is not always 8000. Falls back to
# 8000 for local `docker compose` use, where docker-compose.yml maps
# 8000:8000 explicitly and no $PORT is set.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
