# ============================================================================
# NatHacks-fork  -  Multi-Stage Dockerfile (root)
#
# Build from root:   docker compose build
#                   docker compose build <service>
#
# Each service targets its named stage below.
# Override version ARGs via compose build args or --build-arg.
# Per-service Dockerfiles in backend/frontend/tools/ kept for standalone builds.
# ============================================================================

# ── Global build ARGs (must precede first FROM) ───────────────────────────────

ARG PYTHON_VERSION=3.10-slim
ARG NODE_VERSION=18-alpine
ARG NGINX_VERSION=alpine

# ── Backend ───────────────────────────────────────────────────────────────────

FROM python:${PYTHON_VERSION} AS backend-base

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


# ── backend-tests  (docker compose --profile test run backend-tests) ──────────
FROM backend-base AS backend-tests

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest httpx

COPY backend/ .
CMD ["sh", "-c", "PYTHONPATH=/app pytest tests/ -v"]


# ── backend / api  (production) ──────────────────────────────────────────────
FROM backend-base AS backend

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


# ── Frontend ──────────────────────────────────────────────────────────────────

FROM node:${NODE_VERSION} AS frontend-deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci


# ── frontend-builder  (Next.js standalone output) ─────────────────────────────
FROM node:${NODE_VERSION} AS frontend-builder

WORKDIR /app
COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build


# ── frontend-tests  (docker compose --profile test run frontend-tests) ────────
FROM node:${NODE_VERSION} AS frontend-tests

WORKDIR /app
COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ .

ENV NEXT_TELEMETRY_DISABLED=1
CMD ["npm", "run", "test"]


# ── frontend / web  (production) ──────────────────────────────────────────────
FROM node:${NODE_VERSION} AS frontend

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=frontend-builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=frontend-builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=frontend-builder /app/public ./public

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]


# ── Tools ─────────────────────────────────────────────────────────────────────

FROM python:${PYTHON_VERSION} AS tools-builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY tools/scripts/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY tools/scripts/ ./scripts/
COPY tools/markers/ ./markers/


# ── tools / viewer  (nginx serving aruco-viewer) ──────────────────────────────

FROM nginx:${NGINX_VERSION} AS tools

COPY tools/aruco-viewer/ /usr/share/nginx/html/
COPY tools/markers/ /usr/share/nginx/html/markers/

EXPOSE 80
