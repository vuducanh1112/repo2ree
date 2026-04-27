FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
#ENV UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    docker.io \
    gosu \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN useradd --create-home --shell /bin/bash appuser \
    && usermod --append --groups docker appuser \
    && mkdir -p /app/.repo2ree/workspaces /app/.repo2ree/reviews \
    && chown -R appuser:appuser /app

COPY pyproject.toml uv.lock ./
COPY core ./core
COPY api ./api
COPY docker/demo/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh

RUN uv sync --package repo2ree-api --frozen --no-dev

RUN chown -R appuser:appuser /app
RUN chmod +x /usr/local/bin/backend-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/backend-entrypoint.sh"]
CMD ["uv", "run", "--package", "repo2ree-api", "--no-sync", "--frozen", "uvicorn", "repo2ree_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
