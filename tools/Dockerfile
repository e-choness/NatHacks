# ── Stage 1: Python builder (generates aruco markers, runs calibration) ──────
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/
COPY markers/ ./markers/

# ── Stage 2: nginx viewer (serves the AR marker viewer HTML tool) ─────────────
FROM nginx:alpine AS viewer

COPY aruco-viewer/ /usr/share/nginx/html/
COPY markers/ /usr/share/nginx/html/markers/

EXPOSE 80
