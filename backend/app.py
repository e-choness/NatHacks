import asyncio
import base64
import contextlib
import importlib.util
import json
import logging
import os
import platform
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, validator

import cv2
from pathlib import Path

# Import task system
from task_system import (
    get_all_tasks,
    start_task,
    TaskSession,
    TaskState,
    TASKS
)
from voice_pipeline import VoiceAssistant, build_voice_assistant_from_env

LOGGER = logging.getLogger("assistivecoach.backend")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
)

# --- OpenCV perf knobs (early, process-wide) ---
try:
    cv2.useOptimized()
except Exception as exc:
    logging.debug("OpenCV optimizations unavailable: %s", exc)
try:
    cv2.setNumThreads(1)
except Exception as exc:
    logging.debug("OpenCV setNumThreads unavailable: %s", exc)
# -----------------------------------------------

# --- WS origin policy (dev-friendly) ---
# Default "*" allows all origins for development. 
# For production, set ALLOW_WS_ORIGINS env var to comma-separated list of allowed domains.
# Example: ALLOW_WS_ORIGINS="https://yourdomain.com,https://mirror.local"
_WS_ALLOWED = os.getenv("ALLOW_WS_ORIGINS", "*").split(",")

def _ws_origin_ok(origin: Optional[str]) -> bool:
    # Browsers may omit Origin for file://; allow in dev.
    if not origin or origin == "null" or origin.startswith("file://"):
        return True
    if "*" in _WS_ALLOWED:
        return True
    # Always allow localhost patterns for dev convenience
    if any(origin.startswith(p) for p in (
        "http://localhost", "https://localhost",
        "http://127.0.0.1", "https://127.0.0.1"
    )):
        return True
    return any(origin.startswith(p) for p in _WS_ALLOWED)
# ---------------------------------------

