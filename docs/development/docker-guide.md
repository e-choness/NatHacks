# Docker Development Guide

This guide explains how to use Docker and Docker Compose for developing, testing, and deploying the NatHacks Assistive Mirror application.

## Overview

The project uses a multi-stage Dockerfile and Docker Compose to:
- **Develop locally** with live code reloading
- **Run tests** in isolated containers
- **Deploy** to production with optimized images

### Key Files

- **`Dockerfile`** — Multi-stage build (backend, frontend, tools, tests)
- **`docker-compose.yml`** — Service orchestration (5 core + 2 test services)
- **Individual Dockerfiles** — `backend/Dockerfile`, `frontend/Dockerfile`, `tools/Dockerfile` (for standalone builds)

---

## Quick Start

```bash
# Start all core services
docker compose up

# Or run in background
docker compose up -d

# View logs
docker compose logs -f
```

Services:
- **api** (backend): `http://localhost:8000`
- **web** (frontend): `http://localhost:3000`
- **db** (PostgreSQL): Internal, port 5432
- **redis**: Internal, port 6379
- **tools** (AR viewer): `http://localhost:8080`

---

## Service Architecture

### Core Services

| Service | Technology | Port | Purpose |
|---------|-----------|------|---------|
| `api` | Python FastAPI | 8000 | Backend server |
| `web` | Node.js Next.js | 3000 | Frontend SPA |
| `db` | PostgreSQL 15 | 5432 (internal) | User data, history |
| `redis` | Redis 7 | 6379 (internal) | Caching, WebSocket queuing |
| `tools` | Nginx | 8080 | AR marker viewer |

### Test Services (Profile: `test`)

| Service | Technology | Purpose |
|---------|-----------|---------|
| `backend-tests` | Python pytest | Run backend unit/integration tests |
| `frontend-tests` | Node.js npm test | Run frontend tests |

---

## Running Services

### All Services (Default)

```bash
docker compose up
```

### Specific Services Only

```bash
# Backend + infrastructure only (no frontend)
docker compose up api db redis

# Frontend development (assuming backend is running separately)
docker compose up web

# Just the database and cache
docker compose up db redis
```

### Running in Detached Mode

```bash
docker compose up -d
docker compose ps
docker compose logs -f api
```

### Stopping Services

```bash
# Stop running services
docker compose stop

# Stop and remove containers
docker compose down

# Stop, remove containers, and delete volumes
docker compose down -v
```

---

## Development Workflow

### Live Code Reloading

Changes in source code automatically reload without rebuilding images:

#### Backend (FastAPI)

Edit any file in `backend/` → Uvicorn detects changes → Server reloads automatically

```bash
docker compose up api

# Edit backend/app.py, changes reload instantly
```

#### Frontend (Next.js)

Edit any file in `frontend/` → Next.js dev server detects changes → Recompiles automatically

```bash
docker compose up web

# Edit frontend/app/page.tsx, changes reload instantly
```

### Modifying Dependencies

If you add packages, update `requirements.txt` or `package.json`:

```bash
# Rebuild the affected image
docker compose build api       # For backend dependencies
docker compose build web       # For frontend dependencies

# Restart the service
docker compose up api web
```

### Running Backend Commands

```bash
# Run a one-off command in the backend container
docker compose run --rm api python -c "print('Hello')"

# Run migrations (if applicable)
docker compose run --rm api python manage.py migrate

# Access Python shell
docker compose run --rm api python
```

### Accessing the Database

```bash
# Connect to PostgreSQL
docker compose exec db psql -U user -d appdb

# Or run queries directly
docker compose run --rm db psql -U user -d appdb -c "SELECT VERSION();"
```

---

## Testing

### Run Tests in Docker

```bash
# Backend tests (pytest)
docker compose run --rm backend-tests

# Frontend tests
docker compose run --rm frontend-tests

# Both tests (using profile)
docker compose --profile test up backend-tests frontend-tests
```

### Run Tests Locally

```bash
# Backend
cd backend
python -m pytest tests/ -v

# Frontend
cd frontend
npm run test
```

