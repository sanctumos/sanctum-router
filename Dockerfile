# Sanctum Router — single container. PRD §7 Architecture.
# Python slim; no MCP server in image. ROUTER_DB_PATH=/data/router.db; volume /data.

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .

COPY router/ ./router/
COPY plugins/ ./plugins/

ENV ROUTER_DB_PATH=/data/router.db
EXPOSE 8480

# Single entrypoint: bind 127.0.0.1 by default; use Docker port mapping for host.
CMD ["python", "-m", "uvicorn", "router.main:app", "--host", "127.0.0.1", "--port", "8480"]
