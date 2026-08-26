FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install uv from official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install runtime and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml (and lockfile if present) and sync dependencies with uv
COPY pyproject.toml /app/
RUN uv sync --all-groups --no-install-project

# Copy entrypoint and start scripts
COPY ./compose/local/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

COPY ./compose/local/django/start /start
RUN sed -i 's/\r$//g' /start && chmod +x /start

# Copy project code
COPY . /app/

ENTRYPOINT ["/entrypoint"]
