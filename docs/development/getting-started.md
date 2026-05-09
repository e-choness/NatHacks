# Getting Started

This guide walks you through setting up the NatHacks Assistive Mirror codebase for development.

**We recommend using Docker Compose** for a quick, consistent setup across all platforms. Local development is also supported if you prefer.

---

## Option 1: Docker Compose (Recommended)

The easiest and most consistent way to set up the entire stack.

### Prerequisites

- **Docker** ([install](https://docs.docker.com/install))
- **Docker Compose** ([install](https://docs.docker.com/compose/install))
- **Git**

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd NatHacks-fork

# Start services (Docker Compose automatically uses .env.example as defaults)
docker compose up
```

That's it! Docker Compose automatically loads default environment values from `.env.example` files.

**Optional: Customize environment variables**

If you want to override defaults (e.g., add your own API keys):

```bash
# Copy .env.example to .env (only if you want custom values)
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp tools/.env.example tools/.env

# Edit the .env files to customize
# - Add GEMINI_API_KEY to backend/.env for AI coaching
# - Add GOOGLE_APPLICATION_CREDENTIALS to backend/.env for enhanced vision
# - Adjust API URLs in frontend/.env if needed (rarely needed)

# Then restart services
docker compose down && docker compose up
```

**Without customization**, just start services:

```bash
docker compose up
```

**Services are now running:**
- **Backend API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **AR Marker Viewer**: http://localhost:8080

#### Verify It's Working

```bash
# Check all services are healthy
docker compose ps

# Test backend health
curl http://localhost:8000/health

# Open frontend in browser
open http://localhost:3000
```

#### Useful Docker Commands

```bash
# View logs for a specific service
docker compose logs -f api      # Backend logs
docker compose logs -f web      # Frontend logs
docker compose logs -f db       # Database logs

# Stop all services
docker compose down

# Stop and remove all volumes (reset database)
docker compose down -v

# Restart a service
docker compose restart api

# Run a one-off command
docker compose run --rm api python -c "print('Hello')"
```

#### Running Tests in Docker

```bash
# Backend tests (pytest)
docker compose run --rm backend-tests

# Frontend tests
docker compose run --rm frontend-tests

# Both tests in parallel
docker compose --profile test up backend-tests frontend-tests
```

#### Development Workflow

Code changes automatically hot-reload without rebuilding:

```bash
# Backend (FastAPI)
# Edit files in backend/ → uvicorn --reload detects changes
# Changes reload automatically

# Frontend (Next.js)
# Edit files in frontend/ → Next.js dev server recompiles
# Changes reload automatically
```

If you modify dependencies (`requirements.txt` or `package.json`):

```bash
# Rebuild the image
docker compose build api     # For backend
docker compose build web     # For frontend

# Then restart
docker compose up api web
```

---

## Option 2: Local Development (Without Docker)

If you prefer to run services locally without Docker.

### Prerequisites

- **OS**: Linux (Ubuntu/Debian), macOS, or Windows via WSL2
- **Node.js**: >= 18.18.0
- **Python**: 3.10 or 3.11
- **Webcam**: (optional, for camera features)
- **Git**

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Run development server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The backend is now running at `http://localhost:8000`

**Note on macOS/Windows**: If you encounter camera permission issues via OpenCV, grant your terminal application camera access in OS privacy settings.

### Frontend Setup

In a new terminal:

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Copy and configure environment
cp .env.example .env.local

# Start development server
npm run dev
```

The frontend is now running at `http://localhost:3000`

### Local Database Setup (Optional)

For local development, you can skip the database setup for basic testing, but some features may be limited.

**Option A: Use Docker just for the database**

```bash
# In the project root, start only database and Redis
docker compose up db redis -d

# Then in backend/.env, set:
DATABASE_URL=postgresql://user:password@localhost:5432/appdb
REDIS_URL=redis://localhost:6379/0
```

**Option B: Install PostgreSQL locally**

```bash
# macOS (brew)
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# Start service and create database
sudo service postgresql start
# createdb -U postgres appdb
```

---

## Configuration

### Environment Variables — Backend

**For Docker Compose**: Docker automatically loads from `backend/.env`

**For Local Development**: Copy and edit `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

**Key variables** (edit these in `backend/.env`):

```env
# Database (optional, pre-configured in Docker)
DATABASE_URL=postgresql://user:password@localhost:5432/appdb
REDIS_URL=redis://localhost:6379/0

# Google Cloud Vision (OPTIONAL)
# Enable fallback detection when MediaPipe isn't confident
# Get credentials: https://cloud.google.com/docs/authentication/getting-started
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Gemini AI Assistant (OPTIONAL BUT RECOMMENDED)
# Enable intelligent coaching feedback
# Get API key: https://ai.google.dev/tutorials/setup
GEMINI_API_KEY=your_gemini_api_key_here

# Vision Pipeline Tuning (Optional)
DETECT_SCALE=0.75              # Frame downscale (0.0-1.0, faster = lower quality)
REDUCE_MOTION=false            # Smooth overlays with frame averaging
ARUCO_STRIDE=2                 # Process every N frames

# Server Settings (Usually don't need to change)
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### Environment Variables — Frontend

**For Docker Compose**: Docker automatically loads from `frontend/.env`

**For Local Development**: Copy and edit `frontend/.env.local`:

```bash
cp frontend/.env.example frontend/.env.local
```

**Variables** (edit if your backend is on a different URL):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_TELEMETRY_DISABLED=1
```

---

## Obtaining API Keys (Optional)

These are optional but recommended for enhanced features:

### Gemini AI API Key

For intelligent coaching with natural language feedback:

1. Go to [Google AI Studio](https://ai.google.dev/tutorials/setup)
2. Click "Get API Key"
3. Copy the key and add to `backend/.env`:
   ```env
   GEMINI_API_KEY=your_key_here
   ```

### Google Cloud Vision

For enhanced object detection fallback:

1. Create a GCP project: https://cloud.google.com/docs/authentication/getting-started
2. Enable Vision API
3. Create a service account and download the JSON key
4. Add to `backend/.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
   ```

---

## Development Tools

### Camera Calibration

If you plan to use physical ArUco markers for positional tracking:

**With Docker**:
```bash
docker compose run --rm api python scripts/calibrate_cam.py
```

**Locally**:
```bash
cd backend
python scripts/calibrate_cam.py
```

Instructions:
1. Print a standard OpenCV checkerboard pattern
2. Hold the checkerboard in front of your camera in various orientations
3. Press keys as instructed (usually 'c' to capture, 'q' to finish)
4. A `camera_matrix.npy` file will be saved to `config/`

### Generate ArUco Markers

**With Docker**:
```bash
docker compose run --rm api python scripts/gen_aruco.py
```

**Locally**:
```bash
cd backend
python scripts/gen_aruco.py
```

### View AR Markers

Once generated, view markers at `http://localhost:8080`

---

## Running Tests

### Backend Tests (pytest)

**With Docker**:
```bash
docker compose run --rm backend-tests
```

**Locally**:
```bash
cd backend
python -m pytest tests/ -v
```

### Frontend Tests

**With Docker**:
```bash
docker compose run --rm frontend-tests
```

**Locally**:
```bash
cd frontend
npm run test
```

---

## Troubleshooting

### Docker: Service Won't Start

```bash
# Check service status and logs
docker compose ps
docker compose logs api

# Verify no port conflicts
lsof -i :8000   # Backend
lsof -i :3000   # Frontend
lsof -i :5432   # Database
```

### Docker: "Connection refused" errors

```bash
# Ensure all services are healthy
docker compose ps

# If database is unhealthy, reset it
docker compose down -v
docker compose up db --wait
```

### Local: ModuleNotFoundError in backend

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Local: Cannot find module in frontend

```bash
# Clear and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Camera Access Issues

**Linux**:
```bash
ls -la /dev/video0
sudo usermod -a -G video $(whoami)
# Log out and back in for changes to take effect
```

**macOS/Windows**: Check privacy settings → camera permissions for your terminal/IDE

### WebSocket Connection Failed

1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `NEXT_PUBLIC_WS_URL` in your `.env` or `.env.local`
3. Inspect browser console for connection errors
4. If using Docker, ensure backend service is healthy: `docker compose ps`

---

## Next Steps

Once everything is running:

1. **Open the frontend**: http://localhost:3000
2. **Grant camera permissions** when prompted
3. **Check diagnostics**: Look for latency, FPS, and pose detection status
4. **Read the architecture guide**: [Architecture Overview](../architecture/overview.md)
5. **Explore the API**: Check [API Documentation](../services/fastapi-server.md)
6. **Run tests**: Follow [Testing Guide](./testing.md)

---

## Getting Help

- Check [Troubleshooting](#troubleshooting) section above
- Review logs: `docker compose logs <service>`
- Read [Docker Guide](./docker-guide.md) for deep Docker knowledge
- Check [Testing Guide](./testing.md) for test-related issues
