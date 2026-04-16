FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY packages/agent-core /app/packages/agent-core
COPY apps/api-server /app/apps/api-server
COPY apps/mcp-server /app/apps/mcp-server

RUN pip install --upgrade pip \
    && pip install -e /app/packages/agent-core -e /app/apps/api-server -e /app/apps/mcp-server

WORKDIR /app/apps/mcp-server
CMD ["python", "-m", "eldercare_mcp.main"]
