# Deployment Guide

This guide covers deploying the **NatHacks Assistive Mirror** in various environments, focusing on local development, hardware deployment (Raspberry Pi/Smart Mirror), and production considerations.

## 1. Local Development Environment

For testing and building the application on your personal machine, you will run both the frontend and backend concurrently.

### Prerequisites
- Node.js >= 18.18.0
- Python 3.10+
- Webcam

### Backend (FastAPI)
```bash
cd backend
python -m venv .venv

# Activate Virtual Environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
The backend API and WebSocket server will be available at `localhost:8000`.

### Frontend (Next.js)
In a separate terminal:
```bash
# In the root project directory
npm install
npm run dev
```
The Next.js application will be available at `http://localhost:3000`.

---

## 2. MagicMirror Hardware Deployment (Raspberry Pi)

The primary deployment target is a Raspberry Pi (4B/8GB recommended) driving a two-way mirror display.

### 2.1 Install MagicMirror²
If you haven't already, install the core MagicMirror² platform:
```bash
bash -c "$(curl -sL https://raw.githubusercontent.com/MichMich/MagicMirror/master/installers/raspberry.sh)"
```

### 2.2 Install Assistive Mirror Components
Clone this repository and set up the modules:

```bash
# 1. Build the frontend for MagicMirror embedding
cd frontend
npm install
npm run build:mm

# 2. Setup the MagicMirror module wrapper
cd ../modules/MMM-AssistiveCoach
npm install

# 3. Add to MagicMirror Config
```

Edit your MagicMirror `config/config.js`:
```javascript
{
    module: "MMM-AssistiveCoach",
    position: "fullscreen_above",
    config: {
        wsUrl: "ws://127.0.0.1:8000/ws",
        apiBase: "http://127.0.0.1:8000",
        reduceMotion: false,
        showHints: true
    }
}
```

### 2.3 Run the System
For hardware deployments, you typically run MagicMirror and the backend as systemd services.
- `pm2` is recommended to manage the Node processes.
- Ensure the backend (`uvicorn`) is running before the MagicMirror UI loads.

---

## 3. Production Considerations

If deploying parts of this system (e.g., the Next.js UI or a cloud-synced backend) to the internet:
- **Backend**: Can be containerized via Docker and deployed to Google Cloud Run or AWS ECS. Update `ALLOW_WS_ORIGINS` to accept production frontend domains.
- **Frontend**: The Next.js app can be deployed effortlessly via Vercel.
- **Security**: The current iteration defaults to local processing without strict authentication. Introduce JWT/OAuth middleware (Auth0 or NextAuth) if deploying to a public-facing cloud environment.
- **HTTPS**: Required for accessing `getUserMedia` (camera permissions) on modern browsers when not on `localhost`.
