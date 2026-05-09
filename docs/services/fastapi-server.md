# FastAPI Server

The `backend/app.py` script serves as the central orchestration layer for the Assistive Mirror, combining traditional REST APIs with a high-throughput WebSocket server.

## Connection Management

Because the mirror relies on real-time feedback (typically 30 FPS), standard HTTP requests carry too much overhead for the AR canvas payloads. The server implements a custom `ConnectionManager`:

```python
class ConnectionManager:
    def __init__(self):
        self._active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def broadcast(self, message: Dict[str, object]) -> None:
        # Pushes stringified JSON payloads to all connected clients
```
The application uses an internal `_message_queue` and an asyncio worker task `_broadcast_worker` to safely pull messages from the computer vision thread pool and push them out over the async WebSocket connections.

## REST Endpoints

While active routines run over WS, configuration and session management use REST endpoints:

- `GET /health`: Returns diagnostic information (`HealthState`) including camera status, lighting, current FPS, and Cloud API circuit-breaker state.
- `POST /settings`: Updates the `SettingsState`. The frontend can toggle specific tracking pipelines (`face`, `hands`, `aruco`) or adjust rate limits.
- `POST /session/start`: Initializes a new user session (`SessionState`) for a specific routine (e.g., morning grooming) and broadcasts the first HUD state.
- `POST /tasks/{task_id}/start`: Manages starting a specific task via the `task_system.py` logic.

## Concurrency Model

FastAPI runs on an asynchronous event loop (uvicorn). However, computer vision operations (especially OpenCV captures and MediaPipe inference) are synchronous and heavily CPU-bound. 
To prevent blocking the async event loop:
1. Vision tasks run in an independent Python `Thread` (`_vision_pipeline`).
2. Data from the vision thread is injected back into the async loop via thread-safe queue operations (`call_soon_threadsafe`).
3. Audio generation (`TTS`) uses a `ThreadPoolExecutor` to shell out to `espeak-ng` or system TTS commands without freezing the server.