app = FastAPI(title="Assistive Coach Backend", version="0.1.0")

ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Anchor(BaseModel):
    landmark: Optional[str] = None
    aruco_id: Optional[int] = Field(default=None, ge=0)
    pixel: Optional[Dict[str, float]] = None

    @validator("pixel")
    def validate_pixel(cls, value: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if value is None:
            return value
        if not {"x", "y"}.issubset(value.keys()):
            raise ValueError("pixel anchor must include x and y")
        return value

    @validator("landmark")
    def validate_landmark(cls, value: Optional[str], values: Dict[str, object]) -> Optional[str]:
        if value and values.get("aruco_id") is not None:
            raise ValueError("Anchor cannot define both landmark and aruco_id")
        return value


class Shape(BaseModel):
    kind: str
    anchor: Anchor
    to: Optional[Anchor] = None
    radius_px: Optional[int] = Field(default=None, ge=0)
    accent: Optional[str] = None
    text: Optional[str] = None

    @validator("kind")
    def validate_kind(cls, value: str) -> str:
        allowed = {"ring", "arrow", "badge"}
        if value not in allowed:
            raise ValueError(f"Shape kind must be one of {sorted(allowed)}")
        return value

    @validator("to")
    def validate_to(cls, value: Optional[Anchor], values: Dict[str, object]) -> Optional[Anchor]:
        if values.get("kind") == "arrow" and value is None:
            raise ValueError("Arrow shapes require a 'to' anchor")
        return value


class HUDPayload(BaseModel):
    title: Optional[str] = None
    step: Optional[str] = None
    subtitle: Optional[str] = None
    time_left_s: Optional[int] = Field(default=None, ge=0)
    hint: Optional[str] = None
    instruction: Optional[str] = None
    max_time_s: Optional[int] = Field(default=None, ge=0)
    progress: Optional[float] = None
    coach_tip: Optional[str] = None


class OverlayMessage(BaseModel):
    type: str
    hud: Optional[HUDPayload] = None
    camera: Optional[str] = None
    lighting: Optional[str] = None
    fps: Optional[float] = None
    ar_overlays: Optional[bool] = None
    detectors: Optional[Dict[str, bool]] = None
    text: Optional[str] = None
    level: Optional[str] = None
    reason: Optional[str] = None

    @validator("type")
    def validate_type(cls, value: str) -> str:
        allowed = {"overlay.set", "status", "tts", "safety.alert"}
        if value not in allowed:
            raise ValueError(f"Unsupported message type: {value}")
        return value


class OverlayRequest(BaseModel):
    message: OverlayMessage


class TTSRequest(BaseModel):
    text: str

    @validator("text")
    def validate_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Text cannot be empty")
        return trimmed


class VoiceResponse(BaseModel):
    transcript: Optional[str]
    response_text: Optional[str]
    audio_b64: Optional[str] = None


class SessionRequest(BaseModel):
    patient_id: Optional[str]
    routine_id: Optional[str]


class SettingsPayload(BaseModel):
    use_cloud: Optional[bool] = None
    face: Optional[bool] = None
    hands: Optional[bool] = None
    aruco: Optional[bool] = None
    cloud_rps: Optional[int] = Field(default=None, ge=1, le=10)
    cloud_timeout_s: Optional[float] = Field(default=None, ge=0.1, le=3.0)
    cloud_min_interval_ms: Optional[int] = Field(default=None, ge=0)


class HealthState(BaseModel):
    camera: str = "off"
    lighting: str = "unknown"
    fps: float = 0.0
    latency_ms: float = 0.0
    last_frame_ns: Optional[int] = None
    cloud_enabled: bool = False
    cloud_ok_count: int = 0
    cloud_fail_count: int = 0
    cloud_breaker_open: bool = False
    cloud_latency_ms: float = 0.0
    cloud_last_ok_ns: Optional[int] = None
    # Hotfix additions
    mock_camera: bool = False
    camera_error: Optional[str] = None


class HealthResponse(BaseModel):
    camera: str
    lighting: str
    fps: float
    latency_ms: float
    vision_state: Optional[Dict[str, Any]] = None
    cloud: Optional[Dict[str, Any]] = None


class SettingsState(BaseModel):
    use_cloud: bool = False
    face: bool = True
    hands: bool = True
    aruco: bool = False
    cloud_rps: int = 2
    cloud_timeout_s: float = 0.8
    cloud_min_interval_ms: int = 600
    aruco_stride: int = 2
    detect_scale: float = 0.75
    reduce_motion: bool = False


class SessionState(BaseModel):
    patient_id: Optional[str] = None
    routine_id: Optional[str] = None
    started_at: Optional[datetime] = None
    step_index: int = 0


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._active_connections.append(websocket)
        LOGGER.info("WebSocket client connected. active=%d", len(self._active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._active_connections:
                self._active_connections.remove(websocket)
        LOGGER.info("WebSocket client disconnected. active=%d", len(self._active_connections))

    async def broadcast(self, message: Dict[str, object]) -> None:
        payload = json.dumps(message)
        async with self._lock:
            websockets = list(self._active_connections)
        for connection in websockets:
            try:
                await connection.send_text(payload)
            except Exception as exc:  # pragma: no cover - defensive log
                LOGGER.warning("Failed to send WS message: %s", exc)


settings_state = SettingsState()
health_state = HealthState()
session_state = SessionState()
active_task_session: Optional[TaskSession] = None  # Current active task
manager = ConnectionManager()
_executor = ThreadPoolExecutor(max_workers=4)
_preview_buffer: Optional[bytes] = None
_preview_lock = Lock()
_message_queue: Optional["asyncio.Queue[Dict[str, object]]"] = None
_broadcast_task: Optional[asyncio.Task] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_voice_assistant: Optional[VoiceAssistant] = None


async def _broadcast_worker() -> None:
    global _message_queue
    if _message_queue is None:
        LOGGER.warning("Broadcast queue not initialised; worker exiting")
        return
    LOGGER.info("Broadcast worker started")
    while True:
        message = await _message_queue.get()
        try:
            await manager.broadcast(message)
        finally:
            _message_queue.task_done()


def queue_broadcast(message: Dict[str, object]) -> None:
    global _message_queue, _event_loop
    if _message_queue is None:
        LOGGER.warning("Broadcast queue not ready; dropping message")
        return
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop is _event_loop:
        try:
            _message_queue.put_nowait(message)
        except asyncio.QueueFull:  # pragma: no cover - defensive log
            LOGGER.warning("Broadcast queue full; dropping message")
        return

    if _event_loop is None:
        LOGGER.warning("Broadcast loop not ready; dropping message")
        return

    def _enqueue() -> None:
        if _message_queue is None:
            return
        if _message_queue.full():  # pragma: no cover - overflow guard
            LOGGER.warning("Broadcast queue full; dropping message")
            return
        _message_queue.put_nowait(message)

    _event_loop.call_soon_threadsafe(_enqueue)


async def broadcast(message: Dict[str, object]) -> None:
    queue_broadcast(message)


def set_preview_frame(jpeg_bytes: bytes) -> None:
    global _preview_buffer
    with _preview_lock:
        _preview_buffer = jpeg_bytes


async def get_preview_frame() -> Optional[bytes]:
    global _preview_buffer
    with _preview_lock:
        return _preview_buffer


@lru_cache
def _detect_speech_engine() -> str:
    if shutil and shutil.which("espeak-ng"):
        return "espeak-ng"
    if importlib.util.find_spec("pyttsx3") is not None:
        return "pyttsx3"
    return ""


try:
    import shutil
except ImportError:  # pragma: no cover
    shutil = None  # type: ignore


_speech_engine = _detect_speech_engine()


def _speak_espeak(text: str) -> None:
    try:
        subprocess.run(
            [_speech_engine, text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        LOGGER.error("espeak-ng failed: %s", exc)
        raise


def _speak_pyttsx(text: str) -> None:
    try:
        import pyttsx3  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - optional dependency
        LOGGER.error("pyttsx3 unavailable: %s", exc)
        return

    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


def _speak_system(text: str) -> bool:
    """Platform-aware TTS; returns True if spoken, False otherwise."""
    try:
        import shutil as _sh
    except ImportError:
        _sh = None  # type: ignore
    sysname = platform.system()
    if sysname == "Darwin":
        try:
            subprocess.run(["say", text], check=True)
            return True
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("macOS say failed: %s", exc)
            return False
    if sysname == "Linux" and _sh and _sh.which("espeak-ng"):
        try:
            subprocess.run(["espeak-ng", text], check=True)
            return True
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("espeak-ng failed: %s", exc)
            return False
    return False


def speak_text(text: str) -> None:
    # Try system first
    if _speak_system(text):
        return
    # Fallback chain
    if _speech_engine == "pyttsx3":
        try:
            _speak_pyttsx(text)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("pyttsx3 fallback failed: %s", exc)
    elif _speech_engine:
        try:
            _speak_espeak(text)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("espeak-ng fallback failed: %s", exc)
    else:
        LOGGER.warning("No TTS engine available; skipping")


@app.on_event("startup")
async def _init_voice_assistant() -> None:
    global _voice_assistant
    try:
        _voice_assistant = build_voice_assistant_from_env()
    except Exception as exc:  # pragma: no cover - defensive log
        LOGGER.warning("Failed to initialise VoiceAssistant: %s", exc)
        _voice_assistant = None


@app.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    vision_state = None
    if _vision_pipeline:
        vision_state = {
            "fps": health_state.fps,
            "latency_ms": health_state.latency_ms,
            "last_frame_ns": health_state.last_frame_ns,
        }
    cloud_state = None
    if health_state.cloud_enabled or health_state.cloud_latency_ms > 0:
        cloud_state = {
            "enabled": health_state.cloud_enabled,
            "latency_ms": health_state.cloud_latency_ms,
            "ok_count": health_state.cloud_ok_count,
            "fail_count": health_state.cloud_fail_count,
            "breaker_open": health_state.cloud_breaker_open,
            "last_ok_ns": health_state.cloud_last_ok_ns,
        }

    return HealthResponse(
        camera=health_state.camera,
        lighting=health_state.lighting,
        fps=health_state.fps,
        latency_ms=health_state.latency_ms,
        vision_state=vision_state,
        cloud=cloud_state,
    )


@app.post("/session/start")
async def start_session(payload: SessionRequest) -> JSONResponse:
    session_state.patient_id = payload.patient_id
    session_state.routine_id = payload.routine_id
    session_state.started_at = datetime.utcnow()
    session_state.step_index = 0
    LOGGER.info("Session started: %s", session_state.dict())
    
    # Send initial status
    await broadcast(
        {
            "type": "status",
            "camera": health_state.camera,
            "lighting": health_state.lighting,
            "fps": health_state.fps,
        }
    )
    
    # Immediately push Step 1 HUD (vision pipeline will add shapes on next frame)
    if _vision_pipeline and payload.routine_id:
        try:
            # Load routine to get first step
            from pathlib import Path
            import json
            tasks_path = Path(__file__).resolve().parents[1] / "config" / "tasks.json"
            if tasks_path.exists():
                with tasks_path.open("r") as f:
                    tasks = json.load(f)
                    routine_steps = tasks.get(payload.routine_id, [])
                    if routine_steps and len(routine_steps) > 0:
                        step = routine_steps[0]
                        await broadcast({
                            "type": "overlay.set",
                            "shapes": [],  # Vision pipeline will add shapes
                            "hud": {
                                "title": step.get("title"),
                                "step": f"Step 1 of {len(routine_steps)}",
                                "subtitle": step.get("subtitle"),
                                "time_left_s": step.get("min_time_s"),
                                "max_time_s": step.get("min_time_s"),
                                "hint": step.get("hint"),
                            }
                        })
        except Exception as exc:
            LOGGER.warning("Failed to send initial HUD: %s", exc)
    
    # Use jsonable_encoder for safe datetime serialization
    try:
        from fastapi.encoders import jsonable_encoder
        session_payload = jsonable_encoder(session_state)
    except Exception as exc:
        # Fallback: manual ISO conversion
        LOGGER.debug("jsonable_encoder unavailable, using manual conversion: %s", exc)
        session_payload = session_state.dict()
        if isinstance(session_payload.get("started_at"), datetime):
            session_payload["started_at"] = session_payload["started_at"].isoformat() + "Z"
    return JSONResponse({"status": "started", "session": session_payload})


@app.post("/session/next_step")
async def next_step() -> JSONResponse:
    session_state.step_index += 1
    LOGGER.info("Advanced to step %d", session_state.step_index)
    return JSONResponse({"step_index": session_state.step_index})


@app.post("/session/prev_step")
async def prev_step() -> JSONResponse:
    session_state.step_index = max(0, session_state.step_index - 1)
    LOGGER.info("Rewound to step %d", session_state.step_index)
    return JSONResponse({"step_index": session_state.step_index})


@app.post("/overlay")
async def post_overlay(raw: Dict[str, Any]) -> JSONResponse:
    # Accept either {"message": {...}} or raw overlay payload
    if "message" in raw and isinstance(raw["message"], dict):
        payload = raw["message"]
    else:
        payload = raw
    if "type" not in payload:
        # Wrap arbitrary payload
        payload = {
            "type": "overlay.set",
            "shapes": [],
            "hud": payload,
        }
    await broadcast(payload)
    LOGGER.info("Broadcast overlay message %s", payload.get("type"))
    return JSONResponse({"ok": True})


@app.post("/tts")
async def post_tts(payload: TTSRequest) -> JSONResponse:
    text = payload.text.strip()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, speak_text, text)

    await broadcast({"type": "tts", "text": text})
    LOGGER.info("Queued TTS text length=%d", len(text))
    return JSONResponse({"status": "ok"})


@app.post("/settings")
async def update_settings(payload: SettingsPayload) -> JSONResponse:
    updated = payload.dict(exclude_none=True)
    for key, value in updated.items():
        setattr(settings_state, key, value)
    # Clamp aruco_stride if provided
    if "aruco_stride" in updated:
        settings_state.aruco_stride = max(1, min(int(settings_state.aruco_stride), 8))
    if "detect_scale" in updated:
        try:
            ds = float(settings_state.detect_scale)
        except Exception as exc:
            LOGGER.debug("Invalid detect_scale value, using default: %s", exc)
            ds = 0.75
        settings_state.detect_scale = min(1.0, max(0.5, ds))
    if _vision_pipeline and {"cloud_rps", "cloud_timeout_s", "cloud_min_interval_ms"}.intersection(updated):
        try:
            _vision_pipeline.refresh_cloud_limits()
        except Exception as exc:
            LOGGER.warning("Failed to refresh cloud limits: %s", exc)
    LOGGER.info("Settings updated: %s", updated)
    # Notify clients when reduce_motion changes so UIs can adjust animations
    if "reduce_motion" in updated:
        await broadcast({
            "type": "status",
            "camera": health_state.camera,
            "lighting": health_state.lighting,
            "fps": health_state.fps,
            "reduce_motion": settings_state.reduce_motion,
        })
    return JSONResponse(settings_state.dict())


@app.get("/preview.jpg")
async def get_preview() -> Response:
    frame = await get_preview_frame()
    if frame is None:
        raise HTTPException(status_code=404, detail="Preview unavailable")
    return Response(content=frame, media_type="image/jpeg")


@app.post("/voice/converse", response_model=VoiceResponse)
async def voice_converse(
    file: UploadFile = File(...),
    include_audio: bool = False,
) -> VoiceResponse:
    if _voice_assistant is None or not _voice_assistant.enabled:
        raise HTTPException(status_code=503, detail="Voice assistant unavailable")

    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = Path(tmp.name)
            data = await file.read()
            tmp.write(data)

        result = _voice_assistant.converse_with_details(str(temp_path), play_audio=False)
        if not result:
            raise HTTPException(status_code=502, detail="Unable to process audio input")

        audio_b64 = None
        if include_audio and result.audio_bytes:
            audio_b64 = base64.b64encode(result.audio_bytes).decode("utf-8")

        LOGGER.info(
            "Voice assistant handled request (transcript_length=%s response_length=%s)",
            len(result.transcript or ""),
            len(result.response_text or ""),
        )

        return VoiceResponse(
            transcript=result.transcript,
            response_text=result.response_text,
            audio_b64=audio_b64,
        )
    finally:
        if temp_path and temp_path.exists():
            with contextlib.suppress(Exception):
                temp_path.unlink()


# ============================================================================
# TASK SYSTEM ENDPOINTS
# ============================================================================

@app.get("/tasks")
async def list_tasks() -> JSONResponse:
    """Get list of all available tasks"""
    tasks = get_all_tasks()
    return JSONResponse({"tasks": tasks})


@app.post("/tasks/{task_id}/start")
async def start_task_endpoint(task_id: str) -> JSONResponse:
    """Start a new task"""
    global active_task_session
    
    # Stop any existing task
    if active_task_session:
        await broadcast({"type": "overlay.clear"})
    
    # Start new task
    task_session = start_task(task_id)
    if not task_session:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    active_task_session = task_session
    
    # Update session_state for vision pipeline overlay rendering
    session_state.routine_id = task_id
    session_state.step_index = 0
    session_state.started_at = datetime.utcnow()
    
    # Get first step
    step = task_session.get_current_step()
    if not step:
        raise HTTPException(status_code=500, detail="Task has no steps")
    
    # Speak the first instruction
    if step.voice_prompt:
        speak_text(step.voice_prompt)
    
    # Send overlay
    overlay_msg = task_session.to_overlay_message()
    await broadcast(overlay_msg)
    
    return JSONResponse({
        "ok": True,
        "task_id": task_id,
        "task_name": task_session.task.name,
        "current_step": task_session.current_step,
        "total_steps": len(task_session.task.steps)
    })


@app.post("/tasks/next_step")
async def next_step_endpoint() -> JSONResponse:
    """Advance to next step in active task"""
    global active_task_session
    
    if not active_task_session:
        raise HTTPException(status_code=400, detail="No active task")
    
    # Check if step is complete
    if not active_task_session.check_step_complete():
        return JSONResponse({
            "ok": False,
            "reason": "Step requirements not met",
            "time_left": active_task_session.get_time_left_in_step()
        })
    
    # Advance
    continued = active_task_session.advance_step()
    
    # Update session_state for vision pipeline
    session_state.step_index = active_task_session.current_step - 1  # session_state is 0-indexed
    
    if not continued:
        # Task complete!
        session_state.routine_id = None
        session_state.step_index = 0
        await broadcast({"type": "overlay.clear"})
        speak_text(f"Great job! You completed {active_task_session.task.name}!")
        active_task_session = None
        return JSONResponse({
            "ok": True,
            "task_complete": True
        })
    
    # Get new step
    step = active_task_session.get_current_step()
    if step and step.voice_prompt:
        speak_text(step.voice_prompt)
    
    # Send overlay
    overlay_msg = active_task_session.to_overlay_message()
    await broadcast(overlay_msg)
    
    return JSONResponse({
        "ok": True,
        "current_step": active_task_session.current_step,
        "total_steps": len(active_task_session.task.steps)
    })


@app.post("/tasks/stop")
async def stop_task_endpoint() -> JSONResponse:
    """Stop current task"""
    global active_task_session
    
    if not active_task_session:
        return JSONResponse({"ok": True, "message": "No active task"})
    
    task_name = active_task_session.task.name
    active_task_session = None
    
    # Clear session_state
    session_state.routine_id = None
    session_state.step_index = 0
    
    await broadcast({"type": "overlay.clear"})
    speak_text(f"Task stopped: {task_name}")
    
    return JSONResponse({"ok": True, "message": f"Stopped {task_name}"})

# ============================================================================
# GENAI COACHING (stub heuristics now; replace later with LLM call)
# ============================================================================

class CoachRequest(BaseModel):
    task_id: Optional[str] = None
    step_num: Optional[int] = None
    user_state: Optional[Dict[str, Any]] = None

class CoachResponse(BaseModel):
    coach_tip: str
    source: str

@app.post("/genai/coach", response_model=CoachResponse)
async def genai_coach(req: CoachRequest) -> CoachResponse:
    global active_task_session
    # Derive context from active session if missing
    task_id = req.task_id or (active_task_session.task.task_id if active_task_session else None)
    step_num = req.step_num or (active_task_session.current_step if active_task_session else None)
    if not task_id or not step_num:
        raise HTTPException(status_code=400, detail="No task context available")
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Unknown task")
    step = task.get_step(step_num)
    if not step:
        raise HTTPException(status_code=404, detail="Unknown step")
    title = step.title.lower()
    tip = None
    if "upper" in title:
        tip = "Tilt brush 45° toward gums; short circles help remove plaque."
    elif "lower" in title:
        tip = "Relax jaw slightly; reach molars with gentle circular passes."
    elif "tongue" in title:
        tip = "2–3 light strokes are enough; avoid triggering gag reflex."
    elif "detangle" in title:
        tip = "Hold section; work from ends upward to prevent breakage."
    elif "roots" in title:
        tip = "Long strokes from roots to tips distribute natural oils."
    elif "fill" in title or "define" in title:
        tip = "Feather light strokes following natural hair direction."
    elif "massage" in title:
        tip = "Use fingertip pads, gentle circles—avoid eye area."
    else:
        tip = step.instruction or "Keep a steady pace—consistency matters."
    return CoachResponse(coach_tip=tip, source="heuristic-local")

# ============================================================================
# TTS REPLAY ENDPOINT
# ============================================================================

@app.post("/tts/replay")
async def tts_replay() -> JSONResponse:
    global active_task_session
    if not active_task_session:
        raise HTTPException(status_code=400, detail="No active task")
    step = active_task_session.get_current_step()
    if not step or not step.voice_prompt:
        return JSONResponse({"ok": False, "reason": "No voice prompt for this step"})
    speak_text(step.voice_prompt)
    return JSONResponse({"ok": True})


@app.get("/tasks/current")
async def get_current_task() -> JSONResponse:
    """Get current active task status"""
    global active_task_session
    
    if not active_task_session:
        return JSONResponse({"active": False})
    
    step = active_task_session.get_current_step()
    
    return JSONResponse({
        "active": True,
        "task_id": active_task_session.task.task_id,
        "task_name": active_task_session.task.name,
        "current_step": active_task_session.current_step,
        "total_steps": len(active_task_session.task.steps),
        "step_title": step.title if step else None,
        "time_left_s": active_task_session.get_time_left_in_step(),
        "state": active_task_session.state.value
    })


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/ws")
async def websocket_root(websocket: WebSocket) -> None:  # new dev-friendly endpoint
    origin = websocket.headers.get("origin")
    if not _ws_origin_ok(origin):
        LOGGER.info(f"WS 403 blocked origin={origin!r}")
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            # We don't currently expect messages; keep receive to detect client close
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("WebSocket error: %s", exc)
        await manager.disconnect(websocket)

@app.websocket("/ws/mirror")
async def websocket_endpoint(websocket: WebSocket) -> None:  # legacy path preserved
    origin = websocket.headers.get("origin")
    if not _ws_origin_ok(origin):
        LOGGER.info(f"WS 403 blocked origin={origin!r}")
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:  # pragma: no cover - defensive log
        LOGGER.warning("WebSocket error: %s", exc)
        await manager.disconnect(websocket)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _vision_pipeline
    LOGGER.info("Shutting down backend")
    
    # Stop vision pipeline
    if _vision_pipeline:
        try:
            _vision_pipeline.stop()
            LOGGER.info("Vision pipeline stopped")
        except Exception as exc:
            LOGGER.error("Error stopping vision pipeline: %s", exc)
    
    _executor.shutdown(wait=False)
    if _broadcast_task:
        _broadcast_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _broadcast_task


_vision_pipeline: Optional[Any] = None


@app.on_event("startup")
async def on_startup() -> None:
    global _broadcast_task, _message_queue, _event_loop, _vision_pipeline
    _event_loop = asyncio.get_running_loop()
    _message_queue = asyncio.Queue(maxsize=256)
    _broadcast_task = asyncio.create_task(_broadcast_worker())
    
    # Start vision pipeline
    try:
        from vision_pipeline import VisionPipeline
        _vision_pipeline = VisionPipeline(
            broadcast_fn=queue_broadcast,
            settings=settings_state,
            session=session_state,
            health=health_state,
            camera_width=1280,
            camera_height=720,
            camera_fps=24,
            camera_device=0,
            preview_fn=set_preview_frame  # Pass preview function directly
        )
        _vision_pipeline.start()
        LOGGER.info("Vision pipeline started successfully")
    except Exception as exc:
        LOGGER.error("Failed to start vision pipeline: %s", exc)
        # Attempt synthetic fallback so overlays & health still work
        try:
            from vision_pipeline import VisionPipeline
            _vision_pipeline = VisionPipeline(
                broadcast_fn=queue_broadcast,
                settings=settings_state,
                session=session_state,
                health=health_state,
                camera_width=1280,
                camera_height=720,
                camera_fps=24,
                camera_device=0,
                camera_enabled=False,
            )
            _vision_pipeline.start()
            LOGGER.info("Vision pipeline started in synthetic (mock) mode")
            health_state.camera = "mock"
            health_state.mock_camera = True
        except Exception as inner:
            LOGGER.error("Synthetic fallback failed: %s", inner)
            _vision_pipeline = None


if __name__ == "__main__":
    import uvicorn

    # Use app:app when running from backend directory, or backend.app:app from project root
    # Default to port 8000 to match MagicMirror config
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
