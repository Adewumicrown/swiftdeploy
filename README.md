# SwiftDeploy

> A declarative deployment CLI that generates your entire stack from a single `manifest.yaml`.

```
manifest.yaml  →  swiftdeploy init  →  nginx.conf + docker-compose.yml  →  running stack
```

---

## Architecture

```
  [Client]
     │
     ▼  :8080
 [Nginx container]          ← reverse proxy, access logs, JSON error pages
     │
     ▼  :3000 (internal only, never exposed)
 [API container]            ← Flask app, stable or canary mode
     │
 [app-logs volume]          ← shared log mount
```

Both containers share the `swiftdeploy-net` bridge network.  
The API port is **never** exposed publicly — all traffic routes through Nginx.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker + Docker Compose | ≥ 24.x |
| Python | ≥ 3.10 |
| pip + venv | any recent |

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/swiftdeploy.git
cd swiftdeploy
```

### 2. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install pyyaml jinja2 ruamel.yaml
```

> **Note:** Activate the venv every time you open a new terminal: `source venv/bin/activate`

### 3. Make the CLI executable

```bash
chmod +x swiftdeploy
```

### 4. Build the Docker image

```bash
docker build -t swift-deploy-1-node:latest .
```

Verify image size is under 300MB:

```bash
docker images swift-deploy-1-node:latest
```

---

## Subcommand Walkthrough

### `init` — Generate config files from manifest

Reads `manifest.yaml` and renders:
- `nginx.conf` from `templates/nginx.conf.j2`
- `docker-compose.yml` from `templates/docker-compose.yml.j2`

```bash
./swiftdeploy init
```

Expected output:
```
swiftdeploy init
  ✔ PASS  Generated nginx.conf  (proxy → port 3000, listen 8080)
  ✔ PASS  Generated docker-compose.yml  (mode=stable)
  → Init complete — run './swiftdeploy validate' next
```

> Run `init` any time you edit `manifest.yaml` or after `teardown --clean` deletes the generated files.

---

### `validate` — 5 pre-flight checks

Runs 5 checks before deployment. Exits non-zero if any fail.

```bash
./swiftdeploy validate
```

Expected output:
```
swiftdeploy validate
  ✔ PASS  manifest.yaml exists and is valid YAML
  ✔ PASS  All required fields present and non-empty
  ✔ PASS  Docker image exists locally  (swift-deploy-1-node:latest)
  ✔ PASS  Nginx port not already bound on host  (port 8080 is free or owned by swiftdeploy)
  ✔ PASS  Generated nginx.conf is syntactically valid

All checks passed — ready to deploy!
```

| # | Check | How |
|---|-------|-----|
| 1 | `manifest.yaml` exists and is valid YAML | File exists + PyYAML parse |
| 2 | All required fields present and non-empty | Checks `services`, `nginx`, `network` keys |
| 3 | Docker image exists locally | `docker images -q` |
| 4 | Nginx port not already bound | Socket connect test |
| 5 | `nginx.conf` is syntactically valid | `nginx -t` inside temporary container |

---

### `deploy` — Full stack deployment

Runs `init`, brings up the stack, and blocks until health checks pass or 60s timeout.

```bash
./swiftdeploy deploy
```

Expected output:
```
swiftdeploy deploy
  → Running init…
  ✔ PASS  Generated nginx.conf  (proxy → port 3000, listen 8080)
  ✔ PASS  Generated docker-compose.yml  (mode=stable)
  → Starting stack with docker compose…
  ✔ Container swiftdeploy-api    Healthy
  ✔ Container swiftdeploy-nginx  Started
  → Waiting for service health on port 8080 (timeout 60s)…
  → Health check passed after 1 attempt(s)

✔ Stack is up and healthy!
  API:    http://localhost:8080/
  Health: http://localhost:8080/healthz
```

Test the running stack:

```bash
# Welcome message
curl http://localhost:8080/

# Health check
curl http://localhost:8080/healthz

# Verify headers
curl -I http://localhost:8080/
```

---

### `promote` — Switch deployment mode

Switches between `stable` and `canary` mode with a rolling restart of only the API container. Nginx stays up throughout — zero downtime.

```bash
# Switch to canary
./swiftdeploy promote canary
```

