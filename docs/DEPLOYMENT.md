# Deployment Guide
## The Longevity Alchemist

This guide covers three deployment paths:
- Build and run as a Docker container locally
- Run on a self-hosted Docker server with Portainer
- Deploy the container to Render

---

# 1. Runtime Requirements

- Python app entrypoint: `app.main:app`
- HTTP port inside container: `8888`
- Persistent SQLite path: `/var/data/longevity.db`
- Required env var: `SECRET_KEY`
- Optional default-provider env vars:
  - `OPENAI_API_KEY`
  - `GEMINI_API_KEY`
  - `DEFAULT_AI_PROVIDER`
  - `DEFAULT_REASONING_MODEL`
  - `DEFAULT_DEEP_THINKER_MODEL`
  - `DEFAULT_UTILITY_MODEL`

Note:
- The app supports per-user BYOK AI keys in Settings.
- If you do not set global provider keys, users can still configure their own.

---

# 2. Create Container Files (If Missing)

If your repo does not yet include a `Dockerfile`, create one at repo root:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8888

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
```

Recommended `.dockerignore` at repo root:

```gitignore
.git
.gitignore
.venv
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
tests/
docs/temp.text
```

---

# 3. Build And Run Locally (Docker)

Build image:

```bash
docker build -t longevity:latest .
```

Run container with persistent SQLite volume:

```bash
docker run -d \
  --name longevity \
  -p 8888:8888 \
  -e SECRET_KEY="replace-with-strong-secret" \
  -e DB_PATH="/var/data/longevity.db" \
  -v longevity_data:/var/data \
  longevity:latest
```

Health check:

```bash
curl http://localhost:8888/health
```

Expected:

```json
{"status":"ok"}
```

---

# 3.1 Build And Run On A Remote Docker Server (SSH)

If your Docker daemon is on a separate Linux host, run build/deploy directly there.

## Option A: Build directly on remote host

1. SSH to your Docker server:

```bash
ssh <user>@<docker-server-ip>
```

2. Clone/update repo:

```bash
git clone https://github.com/<org>/<repo>.git
cd <repo>
git pull
```

3. Build image on remote host:

```bash
docker build -t longevity:latest .
```

4. Run container on remote host:

```bash
docker run -d \
  --name longevity \
  -p 8888:8888 \
  -e SECRET_KEY="replace-with-strong-secret" \
  -e DB_PATH="/var/data/longevity.db" \
  -v /opt/longevity/data:/var/data \
  --restart unless-stopped \
  longevity:latest
```

5. Verify from your local machine:

```bash
curl http://<docker-server-ip>:8888/health
```

## Option B: Build locally, run remotely

If you already pushed an image to a registry:

```bash
ssh <user>@<docker-server-ip>
docker pull <registry-user>/longevity:latest
docker run -d \
  --name longevity \
  -p 8888:8888 \
  -e SECRET_KEY="replace-with-strong-secret" \
  -e DB_PATH="/var/data/longevity.db" \
  -v /opt/longevity/data:/var/data \
  --restart unless-stopped \
  <registry-user>/longevity:latest
```

---

# 4. Self-Hosted With Portainer

## 4.1 Push Image (Recommended)

Push your built image to a registry your server can pull from (Docker Hub, GHCR, private registry).

Example:

```bash
docker tag longevity:latest <registry-user>/longevity:latest
docker push <registry-user>/longevity:latest
```

## 4.2 Deploy As Portainer Stack

In Portainer:
- Go to `Stacks`
- Click `Add stack`
- Name: `longevity`
- Paste this stack file:

```yaml
version: "3.8"

services:
  longevity:
    image: <registry-user>/longevity:latest
    container_name: longevity
    restart: unless-stopped
    ports:
      - "8888:8888"
    environment:
      SECRET_KEY: "replace-with-strong-secret"
      DB_PATH: "/var/data/longevity.db"
    volumes:
      - longevity_data:/var/data

volumes:
  longevity_data:
```

Then click `Deploy the stack`.

## 4.3 Update In Portainer

For new versions:
- Push a new image tag
- In Portainer Stack, update image tag
- Redeploy stack

---

# 5. Deploy To Render

Use Render Web Service with Docker runtime.

## 5.1 Repository Setup

Ensure repo contains:
- `Dockerfile` at root

Optional `render.yaml` blueprint:

```yaml
services:
  - type: web
    name: longevity
    env: docker
    plan: starter
    autoDeploy: true
    disk:
      name: longevity-data
      mountPath: /var/data
      sizeGB: 5
    envVars:
      - key: SECRET_KEY
        sync: false
      - key: DB_PATH
        value: /var/data/longevity.db
      - key: PORT
        value: "8888"
```

## 5.2 Render Dashboard Steps

1. Create `Web Service` from your GitHub repo.
2. Runtime: `Docker`.
3. Add persistent disk:
   - Mount path: `/var/data`
4. Set environment variables:
   - `SECRET_KEY`
   - `DB_PATH=/var/data/longevity.db`
   - `PORT=8888`
5. Deploy.

## 5.3 Verify

- Open `https://<your-service>.onrender.com/health`
- Expect: `{"status":"ok"}`

---

# 6. Security Notes

- Never commit real API keys or secrets.
- Use a strong random `SECRET_KEY`.
- Keep all LLM calls server-side only.
- Persist DB only on mounted storage (`/var/data`).

---

# 7. Troubleshooting

## App starts but data disappears
- Cause: no persistent volume/disk mounted to `/var/data`
- Fix: add Docker volume (local/server) or Render disk and set `DB_PATH` correctly

## `Invalid credentials` after deploy
- Likely wrong password/user in your DB; reset test users or run your user reset script

## AI calls fail in chat
- Check user AI config in Settings (provider, key, 3 model slots)
- Verify key validity and provider model availability
- Confirm outbound network access from host
