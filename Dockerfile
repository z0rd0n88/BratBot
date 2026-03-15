# ─── Stage 1: Builder ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock* ./

# Export lockfile to requirements.txt and install deps
RUN uv export --format requirements-txt --no-dev > requirements.txt && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy source and install the package itself
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install --no-deps .

# ─── Stage 2: Runtime ────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy alembic config and migrations for running migrations in production
COPY alembic.ini ./
COPY alembic/ alembic/

CMD ["python", "-m", "bratbot"]
