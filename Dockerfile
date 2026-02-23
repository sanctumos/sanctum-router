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

# Entrypoint runs router.main so config (admin_bind_localhost_only, port) is applied.
CMD ["python", "-m", "router.main"]
