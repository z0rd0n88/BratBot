# ─── Stage 1: Build BratBot (Discord bot) ─────────────────────────────
FROM python:3.12-slim AS bot-builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock* README.md ./

# Export lockfile to requirements.txt and install deps
RUN uv export --format requirements-txt --no-dev --no-hashes --no-emit-project > requirements.txt && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy source and install the package itself
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install --no-deps .

# ─── Stage 2: Build BratBotModel (FastAPI personality API) ────────────
FROM python:3.12-slim AS model-builder

WORKDIR /model
COPY model/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 3: Build SMS Gateway ────────────────────────────────────────
FROM python:3.12-slim AS sms-builder

WORKDIR /sms
COPY sms/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 4: Runtime — all services via supervisord ──────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages — model first, then sms, then bot (bot's lockfile takes precedence)
COPY --from=model-builder /install /usr/local
COPY --from=sms-builder /install /usr/local
COPY --from=bot-builder /install /usr/local

# BratBot files
WORKDIR /app

# BratBotModel files
COPY model/app.py /model/app.py
COPY model/interactions.py /model/interactions.py
COPY model/verify.py /model/verify.py
COPY model/prompts/ /model/prompts/

# SMS Gateway files
COPY sms/app.py /sms/app.py
COPY sms/settings.py /sms/settings.py

# Supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000 8001

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
