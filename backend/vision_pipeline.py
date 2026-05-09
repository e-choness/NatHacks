"""
Vision Pipeline for CV Smart Mirror
Processes camera frames with MediaPipe Face Mesh & Hands for real-time AR overlays.
"""
import json
import logging
import threading
import time
import contextlib
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from cloud_vision import CloudVisionClient

LOGGER = logging.getLogger("assistivecoach.vision")

# OpenCV performance tuning: pin threads & enable optimizations
try:
    cv2.useOptimized()
    cv2.setNumThreads(1)
except Exception as exc:
    LOGGER.debug("OpenCV performance tuning unavailable: %s", exc)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = PROJECT_ROOT / "config" / "features.json"
TASKS_PATH = PROJECT_ROOT / "config" / "tasks.json"
TOOLS_PATH = PROJECT_ROOT / "config" / "tools.json"
LOGS_PATH = PROJECT_ROOT / "logs" / "latency.csv"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        LOGGER.warning("Missing configuration file: %s", path)
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class VisionPipeline:
    """
    Processes camera frames with MediaPipe Face Mesh & Hands.
    Optionally blends in Google Cloud Vision landmarks via a non-blocking worker.
    Emits overlay messages via broadcast callback with <150ms latency target on Pi 4/5.
    """

    def __init__(
        self,
        broadcast_fn: Callable[[Dict[str, Any]], None],
        settings: Any,
        session: Any,
        health: Any,
        camera_width: int = 1280,
        camera_height: int = 720,
        camera_fps: int = 24,
        camera_device: int = 0,
        *,
        camera_enabled: bool = True,
        camera_override: Optional[Any] = None,
        preview_fn: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """
        Initialize vision pipeline.
        
        Args:
            broadcast_fn: Callback to send overlay messages (queue_broadcast from app.py)
            settings: Settings state object with flags (use_cloud, face, hands, aruco)
            session: Session state object (routine_id, step_index)
            health: Health state object to update (fps, latency_ms, etc.)
            camera_width: Camera resolution width (default 1280 for 720p)
            camera_height: Camera resolution height (default 720)
            camera_fps: Target FPS (24-30 recommended for Pi)
            camera_device: Camera device index
        """
        self.broadcast_fn = broadcast_fn
        self.settings = settings
        self.session = session
        self.health = health
        self.set_preview_frame = preview_fn

        # Initialize camera
        if camera_override is not None:
            self.camera = camera_override
        elif camera_enabled:
            from camera_capture import CameraCapture

            preview_callback = self.set_preview_frame
            if preview_callback is None:
                from app import set_preview_frame as _app_preview

                preview_callback = _app_preview
                self.set_preview_frame = preview_callback

            camera_preview_fn = None if preview_fn is not None else preview_callback

            self.camera = CameraCapture(
                camera_width,
                camera_height,
                camera_fps,
                camera_device,
                health_state=self.health,
                set_preview_fn=camera_preview_fn,
            )
        else:
            class _DummyCamera:
                def __init__(self, width: int, height: int) -> None:
                    self.width = width
                    self.height = height
                def read(self) -> Tuple[np.ndarray, int]:
                    frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    ts = time.time_ns()
                    return frame, ts
                def close(self) -> None:
                    pass
            self.camera = _DummyCamera(camera_width, camera_height)
        self.frame_w = camera_width
        self.frame_h = camera_height
        
        # Load configuration
        features_raw = _load_json(FEATURES_PATH)
        tasks_raw = _load_json(TASKS_PATH)
        tools_raw = _load_json(TOOLS_PATH)
        self._features = features_raw if isinstance(features_raw, dict) else {}
        self._tasks = tasks_raw if isinstance(tasks_raw, dict) else {}
        self._tools = tools_raw.get("tools", {}) if isinstance(tools_raw, dict) else {}
        
        # Thread control
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # EMA smoothing state (alpha=0.4 for good responsiveness vs stability)
        self._ema: Dict[str, Tuple[float, float]] = {}
        self._alpha = 0.4
        
        # Face detection state for ROI optimization
        self._last_face_bbox: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
        self._no_face_since: Optional[float] = None
        
        # Initialize MediaPipe models and optional cloud assist
        self._mediapipe = self._init_mediapipe()
        self._hand_detector = self._init_hands()
        self._cloud_client = CloudVisionClient()
        self._cloud_executor: Optional[ThreadPoolExecutor] = None
        self._cloud_future: Optional[Future[Optional[Dict[str, Any]]]] = None
        self._cloud_latest: Optional[Dict[str, Any]] = None
        self._cloud_result_ttl_s = 1.5
        self._cloud_last_latency_ms = 0.0
        self._cloud_last_confidence = 0.0
        self._cloud_last_ok = False
        if self._cloud_client.enabled:
            self._cloud_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="CloudVision")
        self.refresh_cloud_limits()
        self._refresh_cloud_health()

        # ArUco guidance state
        self._aruco_last_state = {}
        self._aruco_state_since = {}
        self._aruco_debounce_s = 0.25
        self._aruco_last_detection_ns = 0
        self._aruco_last_detection_s = 0.0  # wall-clock seconds of last successful detection
        self._aruco_last_meta = None  # type: Optional[Dict[str, Any]]
        self._aruco_pose_announced = False
        self._last_ar_anchors = []  # type: List[Dict[str, Any]]
        # Frame gating & overlay throttle
        self._i = 0
        self._overlay_min_interval_ms = 66  # ~15 Hz
        self._last_overlay_ts_ms = 0
        # Adaptive performance state
        self._face_frame_stride = 1  # dynamic: may increase under load
        self._aruco_frame_stride = 2  # default every 2 frames; may increase
        # Respect initial stride from shared settings if provided
        try:
            init_stride = int(getattr(self.settings, "aruco_stride", 2))
            if 1 <= init_stride <= 8:
                self._aruco_frame_stride = init_stride
        except Exception as exc:
            LOGGER.debug("Could not read aruco_stride setting, using default: %s", exc)
        self._face_target_w = camera_width  # will downscale under load
        self._last_landmarks = {}
        self._last_face_mesh = None  # raw mediapipe face mesh for contextual overlays
        self._high_latency_frames = 0
        self._high_latency_max_ms = 0.0
        self._latency_window_frames = 0
        self._perf_last_adapt_ns = time.time_ns()
        # Prime intrinsics status once so /health can expose pose availability even before markers appear
        try:
            from ar_overlay import load_camera_intrinsics
            pose_requested = bool(getattr(self.settings, "pose", True))
            if pose_requested:
                _k, _d, ok, err = load_camera_intrinsics()
                self._aruco_last_meta = {
                    "pose_enabled": pose_requested,
                    "pose_available": bool(ok),
                    "intrinsics_error": (None if ok else err),
                }
        except Exception as exc:
            # Safe to ignore; will be populated on first detection
            LOGGER.debug("Could not initialize ArUco intrinsics status: %s", exc)
        
        # Ensure logs directory exists
        LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV header if file doesn't exist
        if not LOGS_PATH.exists():
            with LOGS_PATH.open("w", encoding="utf-8") as f:
                f.write(
                    "capture_ts,landmark_ts,overlay_ts,e2e_ms,fps,use_cloud,"
                    "cloud_latency_ms,cloud_confidence,cloud_ok,cloud_breaker_open\n"
                )
        
        LOGGER.info("VisionPipeline initialized: %dx%d @ %dfps", camera_width, camera_height, camera_fps)

    # ------------------------------------------------------------------
    # Landmark utilities for contextual task overlays
    # ------------------------------------------------------------------
    def _extract_face_landmarks(self, face_result: Any) -> Dict[int, Tuple[float, float]]:
        """Return dict of landmark_index -> (x,y) normalized (0..1)."""
        lm_map: Dict[int, Tuple[float, float]] = {}
        try:
            if not face_result or not getattr(face_result, "multi_face_landmarks", None):
                return lm_map
            face_landmarks = face_result.multi_face_landmarks[0]  # assume 1 face
            for i, lm in enumerate(face_landmarks.landmark):  # type: ignore[attr-defined]
                lm_map[i] = (lm.x, lm.y)
        except Exception:
            return lm_map
        return lm_map

    def _compute_face_regions(self, lm_map: Dict[int, Tuple[float, float]]) -> Dict[str, Dict[str, int]]:
        """Compute all facial region centers from FaceMesh 468 landmarks.
        Returns pixel coordinates for mouth, eyes, cheeks, forehead, chin, nose regions.
        FaceMesh landmark reference: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
        """
        if not lm_map:
            return {}
        
        def _avg(indices: List[int]) -> Tuple[float, float]:
            pts = [lm_map[i] for i in indices if i in lm_map]
            if not pts:
                return (0.5, 0.5)
            x = sum(p[0] for p in pts) / len(pts)
            y = sum(p[1] for p in pts) / len(pts)
            return (x, y)
        
        # Mouth regions (lips outer contours)
        mouth_upper_indices = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
        mouth_lower_indices = [146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
        mouth_left_indices = [61, 76, 62, 78, 81, 13, 82]
        mouth_right_indices = [291, 306, 292, 308, 311, 14, 312]
        mouth_center_indices = [13, 14, 17, 0]
        
        # Eye regions (around eye contours)
        eye_left_indices = [33, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7]
        eye_right_indices = [263, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249]
        
        # Cheek regions (mid-face area)
        cheek_left_indices = [116, 123, 147, 213, 192, 214]
        cheek_right_indices = [345, 352, 376, 433, 416, 434]
        
        # Forehead / brow regions
        brow_left_indices = [70, 63, 105, 66, 107, 55, 65]
        brow_right_indices = [300, 293, 334, 296, 336, 285, 295]
        forehead_center_indices = [10, 151, 9, 8]
        
        # Chin / jaw region
        chin_center_indices = [152, 148, 149, 176, 148, 152]
        jaw_left_indices = [172, 136, 150, 149]
        jaw_right_indices = [397, 365, 379, 378]
        
        # Nose regions
        nose_tip_indices = [1, 2]
        nose_bridge_indices = [6, 197, 195, 5]
        
        regions: Dict[str, Dict[str, int]] = {}
        
        # Compute all regions
        region_map = {
            "mouth_upper": mouth_upper_indices,
            "mouth_lower": mouth_lower_indices,
            "mouth_left": mouth_left_indices,
            "mouth_right": mouth_right_indices,
            "mouth_center": mouth_center_indices,
            "eye_left": eye_left_indices,
            "eye_right": eye_right_indices,
            "cheek_left": cheek_left_indices,
            "cheek_right": cheek_right_indices,
            "brow_left": brow_left_indices,
            "brow_right": brow_right_indices,
            "forehead_center": forehead_center_indices,
            "chin_center": chin_center_indices,
            "jaw_left": jaw_left_indices,
            "jaw_right": jaw_right_indices,
            "nose_tip": nose_tip_indices,
            "nose_bridge": nose_bridge_indices,
        }
        
        for region_name, indices in region_map.items():
            nx, ny = _avg(indices)
            regions[region_name] = {
                "x": int(nx * self.frame_w),
                "y": int(ny * self.frame_h),
            }
        
        return regions

    def _task_overlay_shapes(self, lm_map: Dict[int, Tuple[float, float]]) -> List[Dict[str, Any]]:
        """Return shapes list contextual to active task step.
        Maps task steps to facial regions with appropriate visual guidance.
        """
        task_id = getattr(self.session, "routine_id", None)
        step_index = getattr(self.session, "step_index", 0)
        if not task_id:
            return []
        
        regions = self._compute_face_regions(lm_map)
        if not regions:
            return []
        
        # Task-specific step mappings: step_index -> (region_keys, shape_config)
        task_mappings = {
            "brush_teeth": {
                0: {  # Wet toothbrush - show mouth center
                    "regions": ["mouth_center"],
                    "radius": 80,
                    "show_arrow": False,
                },
                1: {  # Upper teeth
                    "regions": ["mouth_upper"],
                    "radius": 110,
                    "show_arrow": True,
                    "arrow_from": "mouth_left",
                    "arrow_to": "mouth_right",
                },
                2: {  # Lower teeth
                    "regions": ["mouth_lower"],
                    "radius": 110,
                    "show_arrow": True,
                    "arrow_from": "mouth_left",
                    "arrow_to": "mouth_right",
                },
                3: {  # Tongue
                    "regions": ["mouth_center"],
                    "radius": 90,
                    "show_arrow": False,
                },
            },
            "wash_face": {
                0: {  # Wet face - show full face
                    "regions": ["forehead_center", "cheek_left", "cheek_right", "chin_center"],
                    "radius": 90,
                    "show_arrow": False,
                },
                1: {  # Apply cleanser (hands, skip facial overlay)
                    "regions": [],
                    "radius": 0,
                    "show_arrow": False,
                },
                2: {  # Massage face - show cheeks with circular motion hint
                    "regions": ["cheek_left", "cheek_right", "forehead_center"],
                    "radius": 110,
                    "show_arrow": True,
                    "arrow_from": "nose_bridge",
                    "arrow_to": "cheek_right",
                },
                3: {  # Rinse - show full face again
                    "regions": ["forehead_center", "cheek_left", "cheek_right", "chin_center"],
                    "radius": 90,
                    "show_arrow": False,
                },
                4: {  # Pat dry - show cheeks
                    "regions": ["cheek_left", "cheek_right"],
                    "radius": 100,
                    "show_arrow": False,
                },
            },
            "comb_hair": {
                0: {  # Detangle ends (hair, not facial regions - minimal overlay)
                    "regions": [],
                    "radius": 0,
                    "show_arrow": False,
                },
                1: {  # Detangle ends
                    "regions": [],
                    "radius": 0,
                    "show_arrow": False,
                },
                2: {  # Brush from roots - show forehead region
                    "regions": ["forehead_center"],
                    "radius": 130,
                    "show_arrow": True,
                    "arrow_from": "forehead_center",
                    "arrow_to": "chin_center",
                },
                3: {  # Style
                    "regions": [],
                    "radius": 0,
                    "show_arrow": False,
                },
            },
            "draw_eyebrows": {
                0: {  # Prepare tools
                    "regions": [],
                    "radius": 0,
                    "show_arrow": False,
                },
                1: {  # Brush brows
                    "regions": ["brow_left", "brow_right"],
                    "radius": 80,
                    "show_arrow": False,
                },
                2: {  # Fill left brow
                    "regions": ["brow_left"],
                    "radius": 85,
                    "show_arrow": True,
                    "arrow_from": "nose_bridge",
                    "arrow_to": "brow_left",
                },
                3: {  # Fill right brow
                    "regions": ["brow_right"],
                    "radius": 85,
                    "show_arrow": True,
                    "arrow_from": "nose_bridge",
                    "arrow_to": "brow_right",
                },
                4: {  # Blend
                    "regions": ["brow_left", "brow_right"],
                    "radius": 80,
                    "show_arrow": False,
                },
                5: {  # Final check
                    "regions": ["brow_left", "brow_right"],
                    "radius": 80,
                    "show_arrow": False,
                },
            },
            "shave": {
                0: {  # Prep skin
                    "regions": ["cheek_left", "cheek_right"],
                    "radius": 120,
                    "show_arrow": False,
                },
                1: {  # Right cheek
                    "regions": ["cheek_right"],
                    "radius": 130,
                    "show_arrow": True,
                    "arrow_from": "jaw_right",
                    "arrow_to": "cheek_right",
                },
                2: {  # Left cheek
                    "regions": ["cheek_left"],
                    "radius": 130,
                    "show_arrow": True,
                    "arrow_from": "jaw_left",
                    "arrow_to": "cheek_left",
                },
                3: {  # Neck
                    "regions": ["chin_center"],
                    "radius": 100,
                    "show_arrow": True,
                    "arrow_from": "chin_center",
                    "arrow_to": "mouth_center",
                },
            },
            "moisturize": {
                0: {  # Dispense lotion (hands not facial region, skip overlay)
                    "regions": [],
                    "radius": 0,
                    "show_arrow": False,
                },
                1: {  # Cheeks
                    "regions": ["cheek_left", "cheek_right"],
                    "radius": 120,
                    "show_arrow": False,
                },
                2: {  # Forehead
                    "regions": ["brow_left", "brow_right", "forehead_center"],
                    "radius": 100,
                    "show_arrow": True,
                    "arrow_from": "forehead_center",
                    "arrow_to": "brow_right",
                },
                3: {  # Neck
                    "regions": ["chin_center"],
                    "radius": 100,
                    "show_arrow": True,
                    "arrow_from": "chin_center",
                    "arrow_to": "mouth_lower",
                },
            },
        }
        
        # Get mapping for current task and step
        task_map = task_mappings.get(task_id)
        if not task_map:
            return []
        
        step_config = task_map.get(step_index)
        if not step_config:
            return []
        
        shapes: List[Dict[str, Any]] = []
        region_keys = step_config.get("regions", [])
        radius = step_config.get("radius", 100)
        
        # Add ring for each target region
        for region_key in region_keys:
            pt = regions.get(region_key)
            if not pt:
                continue
            
            # Clean up region name for display
            display_name = region_key.replace("_", " ").title()
            if "Left" in display_name or "Right" in display_name:
                display_name = display_name.split()[0]  # Just "Cheek", "Eye", etc.
            
            shapes.append({
                "kind": "ring",
                "anchor": {"pixel": {"x": pt["x"], "y": pt["y"]}},
                "radius_px": radius,
                "accent": "info",
                "text": display_name,
            })
        
        # Add directional arrow if specified
        if step_config.get("show_arrow"):
            arrow_from = step_config.get("arrow_from")
            arrow_to = step_config.get("arrow_to")
            if arrow_from and arrow_to:
                pt_from = regions.get(arrow_from)
                pt_to = regions.get(arrow_to)
                if pt_from and pt_to:
                    shapes.append({
                        "kind": "arrow",
                        "anchor": {"pixel": {"x": pt_from["x"], "y": pt_from["y"]}},
                        "to": {"pixel": {"x": pt_to["x"], "y": pt_to["y"]}},
                        "accent": "info",
                    })
        
        return shapes

    def _init_mediapipe(self) -> Any:  # pragma: no cover
        """Initialize MediaPipe FaceMesh model (lazy import)."""
        try:
            import mediapipe as mp  # type: ignore[import]
            face_mesh = mp.solutions.face_mesh.FaceMesh(  # type: ignore[attr-defined]
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            LOGGER.info("MediaPipe FaceMesh initialized")
            return face_mesh
        except ImportError:
            LOGGER.warning("MediaPipe FaceMesh not available")
            return None

    def _init_hands(self) -> Any:  # pragma: no cover
        """Initialize MediaPipe Hands detector."""
        try:
            import mediapipe as mp  # type: ignore[import]
            hands = mp.solutions.hands.Hands(  # type: ignore[attr-defined]
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            LOGGER.info("MediaPipe Hands initialized")
            return hands
        except ImportError:
            LOGGER.warning("MediaPipe Hands not available")
            return None

    def start(self) -> None:
        """Start the vision pipeline background thread."""
        if self._running:
            LOGGER.warning("Vision pipeline already running")
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="VisionPipeline")
        self._thread.start()
        LOGGER.info("Vision pipeline started")

    def stop(self) -> None:
        """Stop the vision pipeline and clean up resources."""
        if not self._running:
            return
        LOGGER.info("Stopping vision pipeline...")
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._cloud_executor:
            self._cloud_executor.shutdown(wait=False)
            self._cloud_executor = None
        self._cloud_future = None
        self.camera.close()
        LOGGER.info("Vision pipeline stopped")

    def _run(self) -> None:  # pragma: no cover - involves hardware
        """Main processing loop running in background thread."""
        LOGGER.info("Vision pipeline processing loop started")
        frame_count = 0
        
        while self._running and not self._stop_event.is_set():
            try:
                # Grab latest frame
                frame_rgb, capture_ts_ns = self.camera.read()
                capture_ts = capture_ts_ns / 1e9  # Convert to seconds
            except RuntimeError:
                # Camera not ready yet
                if not self._stop_event.wait(0.05):
                    continue
                break
            
            frame_count += 1
            loop_start_perf = time.perf_counter()
            capture_end_perf = loop_start_perf  # camera.read already done
            landmark_start_perf = time.perf_counter()
            self.health.last_frame_ns = capture_ts_ns

            # Update any completed cloud vision work before processing this frame.
            self._resolve_cloud_future()
            self._refresh_cloud_health()

            # Get frame dimensions
            frame_h, frame_w = frame_rgb.shape[:2]
            self.frame_w = frame_w
            self.frame_h = frame_h

            # ROI optimization: crop around last known face
            roi_frame, roi_offset = self._apply_roi(frame_rgb)

            # Process landmarks (MediaPipe or synthetic mode)
            process_face = True
            if self._face_frame_stride > 1:
                # Only process face landmarks on stride boundary
                if (frame_count % self._face_frame_stride) != 0:
                    process_face = False
            if process_face:
                # Dynamic downscale for face landmarks
                face_frame = roi_frame
                rw = roi_frame.shape[1]
                if rw > self._face_target_w:
                    fx = self._face_target_w / float(rw)
                    face_frame = cv2.resize(roi_frame, dsize=None, fx=fx, fy=fx, interpolation=cv2.INTER_AREA)
                    face_scale_up = 1.0 / fx
                else:
                    face_scale_up = 1.0
                landmarks = self._process_landmarks(face_frame, roi_offset)
                # Landmarks already normalized to full-frame; reuse
                self._last_landmarks = landmarks
            else:
                landmarks = self._last_landmarks
            face_end_perf = time.perf_counter()

            # Process hands if enabled
            hand_landmarks: Dict[str, Tuple[float, float]] = {}
            hands_start_perf = time.perf_counter()
            if self.settings.hands and self._hand_detector:
                hand_landmarks = self._process_hands(roi_frame, roi_offset)
            hands_end_perf = time.perf_counter()

            # Detect ArUco markers if enabled (downscale & run every 2 frames)
            ar_anchors: List[Dict[str, Any]] = []
            aruco_start_perf = time.perf_counter()
            if self.settings.aruco:
                try:
                    from ar_overlay import detect_aruco_anchors
                    ar_anchors = detect_aruco_anchors(frame_rgb)
                except (RuntimeError, ImportError) as exc:
                    LOGGER.debug("ArUco detection unavailable: %s", exc)
            aruco_end_perf = time.perf_counter()

            landmark_ts = time.time()
            landmarks_done_perf = time.perf_counter()

            cloud_latency_ms = 0.0
            cloud_confidence = 0.0
            cloud_ok = False
            if self.settings.use_cloud and self._cloud_client.enabled:
                active_cloud = self._active_cloud_result()
                if active_cloud and isinstance(active_cloud.get("landmarks"), dict):
                    cloud_confidence = float(active_cloud.get("confidence", 0.0) or 0.0)
                    cloud_latency_ms = float(active_cloud.get("latency_ms", 0.0) or 0.0)
                    cloud_ok = bool(active_cloud.get("ok", False))
                    landmarks = self._merge_cloud_landmarks(
                        landmarks,
                        active_cloud.get("landmarks", {}),
                        cloud_confidence,
                    )
                self._submit_cloud_job(frame_rgb)
            else:
                self._cloud_latest = None

            # Build overlay message
            all_landmarks = {**landmarks, **hand_landmarks}
            shapes_start_perf = time.perf_counter()
            overlay_shapes = self._build_shapes(all_landmarks, frame_w, frame_h, ar_anchors)

            # Auto ArUco ring overlays (idle clear after 0.75s)
            if getattr(self.settings, "overlay_from_aruco", True):
                now_s = time.time()
                age_s = now_s - self._aruco_last_detection_s
                if age_s < 0.75 and self._last_ar_anchors:
                    for anchor in self._last_ar_anchors:
                        center = anchor.get("center_px")
                        if not isinstance(center, dict):
                            continue
                        cx = float(center.get("x", 0.0))
                        cy = float(center.get("y", 0.0))
                        overlay_shapes.append(
                            {
                                "kind": "ring",
                                "anchor": {"pixel": {"x": cx, "y": cy}},
                                "radius_px": 60,
                                "accent": "info",
                            }
                        )

            if self.settings.aruco and ar_anchors:
                guidance = self._build_tool_guidance(ar_anchors, all_landmarks, frame_w, frame_h)
                overlay_shapes.extend(guidance)
            # Contextual task-specific overlays (e.g., mouth quadrants)
            try:
                if self._last_face_mesh is not None and getattr(self.session, "routine_id", None):
                    lm_full = {i: (lm.x, lm.y) for i, lm in enumerate(self._last_face_mesh.landmark)}
                    contextual = self._task_overlay_shapes(lm_full)
                    if contextual:
                        overlay_shapes.extend(contextual)
            except Exception as exc:
                LOGGER.debug("Contextual overlay generation failed: %s", exc)
            hud = self._build_hud()
            shapes_end_perf = time.perf_counter()

            # Draw debug overlays on preview frame and publish annotated frames
            try:
                self._draw_debug_overlays(frame_rgb, landmarks, hand_landmarks, ar_anchors)
            except Exception as exc:  # pragma: no cover - debug aid
                LOGGER.debug("Debug overlay drawing failed: %s", exc)

            if self.set_preview_frame and frame_count % 2 == 0:
                try:
                    prev_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                    _, buffer = cv2.imencode(
                        ".jpg",
                        prev_bgr,
                        [cv2.IMWRITE_JPEG_QUALITY, 85],
                    )
                    self.set_preview_frame(bytes(buffer))
                except Exception as exc:  # pragma: no cover - preview is best-effort
                    LOGGER.debug("Preview publish failed: %s", exc)

            message = {
                "type": "overlay.set",
                "shapes": overlay_shapes,
                "hud": hud,
            }
            
            # Broadcast overlay
            broadcast_start_perf = time.perf_counter()
            self.broadcast_fn(message)
            overlay_ts = time.time()
            broadcast_end_perf = time.perf_counter()
            
            # Update health metrics
            e2e_ms = (overlay_ts - capture_ts) * 1000.0
            loop_end_perf = time.perf_counter()
            # Timing breakdown (ms)
            capture_ms = (capture_end_perf - loop_start_perf) * 1000.0
            face_ms = (face_end_perf - landmark_start_perf) * 1000.0
            hands_ms = (hands_end_perf - hands_start_perf) * 1000.0
            aruco_ms = (aruco_end_perf - aruco_start_perf) * 1000.0
            shapes_ms = (shapes_end_perf - shapes_start_perf) * 1000.0
            broadcast_ms = (broadcast_end_perf - broadcast_start_perf) * 1000.0
            other_ms = e2e_ms - (face_ms + hands_ms + aruco_ms + shapes_ms + broadcast_ms)
            self.health.latency_ms = e2e_ms
            self._refresh_cloud_health()
            if self.settings.use_cloud and self._cloud_client.enabled:
                if cloud_latency_ms == 0.0:
                    cloud_latency_ms = self.health.cloud_latency_ms
            else:
                cloud_latency_ms = 0.0
                cloud_confidence = 0.0
                cloud_ok = False
            
            # Log to CSV
            self._log_latency(
                capture_ts,
                landmark_ts,
                overlay_ts,
                e2e_ms,
                cloud_latency_ms,
                cloud_confidence,
                cloud_ok,
            )
            
            # Check for "no face" condition
            if not landmarks and self.settings.face:
                if self._no_face_since is None:
                    self._no_face_since = time.time()
                elif (time.time() - self._no_face_since) > 2.0:
                    # No face for 2 seconds - send hint
                    if frame_count % 30 == 0:  # Don't spam, send every ~1 sec at 30fps
                        self._send_no_face_hint()
            else:
                self._no_face_since = None
            
            # Frame drop handling: if processing is lagging, we naturally drop frames
            # because camera.read() always returns latest frame
            if e2e_ms > 150:
                self._high_latency_frames += 1
                self._high_latency_max_ms = max(self._high_latency_max_ms, e2e_ms)
            self._latency_window_frames += 1
            if e2e_ms > 300:
                LOGGER.warning(
                    "Frame %d latency=%.1fms breakdown capture=%.1f face=%.1f hands=%.1f aruco=%.1f shapes=%.1f broadcast=%.1f other=%.1f stride(face=%d aruco=%d) target_w(face=%d)",
                    frame_count,
                    e2e_ms,
                    capture_ms,
                    face_ms,
                    hands_ms,
                    aruco_ms,
                    shapes_ms,
                    broadcast_ms,
                    other_ms,
                    self._face_frame_stride,
                    self._aruco_frame_stride,
                    self._face_target_w,
                )
            # Aggregate summary every 60 frames
            if self._latency_window_frames >= 60:
                if self._high_latency_frames:
                    LOGGER.warning(
                        "Latency summary: high=%d/%d frames (%.1f%%) max=%.1fms stride(face=%d aruco=%d) face_w=%d",
                        self._high_latency_frames,
                        self._latency_window_frames,
                        100.0 * self._high_latency_frames / self._latency_window_frames,
                        self._high_latency_max_ms,
                        self._face_frame_stride,
                        self._aruco_frame_stride,
                        self._face_target_w,
                    )
                self._latency_window_frames = 0
                self._high_latency_frames = 0
                self._high_latency_max_ms = 0.0
            # Adaptive performance adjustments
            self._adapt_performance(e2e_ms)
            # Simple camera watchdog: if latency remains extreme for a sustained window, attempt soft reset
            try:
                if e2e_ms > 1500 and self._latency_window_frames % 30 == 0:
                    LOGGER.warning("Watchdog: extreme latency detected; attempting camera soft reset")
                    with contextlib.suppress(Exception):
                        self.camera.close()
                    # re-open camera
                    from camera_capture import CameraCapture
                    self.camera = CameraCapture(self.frame_w, self.frame_h, 24, 0)
            except Exception as _wd_exc:  # pragma: no cover
                LOGGER.debug("Watchdog reset failed: %s", _wd_exc)
        
        LOGGER.info("Vision pipeline processing loop exited")

    def _apply_roi(self, frame: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Apply ROI crop around last known face for faster processing.
        Returns: (cropped_frame, (x_offset, y_offset))
        """
        if self._last_face_bbox is None:
            # First frame or lost tracking - use full frame
            return frame, (0, 0)
        
        # Expand bbox by 20% with padding
        x, y, w, h = self._last_face_bbox
        pad_w = int(w * 0.2)
        pad_h = int(h * 0.2)
        
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(frame.shape[1], x + w + pad_w)
        y2 = min(frame.shape[0], y + h + pad_h)
        
        roi = frame[y1:y2, x1:x2]
        return roi, (x1, y1)
    
    def _process_landmarks(
        self, 
        frame_rgb: np.ndarray, 
        roi_offset: Tuple[int, int] = (0, 0)
    ) -> Dict[str, Tuple[float, float]]:
        """
        Extract facial landmarks using MediaPipe Face Mesh.
        Returns normalized (x, y) coordinates [0, 1] in full-frame space.
        """
        if not self.settings.face or not self._mediapipe:
            # Synthetic mode: place mouth at center with small pulse
            if not self._mediapipe:
                pulse = 0.5 + 0.02 * np.sin(time.time() * 2.0)
                return {"mouth_center": (pulse, 0.5)}
            return {}
        
        # Process frame with MediaPipe
        results = self._mediapipe.process(frame_rgb)
        if not results.multi_face_landmarks:
            self._last_face_bbox = None
            return {}
        
        face_landmarks = results.multi_face_landmarks[0]
        # Store raw mesh for contextual overlays (e.g., mouth quadrants)
        self._last_face_mesh = face_landmarks
        
        # Update face bbox for ROI tracking
        h, w = frame_rgb.shape[:2]
        x_coords = [lm.x * w for lm in face_landmarks.landmark]
        y_coords = [lm.y * h for lm in face_landmarks.landmark]
        bbox_x = int(min(x_coords))
        bbox_y = int(min(y_coords))
        bbox_w = int(max(x_coords) - bbox_x)
        bbox_h = int(max(y_coords) - bbox_y)
        
        # Convert ROI coords back to full frame
        x_offset, y_offset = roi_offset
        self._last_face_bbox = (
            bbox_x + x_offset,
            bbox_y + y_offset,
            bbox_w,
            bbox_h
        )
        
        # Extract configured landmarks
        coords: Dict[str, Tuple[float, float]] = {}
        face_map = self._features.get("face", {})
        if not isinstance(face_map, dict):
            return {}
        
        for name, spec in face_map.items():
            if not isinstance(spec, dict):
                continue
            indices_raw = spec.get("indices")
            if not isinstance(indices_raw, list):
                continue
            valid_indices = [int(i) for i in indices_raw if isinstance(i, int)]
            if not valid_indices:
                continue
            
            # Average landmark positions (normalized coords)
            xs = [face_landmarks.landmark[i].x for i in valid_indices]
            ys = [face_landmarks.landmark[i].y for i in valid_indices]
            avg_x = float(sum(xs) / len(xs))
            avg_y = float(sum(ys) / len(ys))
            
            # Convert from ROI space to full frame space
            roi_h, roi_w = frame_rgb.shape[:2]
            full_x = (avg_x * roi_w + x_offset) / self.frame_w
            full_y = (avg_y * roi_h + y_offset) / self.frame_h
            
            # Apply EMA smoothing
            coords[name] = self._smooth(name, (full_x, full_y))
        
        return coords
    
    def _process_hands(
        self,
        frame_rgb: np.ndarray,
        roi_offset: Tuple[int, int] = (0, 0)
    ) -> Dict[str, Tuple[float, float]]:
        """
        Extract hand landmarks using MediaPipe Hands.
        Returns normalized (x, y) coordinates [0, 1] in full-frame space.
        """
        if not self._hand_detector:
            return {}
        
        results = self._hand_detector.process(frame_rgb)
        if not results.multi_hand_landmarks:
            return {}
        
        coords: Dict[str, Tuple[float, float]] = {}
        hands_map = self._features.get("hands", {})
        if not isinstance(hands_map, dict):
            return {}
        
        # Process each detected hand
        for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            handedness = results.multi_handedness[hand_idx].classification[0].label
            
            for name, spec in hands_map.items():
                if not isinstance(spec, dict):
                    continue
                indices_raw = spec.get("indices")
                if not isinstance(indices_raw, list):
                    continue
                valid_indices = [int(i) for i in indices_raw if isinstance(i, int)]
                if not valid_indices:
                    continue
                
                # Get landmark position
                idx = valid_indices[0]  # Hands typically use single index
                lm = hand_landmarks.landmark[idx]
                
                # Convert from ROI space to full frame space
                roi_h, roi_w = frame_rgb.shape[:2]
                x_offset, y_offset = roi_offset
                full_x = (lm.x * roi_w + x_offset) / self.frame_w
                full_y = (lm.y * roi_h + y_offset) / self.frame_h
                
                # Apply EMA smoothing
                smooth_name = f"{name}_{handedness}"
                coords[smooth_name] = self._smooth(smooth_name, (full_x, full_y))
        
        return coords

    def _smooth(self, name: str, value: Tuple[float, float]) -> Tuple[float, float]:
        prev = self._ema.get(name)
        if not prev:
            self._ema[name] = value
            return value
        smoothed = (
            self._alpha * value[0] + (1 - self._alpha) * prev[0],
            self._alpha * value[1] + (1 - self._alpha) * prev[1],
        )
        self._ema[name] = smoothed
        return smoothed

    def _draw_debug_overlays(
        self,
        frame: np.ndarray,
        landmarks: Dict[str, Tuple[float, float]],
        hand_landmarks: Dict[str, Tuple[float, float]],
        ar_anchors: List[Dict[str, Any]],
    ) -> None:
        """Draw detection overlays on frame for debug preview"""
        h, w = frame.shape[:2]
        
        # Draw face landmarks (green dots)
        for name, (nx, ny) in landmarks.items():
            if 'hand' not in name.lower():  # Skip hand landmarks
                x, y = int(nx * w), int(ny * h)
                cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)
        
        # Draw face bounding box if we have landmarks
        if landmarks:
            # Find bounding box of all face landmarks
            face_points = [(int(nx * w), int(ny * h)) for name, (nx, ny) in landmarks.items() if 'hand' not in name.lower()]
            if face_points:
                xs = [p[0] for p in face_points]
                ys = [p[1] for p in face_points]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, "FACE DETECTED", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Draw hand landmarks (blue dots)
        for name, (nx, ny) in hand_landmarks.items():
            x, y = int(nx * w), int(ny * h)
            cv2.circle(frame, (x, y), 5, (255, 0, 0), -1)
        
        # Draw hand bounding box
        if hand_landmarks:
            hand_points = [(int(nx * w), int(ny * h)) for nx, ny in hand_landmarks.values()]
            if hand_points:
                xs = [p[0] for p in hand_points]
                ys = [p[1] for p in hand_points]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(frame, "HAND", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # Draw ArUco markers (red squares)
        for anchor in ar_anchors:
            center = anchor.get("center_px")
            if isinstance(center, dict) and "x" in center and "y" in center:
                cx, cy = int(center["x"]), int(center["y"])
                marker_id = anchor.get("id", "?")
                cv2.circle(frame, (cx, cy), 20, (0, 0, 255), 3)
                cv2.putText(frame, f"ArUco #{marker_id}", (cx + 25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Draw status overlay
        status_y = 30
        cv2.rectangle(frame, (0, 0), (300, 120), (0, 0, 0), -1)
        cv2.putText(frame, f"FPS: {self.health.fps:.1f}", (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Face: {'YES' if landmarks else 'NO'}", (10, status_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Hands: {'YES' if hand_landmarks else 'NO'}", (10, status_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"ArUco: {len(ar_anchors)}", (10, status_y + 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    def _build_shapes(
        self,
        landmarks: Dict[str, Tuple[float, float]],
        width: int,
        height: int,
        ar_anchors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Build overlay shapes based on current routine step and detected landmarks.
        """
        shapes: List[Dict[str, Any]] = []
        routine = self.session.routine_id or ""
        current_step = self.session.step_index
        routine_steps = self._tasks.get(routine, []) if isinstance(self._tasks, dict) else []
        active_step = None
        if isinstance(routine_steps, list) and 0 <= current_step < len(routine_steps):
            candidate = routine_steps[current_step]
            if isinstance(candidate, dict):
                active_step = candidate

        if active_step:
            # Draw rings at target anchors for current step
            anchors = active_step.get("target_anchors", [])
            if not isinstance(anchors, list):
                anchors = []
            for anchor_name in anchors:
                if anchor_name in landmarks:
                    px = landmarks[anchor_name][0] * width
                    py = landmarks[anchor_name][1] * height
                    shapes.append(
                        {
                            "kind": "ring",
                            "anchor": {"pixel": {"x": px, "y": py}},
                            "radius_px": 90,
                            "accent": "info",
                        }
                    )
            
            # Optional: Draw arrow from hand to mouth target
            if self.settings.hands and "hand_right_index_tip_Right" in landmarks:
                # Find primary mouth target
                mouth_target = None
                for anchor_name in anchors:
                    if "mouth" in anchor_name and anchor_name in landmarks:
                        mouth_target = anchor_name
                        break
                
                if mouth_target:
                    hand_x = landmarks["hand_right_index_tip_Right"][0] * width
                    hand_y = landmarks["hand_right_index_tip_Right"][1] * height
                    mouth_x = landmarks[mouth_target][0] * width
                    mouth_y = landmarks[mouth_target][1] * height
                    shapes.append(
                        {
                            "kind": "arrow",
                            "anchor": {"pixel": {"x": hand_x, "y": hand_y}},
                            "to": {"pixel": {"x": mouth_x, "y": mouth_y}},
                        }
                    )
        else:
            # No active routine: keep ring anchored to face if available so it follows the user.
            focus_anchor = None
            if "mouth_center" in landmarks:
                focus_anchor = landmarks["mouth_center"]
            elif landmarks:
                # Average all face-related landmarks (skip hand entries)
                face_points = [
                    coords
                    for name, coords in landmarks.items()
                    if "hand" not in name.lower()
                ]
                if face_points:
                    avg_x = sum(pt[0] for pt in face_points) / len(face_points)
                    avg_y = sum(pt[1] for pt in face_points) / len(face_points)
                    focus_anchor = (avg_x, avg_y)

            if focus_anchor:
                shapes.append(
                    {
                        "kind": "ring",
                        "anchor": {
                            "pixel": {
                                "x": focus_anchor[0] * width,
                                "y": focus_anchor[1] * height,
                            }
                        },
                        "radius_px": 110,
                        "accent": "info",
                    }
                )

        # Add ArUco marker badges
        # (Badge creation moved to guidance logic)
        
        return shapes

    def _build_tool_guidance(
        self,
        ar_anchors: List[Dict[str, Any]],
        landmarks: Dict[str, Tuple[float, float]],
        width: int,
        height: int,
    ) -> List[Dict[str, Any]]:
        shapes: List[Dict[str, Any]] = []
        for anchor in ar_anchors:
            aruco_id = anchor.get("aruco_id")
            center = anchor.get("center_px")
            if not isinstance(center, dict) or not isinstance(aruco_id, int):
                continue
            tool_spec = self._tools.get(str(aruco_id))
            if not isinstance(tool_spec, dict):
                continue
            snap_to = tool_spec.get("snap_to")
            tolerances = tool_spec.get("tolerances", {})
            dist_tol = float(tolerances.get("dist_px", 120.0))
            yaw_tol = float(tolerances.get("yaw_deg", 25.0))
            pitch_tol = float(tolerances.get("pitch_deg", 25.0))
            target = None
            if isinstance(snap_to, str) and snap_to in landmarks:
                tx = landmarks[snap_to][0] * width
                ty = landmarks[snap_to][1] * height
                target = (tx, ty)
            cx = float(center.get("x", 0.0))
            cy = float(center.get("y", 0.0))
            state = "SEARCHING"
            if target is None:
                state = "SEARCHING"
            else:
                dx = target[0] - cx
                dy = target[1] - cy
                dist = (dx * dx + dy * dy) ** 0.5
                if dist <= dist_tol:
                    state = "GOOD"
                else:
                    state = "ALIGNING"
                # Pose tilt hints if pose data available
                if "yaw_deg" in anchor and "pitch_deg" in anchor and state == "GOOD":
                    yaw = abs(float(anchor.get("yaw_deg", 0.0)))
                    pitch = abs(float(anchor.get("pitch_deg", 0.0)))
                    if yaw > yaw_tol or pitch > pitch_tol:
                        state = "ALIGNING"  # degrade to aligning with tilt hint
            # Debounce transitions
            prev = self._aruco_last_state.get(aruco_id)
            now = time.time()
            if prev != state:
                # Only accept change if stable for debounce window
                since = self._aruco_state_since.get(aruco_id, now)
                if (now - since) < self._aruco_debounce_s:
                    state = prev if prev else state
                else:
                    self._aruco_state_since[aruco_id] = now
            self._aruco_last_state[aruco_id] = state

            # Build shapes based on state
            if state == "SEARCHING":
                # Ghost ring at target (if known) else center
                gx = target[0] if target else width / 2
                gy = target[1] if target else height / 2
                shapes.append(
                    {
                        "kind": "ring",
                        "anchor": {"pixel": {"x": gx, "y": gy}},
                        "radius_px": 70,
                        "accent": "neutral",
                    }
                )
                shapes.append(
                    {
                        "kind": "badge",
                        "anchor": {"pixel": {"x": gx, "y": gy - 110}},
                        "text": f"Find {tool_spec.get('name','tool')}",
                    }
                )
            elif state == "ALIGNING" and target is not None:
                # Arrow from marker to target
                shapes.append(
                    {
                        "kind": "arrow",
                        "anchor": {"pixel": {"x": cx, "y": cy}},
                        "to": {"pixel": {"x": target[0], "y": target[1]}},
                    }
                )
                # Optional tilt hint
                if "yaw_deg" in anchor and "pitch_deg" in anchor:
                    yaw = abs(float(anchor.get("yaw_deg", 0.0)))
                    pitch = abs(float(anchor.get("pitch_deg", 0.0)))
                    if yaw > yaw_tol:
                        hint = "Rotate"
                    elif pitch > pitch_tol:
                        hint = "Tilt"
                    else:
                        hint = "Align"
                else:
                    hint = "Align"
                shapes.append(
                    {
                        "kind": "badge",
                        "anchor": {"pixel": {"x": target[0], "y": target[1] - 120}},
                        "text": hint,
                    }
                )
            elif state == "GOOD" and target is not None:
                shapes.append(
                    {
                        "kind": "badge",
                        "anchor": {"pixel": {"x": target[0], "y": target[1]}},
                        "text": f"Hold {tool_spec.get('name','tool')} here",
                    }
                )
        return shapes

    def _build_hud(self) -> Dict[str, Any]:
        """Build HUD payload from current routine step."""
        routine = self.session.routine_id or ""
        steps = self._tasks.get(routine, []) if isinstance(self._tasks, dict) else []
        idx = self.session.step_index
        
        if not isinstance(steps, list) or idx >= len(steps):
            return {}
        
        step_candidate = steps[idx]
        if not isinstance(step_candidate, dict):
            return {}
        
        step = step_candidate
        hud = {
            "title": step.get("title"),
            "step": f"Step {idx + 1} of {len(steps)}",
            "subtitle": step.get("subtitle"),
            "time_left_s": step.get("min_time_s"),
            "max_time_s": step.get("min_time_s"),  # For progress bar calculation
            "hint": step.get("hint"),
        }
        return hud
    
    def _send_no_face_hint(self) -> None:
        """Send a hint message when no face is detected for a while."""
        hint_msg = {
            "type": "overlay.set",
            "shapes": [],
            "hud": {
                "title": "Position Yourself",
                "subtitle": "Move closer to camera",
                "hint": "Ensure good lighting",
            },
        }
        self.broadcast_fn(hint_msg)

    def refresh_cloud_limits(self) -> None:
        """Update cloud client rate limits from shared settings state."""
        if not self._cloud_client.enabled:
            return
        rps = getattr(self.settings, "cloud_rps", self._cloud_client.rps)
        timeout_s = getattr(self.settings, "cloud_timeout_s", self._cloud_client.timeout_s)
        min_interval_ms = getattr(self.settings, "cloud_min_interval_ms", self._cloud_client.min_interval_ms)
        self._cloud_client.update_limits(int(rps), float(timeout_s), int(min_interval_ms))

    def _resolve_cloud_future(self) -> None:
        if not self._cloud_future or not self._cloud_future.done():
            return
        try:
            result = self._cloud_future.result()
        except Exception as exc:  # pragma: no cover - defensive log
            LOGGER.debug("Cloud future error: %s", exc)
            result = None
        finally:
            self._cloud_future = None

        if result:
            self._cloud_latest = result
            self._cloud_last_latency_ms = float(result.get("latency_ms", self._cloud_last_latency_ms))
            self._cloud_last_confidence = float(result.get("confidence", self._cloud_last_confidence))
            self._cloud_last_ok = bool(result.get("ok", True))
        else:
            self._cloud_last_ok = False

    def _active_cloud_result(self) -> Optional[Dict[str, Any]]:
        if not self._cloud_latest:
            return None
        ts_ns_raw = self._cloud_latest.get("ts_ns")
        if isinstance(ts_ns_raw, (int, float)) and ts_ns_raw > 0:
            age_s = (time.time_ns() - int(ts_ns_raw)) / 1e9
            if age_s > self._cloud_result_ttl_s:
                return None
        return self._cloud_latest

    def _merge_cloud_landmarks(
        self,
        base: Dict[str, Tuple[float, float]],
        cloud_landmarks: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Tuple[float, float]]:
        if not isinstance(cloud_landmarks, dict):
            return base
        blended = dict(base)
        weight = confidence if confidence > 0 else 0.5
        weight = max(0.2, min(0.8, weight))
        for name, coords in cloud_landmarks.items():
            if not isinstance(coords, (list, tuple)) or len(coords) != 2:
                continue
            cx = float(coords[0])
            cy = float(coords[1])
            cx = min(1.0, max(0.0, cx))
            cy = min(1.0, max(0.0, cy))
            if name in blended:
                lx, ly = blended[name]
                target = (
                    lx * (1.0 - weight) + cx * weight,
                    ly * (1.0 - weight) + cy * weight,
                )
            else:
                target = (cx, cy)
            blended[name] = self._smooth(name, target)
        return blended

    def _submit_cloud_job(self, frame_rgb: np.ndarray) -> None:
        if not self._cloud_executor or self._cloud_future is not None:
            return
        bbox = self._last_face_bbox
        if bbox is None:
            frame_h, frame_w = frame_rgb.shape[:2]
            bbox = (0, 0, frame_w, frame_h)
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        roi_bytes = CloudVisionClient.roi_bytes(frame_bgr, bbox)
        if not roi_bytes:
            return
        self._cloud_future = self._cloud_executor.submit(self._cloud_client.detect_faces, roi_bytes)

    def _refresh_cloud_health(self) -> None:
        metrics = self._cloud_client.metrics()
        enabled = bool(metrics.get("enabled")) and self.settings.use_cloud
        self.health.cloud_enabled = enabled
        self.health.cloud_ok_count = int(metrics.get("ok_count", 0))
        self.health.cloud_fail_count = int(metrics.get("fail_count", 0))
        self.health.cloud_breaker_open = bool(metrics.get("breaker_open", False)) if enabled else False
        self.health.cloud_latency_ms = float(metrics.get("latency_ms", 0.0)) if enabled else 0.0
        self.health.cloud_last_ok_ns = metrics.get("last_ok_ns") if enabled else None

    def _log_latency(
        self,
        capture_ts: float,
        landmark_ts: float,
        overlay_ts: float,
        e2e_ms: float,
        cloud_latency_ms: float,
        cloud_confidence: float,
        cloud_ok: bool,
    ) -> None:
        """Append latency metrics to CSV log."""
        use_cloud = self.settings.use_cloud
        fps = self.health.fps
        record = (
            f"{capture_ts:.6f},{landmark_ts:.6f},{overlay_ts:.6f},{e2e_ms:.2f},{fps:.1f},"
            f"{int(use_cloud)},{cloud_latency_ms:.2f},{cloud_confidence:.2f},{int(cloud_ok)},"
            f"{int(self.health.cloud_breaker_open)}\n"
        )
        try:
            with LOGS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(record)
        except Exception as exc:
            LOGGER.warning("Failed to log latency: %s", exc)

    def _adapt_performance(self, e2e_ms: float) -> None:
        """Dynamically shed load to bring latency back toward target.

        Rules (hysteresis applied):
          - If latency > 1200ms: increase face stride up to 8, aruco stride up to 6, downscale face target to 640.
          - If latency > 600ms: face stride min 4, aruco stride min 4, face target 800.
          - If latency > 300ms: face stride min 2, aruco stride min 3, face target 960.
          - If latency < 180ms for 3000ms since last adapt: slowly relax (reduce strides, enlarge face target).
        """
        now_ns = time.time_ns()
        # Escalate
        if e2e_ms > 1200:
            self._face_frame_stride = max(self._face_frame_stride, 8)
            self._aruco_frame_stride = max(self._aruco_frame_stride, 6)
            self._face_target_w = min(self._face_target_w, 640)
            self._perf_last_adapt_ns = now_ns
        elif e2e_ms > 600:
            self._face_frame_stride = max(self._face_frame_stride, 4)
            self._aruco_frame_stride = max(self._aruco_frame_stride, 4)
            self._face_target_w = min(self._face_target_w, 800)
            self._perf_last_adapt_ns = now_ns
        elif e2e_ms > 300:
            self._face_frame_stride = max(self._face_frame_stride, 2)
            self._aruco_frame_stride = max(self._aruco_frame_stride, 3)
            self._face_target_w = min(self._face_target_w, 960)
            self._perf_last_adapt_ns = now_ns
        else:
            # Relax after sustained low latency
            since_ms = (now_ns - self._perf_last_adapt_ns) / 1e6
            if since_ms > 3000 and e2e_ms < 180:
                if self._face_frame_stride > 1:
                    self._face_frame_stride -= 1
                if self._aruco_frame_stride > 2:
                    self._aruco_frame_stride -= 1
                # Gradually restore resolution
                if self._face_target_w < 1280:
                    self._face_target_w = min(1280, int(self._face_target_w * 1.25))
                self._perf_last_adapt_ns = now_ns
        # Safety bounds
        self._face_frame_stride = min(max(self._face_frame_stride, 1), 8)
        self._aruco_frame_stride = min(max(self._aruco_frame_stride, 2), 8)
        self._face_target_w = min(max(self._face_target_w, 320), 1280)
        # Enforce baseline stride from settings (never go below user-requested value)
        baseline = 2
        try:
            baseline = int(getattr(self.settings, "aruco_stride", baseline))
        except Exception as exc:
            LOGGER.debug("Could not read aruco_stride for performance tuning: %s", exc)
            baseline = 2
        if baseline < 1:
            baseline = 1
        if self._aruco_frame_stride < baseline:
            self._aruco_frame_stride = baseline


# CLI entrypoint for standalone testing
if __name__ == "__main__":
    import signal
    import sys
    
    # Simple stub classes for standalone mode
    class StubSettings:
        use_cloud = False
        face = True
        hands = False
        aruco = False
    
    class StubSession:
        routine_id = "brush_teeth"
        step_index = 0
    
    class StubHealth:
        fps = 0.0
        latency_ms = 0.0
        camera = "off"
        lighting = "unknown"
    
    def stub_broadcast(msg: Dict[str, Any]) -> None:
        """Stub broadcast that just logs."""
        msg_type = msg.get("type", "unknown")
        shape_count = len(msg.get("shapes", []))
        hud = msg.get("hud", {})
        LOGGER.info(
            "Broadcast: type=%s shapes=%d hud_title=%s",
            msg_type,
            shape_count,
            hud.get("title", "N/A")
        )
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
        datefmt="%H:%M:%S"
    )
    
    LOGGER.info("Starting vision pipeline in standalone mode...")
    LOGGER.info("Press Ctrl+C to stop")
    
    settings = StubSettings()
    session = StubSession()
    health = StubHealth()
    
    # Create pipeline
    pipeline = VisionPipeline(
        broadcast_fn=stub_broadcast,
        settings=settings,
        session=session,
        health=health,
        camera_width=1280,
        camera_height=720,
        camera_fps=24,
        camera_device=0
    )
    
    # Handle graceful shutdown
    def signal_handler(sig: int, frame: Any) -> None:
        LOGGER.info("\nShutting down...")
        pipeline.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start pipeline
    pipeline.start()
    
    # Keep alive and print stats
    try:
        while True:
            time.sleep(2.0)
            LOGGER.info(
                "Stats: fps=%.1f latency=%.1fms camera=%s lighting=%s",
                health.fps,
                health.latency_ms,
                health.camera,
                health.lighting
            )
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()
        LOGGER.info("Vision pipeline stopped")