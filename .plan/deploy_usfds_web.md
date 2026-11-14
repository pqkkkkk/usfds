# Plan: Add `usfds-web` to `deploy/docker-compose.yml`

## Goal
Allow deploying all USFDS services (`postgres`, `rustfs`, `usfds-server`, `usfds-worker`, `usfds-web`) in one `docker compose up -d --build` command from `deploy/`, with `usfds-web` exposed on port `5173` (`USFDS_WEB_PORT`).

## Steps
1. Create `deploy/nginx.conf` to serve `usfds-web` static build (`try_files $uri $uri/ /index.html;`) and reverse-proxy `/api/` to `http://usfds-server:8000/api/`.
2. Create `deploy/Dockerfile.web` (multi-stage: `node:22-alpine` build -> `nginx:alpine` serve).
3. Add `.dockerignore` at repo root to exclude `node_modules`, `dist`, `release`, `__pycache__`, `.venv`, `.git` from Docker build context.
4. Update `deploy/docker-compose.yml`:
   - Remove `profiles: ["app"]` from `usfds-server` and `usfds-worker`.
   - Add `usfds-web` service built from `deploy/Dockerfile.web`, exposing `${USFDS_WEB_PORT:-5173}:80`, `depends_on: [usfds-server]`.
5. Update `deploy/.env.example` and `deploy/.env` with `USFDS_WEB_PORT=5173` and updated comments.
6. Verify with `docker compose --env-file .env config -q` in `deploy/`.

## Success Criteria
- `docker compose --env-file .env config -q` exits 0 in `deploy/`.
- All 5 services (`postgres`, `rustfs`, `usfds-server`, `usfds-worker`, `usfds-web`) are active in the default compose profile.
- `usfds-web` serves the SPA on host port `5173` and proxies `/api/` to `usfds-server:8000`.