### Continuous Testing

```bash
# Backend (watch mode, if supported)
docker compose run --rm api pytest tests/ -v --tb=short -s

# Frontend (watch mode)
docker compose run --rm web npm run test -- --watch
```

---

## Building and Pushing Images

### Build Images

```bash
# Build all services
docker compose build

# Build specific service
docker compose build api
docker compose build web

# Build with custom build args
docker compose build --build-arg PYTHON_VERSION=3.11-slim api
```

### View Built Images

```bash
docker images | grep nathacks
```

### Push to Registry

```bash
# Tag images (example: Docker Hub)
docker tag nathacks-fork_api:latest myregistry/nathacks-api:latest

# Push
docker push myregistry/nathacks-api:latest
docker push myregistry/nathacks-web:latest
```

---

## Debugging

### View Container Logs

```bash
# All services
docker compose logs

# Specific service (follow updates)
docker compose logs -f api
docker compose logs -f web

# Last N lines
docker compose logs --tail=50 api

# With timestamps
docker compose logs --timestamps api
```

### Execute Commands in Running Containers

```bash
# Access backend shell
docker compose exec api sh

# Run command
docker compose exec api ls -la

# Run Python script
docker compose exec api python scripts/calibrate_cam.py
```

### Inspect Container Details

```bash
# Container status
docker compose ps

# View image details
docker inspect $(docker compose ps -q api)

# View container logs
docker logs <container-id>
```

### Network Debugging

```bash
# Check if containers can reach each other
docker compose exec api curl http://db:5432

# View network
docker network ls
docker network inspect nathacks-fork_default
```

---

## Environment Variables

### Dockerfile Build Args

Override in `docker-compose.yml` under `services.<name>.build.args`:

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: backend
      args:
        PYTHON_VERSION: "3.11-slim"
```

### Runtime Environment

Set in `docker-compose.yml` under `services.<name>.environment`:

```yaml
services:
  api:
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/appdb
      - REDIS_URL=redis://redis:6379/0
```

### From `.env` Files

Place in `backend/.env` and `frontend/.env`:

```bash
docker compose --env-file backend/.env up api
```

---

## Database Management

### Reset Database

```bash
# Remove all volumes (clean slate)
docker compose down -v

# Recreate and start fresh
docker compose up db -d
```

### Backup Database

```bash
# Dump to file
docker compose exec db pg_dump -U user -d appdb > backup.sql

# Export to SQL file
docker compose run --rm db pg_dump -U user -d appdb > backup.sql
```

### Restore Database

```bash
docker compose exec -T db psql -U user -d appdb < backup.sql
```

---

## Production Considerations

### Multi-Stage Optimization

The Dockerfile uses multi-stage builds to reduce image size:

```dockerfile
# Development stage (fat, with devtools)
FROM python:3.10-slim AS backend-dev

# Production stage (lean, no devtools)
FROM python:3.10-slim AS backend
```

### Security Best Practices

- **Non-root user**: Backend and frontend run as unprivileged users
- **Health checks**: All services include health checks
- **Minimal dependencies**: Each stage installs only required packages

### Scaling

For production, consider:
- Separate database (managed RDS, etc.)
- Separate cache (managed Redis, etc.)
- Container orchestration (Kubernetes, Docker Swarm)
- Load balancing (Nginx, HAProxy)

---

## Common Issues & Solutions

### Port Already in Use

```bash
# Identify what's using the port
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
```

### Out of Disk Space

```bash
# Clean up Docker resources
docker system prune

# Remove all unused images
docker image prune -a

# Remove all dangling volumes
docker volume prune
```

### Container Won't Start

```bash
# Check logs
docker compose logs api

# Check health status
docker compose ps

# Rebuild image
docker compose build --no-cache api
docker compose up api
```

### Database Won't Initialize

```bash
# Reset database volume
docker compose down -v

# Start just database
docker compose up db

# Check logs
docker compose logs db
```

---

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Multi-stage Builds Guide](https://docs.docker.com/build/building/multi-stage/)
- [Best Practices for Writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
