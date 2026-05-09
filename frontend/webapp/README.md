# Assistive Coach Web Application

Production-ready Next.js 15 application with local browser-based computer vision for healthcare assistance.

## Features

✅ **Local Vision Processing**: MediaPipe Hands + FaceMesh + OpenCV.js ArUco in Web Worker  
✅ **AR Overlays**: WebGL2 overlay engine compatible with backend `overlay.set` schema  
✅ **Voice Assistant**: Web Speech API (STT/TTS) with command grammar  
✅ **Gamification**: XP, streaks, badges, encouragement system  
✅ **Accessibility**: AAA contrast, 44px+ touch targets, reduced motion support  
✅ **Optional Backend Bridge**: Sync with FastAPI at http://127.0.0.1:8000

## Quick Start

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build && npm start
```

Visit **http://localhost:3000** for the app.

## Project Structure

```
app/
  (mirror)/page.tsx          # Patient mirror @1080×1920
  (practice)/practice/page.tsx
  (progress)/progress/page.tsx
  (encouragement)/encourage/page.tsx
  (clinician)/clinician/page.tsx
  api/overlay/route.ts       # Local mock endpoint
components/
  camera/CameraFeed.tsx      # getUserMedia + OffscreenCanvas
  overlay/OverlayCanvas.tsx  # WebGL2/Canvas renderer
  voice/VoiceToggle.tsx      # STT/TTS controls
  routine/RoutineRunner.tsx  # Step engine
lib/
  vision/worker.ts           # MediaPipe + OpenCV.js Worker
  overlay/schema.ts          # Type definitions
  state/useSettings.ts       # Zustand store
  api/backend.ts             # Backend bridge
public/
  models/                    # MediaPipe WASM/models
  opencv/                    # OpenCV.js WASM
```

## Configuration

### Camera Calibration

Import JSON calibration via Settings drawer:

```json
{
	"fx": 1380.2,
	"fy": 1375.7,
	"cx": 955.6,
	"cy": 529.1,
	"dist": [-0.12, 0.03, 0, 0]
}
```

### Performance Controls

- **detect_scale** (0.5–1.0): Processing resolution
- **aruco_stride** (1–4): Detection frequency
- **reduce_motion**: Disable animations

### Backend Bridge

Toggle in Settings to sync with FastAPI:

- Health check: `GET /health`
- Settings sync: `POST /settings`
- WebSocket overlays: `ws://127.0.0.1:8000/ws`

## Acceptance Tests

- [ ] Click **Start** on `/mirror` begins routine with overlays
- [ ] HealthPanel shows FPS and detector status
- [ ] Camera calibration import enables ArUco pose (rvec/tvec)
- [ ] Encouragement popups with sound on success
- [ ] XP increases and confetti on session complete
- [ ] Backend bridge badge shows when FastAPI available

## Technology Stack

- **Next.js 15** (App Router) + TypeScript + React 19 RC
- **Tailwind CSS** + shadcn/ui + 21st.dev components
- **Zustand** (state) + TanStack Query (server state)
- **MediaPipe Vision** + OpenCV.js (WASM)
- **Web Speech API** (STT/TTS)
- **idb-keyval** (local storage)

## License

MIT
