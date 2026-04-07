FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies into a virtual env using the lockfile
RUN uv sync --frozen --no-dev

FROM python:3.11-slim

WORKDIR /app

# Copy the built venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "beever_atlas.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