Expected output:
```
swiftdeploy promote canary
  ✔ PASS  manifest.yaml updated  mode: stable → canary
  ✔ PASS  docker-compose.yml regenerated with MODE=canary
  → Restarting API service container only…
  ✔ PASS  API container restarted
  → Confirming new mode via http://localhost:8080/healthz…
  ✔ PASS  Confirmed: service is now running in canary mode

✔ Promote to 'canary' complete!
```

**Canary mode features:**
- Every response includes `X-Mode: canary` header
- `POST /chaos` endpoint is activated

```bash
# Verify canary headers
curl -I http://localhost:8080/

# Test chaos endpoints (canary only)

# Slow responses by N seconds
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode": "slow", "duration": 2}'

# Return 500 on ~50% of requests
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode": "error", "rate": 0.5}'

# Recover to normal
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode": "recover"}'
```

Switch back to stable:

```bash
./swiftdeploy promote stable
```

---

### `teardown` — Remove the stack

```bash
# Stop containers, remove networks and volumes
./swiftdeploy teardown

# Also delete generated config files (nginx.conf + docker-compose.yml)
./swiftdeploy teardown --clean
```

Expected output:
```
swiftdeploy teardown
  → Stopping and removing containers, networks, and volumes…
  ✔ PASS  Stack torn down successfully

✔ Teardown complete
```

> After `teardown --clean`, run `./swiftdeploy init` to regenerate configs from `manifest.yaml`.

---

## API Endpoints

| Method | Path | Description | Mode |
|--------|------|-------------|------|
| GET | `/` | Welcome message with mode, version, timestamp | Both |
| GET | `/healthz` | Liveness check with process uptime in seconds | Both |
| POST | `/chaos` | Simulate degraded behaviour | Canary only |

### Example responses

**GET /**
```json
{
  "message": "Welcome to SwiftDeploy API — running in stable mode",
  "mode": "stable",
  "version": "1.0.0",
  "timestamp": "2026-05-03T22:28:36Z"
}
```

**GET /healthz**
```json
{
  "status": "ok",
  "mode": "stable",
  "uptime": 48.48
}
```

---

## Nginx Features

- Listens on `nginx.port` from manifest (default: 8080)
- Proxy timeouts set from `nginx.proxy_timeout`
- JSON error bodies on 502/503/504
- `X-Deployed-By: swiftdeploy` header on every response
- Forwards `X-Mode` header from upstream in canary mode
- Access logs in format: `$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request`

View nginx access logs:
```bash
docker logs swiftdeploy-nginx
```

---

## manifest.yaml Reference

```yaml
services:
  image: swift-deploy-1-node:latest   # Docker image name
  port: 3000                          # Internal service port
  mode: stable                        # stable | canary (updated by promote)
  version: "1.0.0"                    # Injected as APP_VERSION

nginx:
  image: nginx:latest
  port: 8080                          # Public-facing port
  proxy_timeout: 30                   # Seconds for proxy timeouts

network:
  name: swiftdeploy-net
  driver_type: bridge

restart_policy: unless-stopped

volumes:
  logs: app-logs
```

> `manifest.yaml` is the **only** file you edit manually. All other config files are generated from it.

---

## Project Structure

```
swiftdeploy/
├── manifest.yaml              ← Single source of truth (only file you edit)
├── swiftdeploy                ← CLI tool (Python)
├── Dockerfile                 ← API service image (Alpine, <300MB)
├── app/
│   ├── main.py                ← Flask API service
│   └── requirements.txt
├── templates/
│   ├── nginx.conf.j2          ← Nginx config template
│   └── docker-compose.yml.j2  ← Compose template
└── README.md

Generated files (never edit manually — re-run init instead):
├── nginx.conf                 ← Generated by swiftdeploy init
└── docker-compose.yml         ← Generated by swiftdeploy init
```

---

## Security Features

- Containers run as non-root user (`appuser`)
- Linux capabilities dropped (`cap_drop: ALL`)
- `no-new-privileges` security option enabled
- API port never exposed publicly (internal only)
- Images based on lightweight Alpine (~83MB)

---

## Viewing Logs

```bash
# Nginx access logs
docker logs swiftdeploy-nginx

# API logs
docker logs swiftdeploy-api

# Follow live
docker compose logs -f
```

Nginx access log format:
```
2026-05-03T22:28:36+00:00 | 200 | 0.001s | 172.18.0.2:3000 | GET / HTTP/1.1
```
