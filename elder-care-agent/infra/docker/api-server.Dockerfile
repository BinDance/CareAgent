FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY packages/agent-core /app/packages/agent-core
COPY apps/api-server /app/apps/api-server
COPY infra/docker/start-api.sh /app/infra/docker/start-api.sh

RUN pip install --upgrade pip \
    && pip install -e /app/packages/agent-core -e /app/apps/api-server

WORKDIR /app/apps/api-server
CMD ["/app/infra/docker/start-api.sh"]
