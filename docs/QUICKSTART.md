# Quickstart — Sanctum Router

Get the router running in minutes: Docker or local install, then verify with curl and the CLI.

---

## Prerequisites

- **Docker** (for Option A), or **Python 3.10+** (for Option B)
- Three secrets: client key, admin key, and an encryption key for provider API keys stored in the DB (see [PERSISTENCE_AND_SECRETS.md](PERSISTENCE_AND_SECRETS.md) for format)

---

## Option A: Docker (recommended)

### 1. Clone and set environment

```bash
git clone https://github.com/sanctumos/sanctum-router.git
cd sanctum-router
```

Set these before starting the container:

```bash
export ROUTER_CLIENT_KEY=your-client-key
export ROUTER_ADMIN_KEY=your-admin-key
export ROUTER_ENCRYPTION_KEY=your-32-char-encryption-key
```

### 2. Start the router

Router binds to localhost; map ports as `127.0.0.1:8480:8480`. Data is stored in a Docker volume.

```bash
docker compose up --build -d
```

### 3. Check health and proxy

```bash
curl -s http://127.0.0.1:8480/health
# {"status":"ok"}

curl -s -H "Authorization: Bearer $ROUTER_CLIENT_KEY" http://127.0.0.1:8480/v1/models
# {"object":"list","data":[...]}
```

### 4. Add a provider (Config API)

Example: add Venice as a provider (replace `YOUR_VENICE_KEY` with a real key if you have one):

```bash
curl -s -X POST http://127.0.0.1:8480/admin/providers \
  -H "Authorization: Bearer $ROUTER_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "venice",
    "endpoint": "https://api.venice.ai",
    "api_key": "YOUR_VENICE_KEY",
    "models": ["kimi-k2"],
    "priority": 1,
    "supports_tools": true,
    "supports_streaming": true,
    "supports_multimodal": false
  }'
```

### 5. Use the CLI

The CLI talks to the router over HTTP. Set `ROUTER_URL` and use the admin key (the CLI calls `/admin/*`):

```bash
export ROUTER_URL=http://127.0.0.1:8480
router-cli status
router-cli providers list
router-cli routing get
router-cli credit
```

---

## Option B: Local install

### 1. Clone and install

```bash
git clone https://github.com/sanctumos/sanctum-router.git
cd sanctum-router
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Set environment

```bash
export ROUTER_CLIENT_KEY=your-client-key
export ROUTER_ADMIN_KEY=your-admin-key
export ROUTER_ENCRYPTION_KEY=your-32-char-encryption-key
export ROUTER_DB_PATH=./router.db   # or /data/router.db
```

### 3. Run the server

```bash
uvicorn router.main:app --host 127.0.0.1 --port 8480
```

### 4. Same checks as Docker

Use the same `curl` and CLI commands as in Option A, with `ROUTER_URL=http://127.0.0.1:8480`.

---

## Minimal curl reference

| Action | Command |
|--------|---------|
| Health (no auth) | `curl -s http://127.0.0.1:8480/health` |
| List models (proxy) | `curl -s -H "Authorization: Bearer $ROUTER_CLIENT_KEY" http://127.0.0.1:8480/v1/models` |
| Chat completion (proxy) | `curl -s -X POST http://127.0.0.1:8480/v1/chat/completions -H "Authorization: Bearer $ROUTER_CLIENT_KEY" -H "Content-Type: application/json" -d '{"model":"venice+kimi-k2","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}'` |
| Admin status | `curl -s -H "Authorization: Bearer $ROUTER_ADMIN_KEY" http://127.0.0.1:8480/admin/status` |
| List providers (admin) | `curl -s -H "Authorization: Bearer $ROUTER_ADMIN_KEY" http://127.0.0.1:8480/admin/providers` |

---

## CLI commands (overview)

Require `ROUTER_URL` and `ROUTER_ADMIN_KEY`:

| Command | Purpose |
|---------|---------|
| `router-cli status` | Router status and health |
| `router-cli providers list` | List providers |
| `router-cli providers add` | Add provider (interactive or args) |
| `router-cli providers remove <id>` | Remove provider |
| `router-cli routing get` | Get routing config (order, failover) |
| `router-cli routing set` | Set routing config |
| `router-cli override <provider_id>` | Pin session to a provider |
| `router-cli credit` | Credit/balance per provider |

Use `router-cli --help` and `router-cli <command> --help` for options (e.g. `--json` for machine output).

---

## Pointing an agent at the router

For Letta or any OpenAI-speaking client:

1. **Base URL** → `http://127.0.0.1:8480/v1` (or `http://127.0.0.1:8480` depending on client).
2. **API key** → `ROUTER_CLIENT_KEY`.

No code changes beyond that; the router is a drop-in OpenAI-compatible endpoint.

---

## Next steps

- **[OVERVIEW.md](OVERVIEW.md)** — What the router is and how routing works (capabilities, failover, model IDs).
- **[CONTROL_PLANE.md](CONTROL_PLANE.md)** — Config API, CLI, and SMCP plugins.
- **[REFERENCE.md](REFERENCE.md)** — Environment variables, session override, API summary.
