# NatHacks Assistive Mirror

Raspberry Pi smart mirror that guides morning routines with on-device computer vision and optional Google Cloud Vision assist. Built for <150ms capture→overlay latency while keeping the UX senior-friendly.

## Quick Start (Docker) — Recommended

The recommended way to run the entire application stack is via Docker Compose:

### 1. (Optional) Configure API Keys

Docker Compose automatically uses default environment values from `.env.example` files. To customize:

```bash
# Create custom .env files (optional, only if you want to change defaults)
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp tools/.env.example tools/.env

# Edit to add your API keys (optional but recommended)
# - backend/.env: Add GEMINI_API_KEY for AI coaching
# - backend/.env: Add GOOGLE_APPLICATION_CREDENTIALS for enhanced vision
# - frontend/.env: Adjust API URLs if needed (usually not needed)
```

**For basic usage, you can skip this step.** Docker Compose will use the `.env.example` files automatically.

**To customize**:
- `GEMINI_API_KEY` — Intelligent coaching with Gemini AI (optional)
- `GOOGLE_APPLICATION_CREDENTIALS` — GCP service account for enhanced vision (optional)
- `DETECT_SCALE`, `REDUCE_MOTION`, `ARUCO_STRIDE` — Fine-tune vision pipeline (optional)

See [Configuration](#configuration) section below for full details.

### 2. Start Services

```bash
docker compose up
```

This starts all services:
- **Backend API** (FastAPI) → `http://localhost:8000`
- **Frontend** (Next.js) → `http://localhost:3000`
- **PostgreSQL Database** → internal port 5432
- **Redis Cache** → internal port 6379
- **Tools** (AR Marker Viewer) → `http://localhost:8080`

Check service health:
```bash
docker compose ps
```

### 3. Verify It's Working

```bash
# Check backend health
curl http://localhost:8000/health

# Open frontend in browser
open http://localhost:3000
```

---

## Running Specific Services

```bash
# Only backend
docker compose up api

# Only frontend
docker compose up web

# Backend + database (no frontend)
docker compose up api db redis
```

### Running Tests in Docker

```bash
# Backend tests
docker compose run --rm backend-tests

# Frontend tests
docker compose run --rm frontend-tests

# Both tests in parallel
docker compose --profile test up backend-tests frontend-tests
```

### Stopping Services

```bash
docker compose down          # Stop services
docker compose down -v       # Stop services and remove volumes (reset DB)
```

---

## Local Development (Without Docker) — Optional

If you prefer to run services locally without Docker:

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate      # Windows

pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env to add GEMINI_API_KEY, etc.

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend
npm install

# Copy and configure environment
cp .env.example .env.local
# Edit .env.local if needed

npm run dev
```

Frontend runs at `http://localhost:3000`

---

## Project Structure

```
.
├── backend/                  # FastAPI Server
│   ├── app.py               # Main application
│   ├── vision_pipeline.py   # MediaPipe + OpenCV
│   ├── cloud_vision.py      # Google Cloud Vision
│   ├── task_system.py       # Routine management
│   ├── requirements.txt     # Python dependencies
│   ├── tests/               # Pytest suite
│   ├── .env.example         # Environment template
│   └── Dockerfile           # Standalone image
│
├── frontend/                # Next.js 15 (React + TypeScript)
│   ├── app/                 # App Router pages & layouts
│   ├── components/          # React components
│   ├── lib/                 # External SDK (don't modify)
│   ├── public/              # Static assets
│   ├── styles/              # Global CSS
│   ├── package.json         # Node dependencies
│   ├── .env.example         # Environment template
│   └── Dockerfile           # Standalone image
│
├── tools/                   # Utilities & AR Marker Viewer
│   ├── aruco-viewer/        # Nginx-served marker viewer
│   ├── scripts/             # Python calibration & generation
│   ├── markers/             # Generated ArUco markers
│   ├── .env.example         # Environment template
│   └── Dockerfile           # Standalone image
│
├── docs/                    # Documentation
│   ├── architecture/        # System design
│   ├── development/         # Dev guides (Docker, testing, etc.)
│   ├── services/            # API documentation
│   └── DEPLOYMENT.md        # Deployment guide
│
├── infrastructure/          # Infrastructure & deployment
│   ├── config/              # Configuration files
│   └── mirror/              # MagicMirror module setup
│
├── Dockerfile               # Multi-stage root Dockerfile
├── docker-compose.yml       # Service orchestration
└── README.md                # This file
```

---

## Architecture

- **Backend (FastAPI)**: Real-time computer vision, WebSocket broadcasting, REST API
- **Frontend (React/Next.js)**: TypeScript SPA with camera access, AR overlays, WebSocket client
- **Database (PostgreSQL)**: User data, session history, configuration
- **Cache (Redis)**: Real-time state, message queue
- **Tools**: AR marker viewer for testing ArUco detection

---

## Configuration

### Backend Environment Variables

Create or edit `backend/.env`:

```env
# Database (optional, pre-configured in Docker)
DATABASE_URL=postgresql://user:password@localhost:5432/appdb
REDIS_URL=redis://localhost:6379/0

# Google Cloud Vision (optional but recommended)
# Download key from: https://cloud.google.com/docs/authentication/getting-started
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Gemini AI Assistant (optional but recommended)
# Get API key from: https://ai.google.dev/tutorials/setup
GEMINI_API_KEY=your_gemini_api_key_here

# Vision pipeline tuning (optional)
DETECT_SCALE=0.75          # Frame downscale (0.0-1.0, faster = lower quality)
REDUCE_MOTION=false        # Smooth overlays with frame averaging
ARUCO_STRIDE=2             # Process every N frames

# Server settings
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

For **Docker Compose**, these are pre-configured and database variables are handled automatically. Only add `GEMINI_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, and vision tuning if needed.

### Frontend Environment Variables

Create or edit `frontend/.env.local` (or `frontend/.env` for Docker):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_TELEMETRY_DISABLED=1
```

---

## Key Components

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server with WebSocket and REST endpoints |
| `vision_pipeline.py` | MediaPipe face/hands + OpenCV processing |
| `cloud_vision.py` | Google Cloud Vision client with rate limiting |
| `task_system.py` | Guided routine & step validation |

### Frontend (`frontend/`)

- React 18 + TypeScript
- Next.js 15 App Router
- Tailwind CSS styling
- Camera access via getUserMedia API
- Canvas 2D AR overlays
- WebSocket real-time updates

### Tools (`tools/`)

- **aruco-viewer**: Nginx-served HTML/JS for marker visualization
- **scripts/**: Python utilities for calibration and marker generation

---

## API Endpoints

### REST

- `GET /health` — System status (camera, FPS, pose availability)
- `POST /settings` — Configure vision pipeline parameters
- `POST /overlay` — Send overlay commands to connected clients
- `POST /session/start` — Begin a guided routine session

### WebSocket

- `ws://localhost:8000/ws` — Real-time overlay updates and client communication

---

## Development Workflow

### Camera Calibration (Optional)

If using physical ArUco markers:

```bash
# Docker
docker compose run --rm api python scripts/calibrate_cam.py

# Local
python backend/scripts/calibrate_cam.py
```

Hold a checkerboard in front of your camera. Generated `camera_matrix.npy` saves to `config/`.

### Generate ArUco Markers

```bash
# Docker
docker compose run --rm api python scripts/gen_aruco.py

# Local
python backend/scripts/gen_aruco.py
```

### View AR Markers

Open `http://localhost:8080` to view generated markers.

---

## Testing

### Backend Tests (pytest)

```bash
# Docker
docker compose run --rm backend-tests

# Local
cd backend && python -m pytest tests/ -v
```

### Frontend Tests

```bash
# Docker
docker compose run --rm frontend-tests

# Local
cd frontend && npm run test
```

---

## Troubleshooting

### Service Won't Start

```bash
# View logs
docker compose logs api       # Backend
docker compose logs web       # Frontend
docker compose logs db        # Database
```

### Database Connection Failed

```bash
# Verify database is healthy
docker compose ps

# Reset database
docker compose down -v
docker compose up db
```

### WebSocket Connection Failed

- Verify backend health: `curl http://localhost:8000/health`
- Check `NEXT_PUBLIC_WS_URL` matches backend location
- Check browser console for errors

### Camera Not Accessible

**Linux**: Check `/dev/video0` permissions
```bash
ls -la /dev/video0
sudo usermod -a -G video $(whoami)
```

**macOS/Windows**: Grant terminal camera access in privacy settings

### Port Already in Use

Change ports in `docker-compose.yml` or use environment overrides:
```bash
docker compose -e "WEB_PORT=3001" up
```

---

## Deployment

### Docker-Based Deployment

For any environment with Docker (cloud VMs, Raspberry Pi, etc.):

```bash
git pull origin main
docker compose build
docker compose up -d
```

### Raspberry Pi Deployment

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed Pi setup with systemd auto-start.

### Cloud Deployment

- **Google Cloud Run**: Deploy backend container
- **AWS ECS**: Full stack deployment
- **Vercel**: Deploy frontend Next.js app

See [Deployment Guide](docs/DEPLOYMENT.md) for instructions.

---

## Hardware Requirements

For production deployment:

- **Raspberry Pi 4+** (8GB RAM recommended, 4GB minimum)
- **Camera module** (Pi Camera V2/V3 or USB webcam)
- **Display** (HDMI monitor/TV)
- **Network** (Ethernet or WiFi)
- **Power** (5V 3A+ for Pi 4)

Optional:
- **Google Cloud Vision** credentials for enhanced accuracy
- **Gemini API** key for voice assistant features

---

## Documentation

See `/docs` for detailed guides:

- **[Getting Started](docs/development/getting-started.md)** — Setup in Docker or locally
- **[Docker Guide](docs/development/docker-guide.md)** — Docker & Docker Compose deep dive
- **[Testing](docs/development/testing.md)** — Running tests in Docker or locally
- **[Architecture](docs/architecture/overview.md)** — System design and data flow
- **[Deployment](docs/DEPLOYMENT.md)** — Production deployment on Pi, cloud, etc.

---

## Environment Setup Quick Reference

```bash
# 1. Copy example files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp tools/.env.example tools/.env

# 2. Edit for your setup
# - Add GEMINI_API_KEY to backend/.env (optional)
# - Add GOOGLE_APPLICATION_CREDENTIALS to backend/.env (optional)
# - Adjust API URLs in frontend/.env if needed

# 3. Start with Docker
docker compose up

# 4. Access services
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# Tools: http://localhost:8080
```

---

## License

MIT
