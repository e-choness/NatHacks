"""
ArUco detection and optional pose estimation utilities with lightweight smoothing.
Compatible with OpenCV 3.4+/4.x aruco APIs.
"""
from __future__ import annotations

import importlib
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import logging

LOGGER = logging.getLogger("assistivecoach.aruco")


# --- Camera intrinsics loading (single-attempt cache) -------------------------

_INTRINSICS_TRIED = False
_INTRINSICS_OK = False
_K: Optional[np.ndarray] = None
_DIST: Optional[np.ndarray] = None
_INTRINSICS_ERR: Optional[str] = None
_POSE_WARNED = False


def load_camera_intrinsics(path: str = "config/camera_intrinsics.yml") -> Tuple[Optional[np.ndarray], Optional[np.ndarray], bool, Optional[str]]:
    global _INTRINSICS_TRIED, _INTRINSICS_OK, _K, _DIST, _INTRINSICS_ERR
    if _INTRINSICS_TRIED:
        return _K, _DIST, _INTRINSICS_OK, _INTRINSICS_ERR
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    try:
        if not fs.isOpened():
            _INTRINSICS_OK = False
            # Prefer a clear error message for health reporting
            _INTRINSICS_ERR = "file not found"
            return None, None, _INTRINSICS_OK, _INTRINSICS_ERR
        K = fs.getNode("K").mat()
        dist = fs.getNode("dist").mat()
        if K is None or dist is None:
            _INTRINSICS_OK = False
            _INTRINSICS_ERR = "missing K/dist nodes"
            return None, None, _INTRINSICS_OK, _INTRINSICS_ERR
        _K = K.astype(np.float64)
        _DIST = dist.astype(np.float64)
        _INTRINSICS_OK = True
        _INTRINSICS_ERR = None
        return _K, _DIST, _INTRINSICS_OK, _INTRINSICS_ERR
    except Exception as exc:  # pragma: no cover
        _INTRINSICS_OK = False
        _INTRINSICS_ERR = str(exc)
        return None, None, _INTRINSICS_OK, _INTRINSICS_ERR
    finally:
        _INTRINSICS_TRIED = True
        fs.release()


def _get_dictionary(dict_name: str = "DICT_5X5_250") -> Any:
    aruco = importlib.import_module("cv2.aruco")
    name = dict_name.upper()
    const = getattr(aruco, name, getattr(aruco, "DICT_5X5_250"))
    get_dict = getattr(aruco, "getPredefinedDictionary", None)
    if get_dict is None:
        raise ImportError("cv2.aruco.getPredefinedDictionary not available")
    return get_dict(const)


def _detect_raw(gray: np.ndarray, dictionary: Any) -> Tuple[List[np.ndarray], Optional[np.ndarray]]:
    aruco = importlib.import_module("cv2.aruco")
    # Support both legacy detectMarkers and new ArucoDetector APIs
    dp_create = getattr(aruco, "DetectorParameters_create", None)
    if dp_create is not None:
        params = dp_create()
    else:
        DP = getattr(aruco, "DetectorParameters", None)
        params = DP() if DP is not None else None
    aruco_detector_cls = getattr(aruco, "ArucoDetector", None)
    if aruco_detector_cls is not None and params is not None:
        detector = aruco_detector_cls(dictionary, params)
        corners, ids, _ = detector.detectMarkers(gray)
    else:
        detectMarkers = getattr(aruco, "detectMarkers", None)
        if detectMarkers is None:
            return [], None
        corners, ids, _ = detectMarkers(gray, dictionary, parameters=params)
    return list(corners) if corners is not None else [], ids


def detect_markers(frame_bgr: np.ndarray, dict_name: str = "DICT_5X5_250") -> List[Dict[str, Any]]:
    """Detect ArUco markers and return id, corners, and center_px.
    Returns a list of dicts: {"id": int, "corners": [(x,y)*4], "center_px": {"x": float, "y": float}}
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return []
    try:
        importlib.import_module("cv2.aruco")
    except ImportError as exc:
        raise ImportError("cv2.aruco module not available; install opencv-contrib-python") from exc

    dictionary = _get_dictionary(dict_name)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    corners, ids = _detect_raw(gray, dictionary)
    results: List[Dict[str, Any]] = []
    if ids is None or len(ids) == 0:
        return results
    for i, cid in enumerate(ids.flatten().tolist()):
        pts = corners[i].reshape(-1, 2)
        cx = float(np.mean(pts[:, 0]))
        cy = float(np.mean(pts[:, 1]))
        results.append(
            {
                "id": int(cid),
                "corners": [(float(x), float(y)) for x, y in pts],
                "center_px": {"x": cx, "y": cy},
            }
        )
    return results


def _euler_from_rvec(rvec: np.ndarray) -> Tuple[float, float, float]:
    R, _ = cv2.Rodrigues(rvec)
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    singular = sy < 1e-6
    if not singular:
        x = np.arctan2(R[2, 1], R[2, 2])
        y = np.arctan2(-R[2, 0], sy)
        z = np.arctan2(R[1, 0], R[0, 0])
    else:
        x = np.arctan2(-R[1, 2], R[1, 1])
        y = np.arctan2(-R[2, 0], sy)
        z = 0.0
    # Convert to degrees (roll=x, pitch=y, yaw=z)
    return (np.degrees(z), np.degrees(y), np.degrees(x))  # yaw, pitch, roll


def estimate_pose(
    markers: List[Dict[str, Any]],
    K: Optional[np.ndarray],
    dist: Optional[np.ndarray],
    marker_size_m: float = 0.02,
) -> List[Dict[str, Any]]:
    if K is None or dist is None or not hasattr(cv2, "aruco"):
        return markers
    if not markers:
        return markers

    # Use OpenCV helper for single-marker pose
    for m in markers:
        # cv2.aruco.estimatePoseSingleMarkers returns rvecs/tvecs for each marker
        pts = np.array(m["corners"], dtype=np.float64).reshape(1, -1, 2)
        try:
            aruco = importlib.import_module("cv2.aruco")
            epsm = getattr(aruco, "estimatePoseSingleMarkers", None)
            if epsm is None:
                continue
            rvecs, tvecs, _obj = epsm(pts, marker_size_m, K, dist)
        except Exception:
            continue
        if rvecs is None or tvecs is None:
            continue
        rvec = rvecs[0].reshape(3, 1)
        tvec = tvecs[0].reshape(3, 1)
        yaw, pitch, roll = _euler_from_rvec(rvec)
        m["rvec"] = rvec.astype(float).tolist()
        m["tvec"] = tvec.astype(float).tolist()
        m["yaw_deg"] = float(yaw)
        m["pitch_deg"] = float(pitch)
        m["roll_deg"] = float(roll)
    return markers


# --- Lightweight smoothing and cached detection for subsampling ---------------

_alpha = 0.4
_prev_center: Dict[int, Tuple[float, float]] = {}
_prev_angles: Dict[int, Tuple[float, float, float]] = {}
_last_ts = 0.0
_min_interval_s = 0.065  # ~15 Hz
_last_anchors: List[Dict[str, Any]] = []
_k_runtime: Optional[np.ndarray] = None
_dist_runtime: Optional[np.ndarray] = None


def _smooth_pair(key: int, value: Tuple[float, float]) -> Tuple[float, float]:
    prev = _prev_center.get(key)
    if prev is None:
        _prev_center[key] = value
        return value
    sx = _alpha * value[0] + (1 - _alpha) * prev[0]
    sy = _alpha * value[1] + (1 - _alpha) * prev[1]
    _prev_center[key] = (sx, sy)
    return _prev_center[key]


def _smooth_angles(key: int, value: Tuple[float, float, float]) -> Tuple[float, float, float]:
    prev = _prev_angles.get(key)
    if prev is None:
        _prev_angles[key] = value
        return value
    sx = _alpha * value[0] + (1 - _alpha) * prev[0]
    sy = _alpha * value[1] + (1 - _alpha) * prev[1]
    sz = _alpha * value[2] + (1 - _alpha) * prev[2]
    _prev_angles[key] = (sx, sy, sz)
    return _prev_angles[key]


def detect_aruco_anchors(
    frame_rgb: np.ndarray,
    pose_enabled: bool = True,
    intrinsics_path: str = "config/camera_intrinsics.yml",
    marker_size_m: float = 0.032,
    dict_name: str = "DICT_5X5_250",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Convenience wrapper used by the pipeline.
    - Subsamples detection rate (~15 Hz) and returns last anchors in between calls.
    - Applies EMA to center and (if present) Euler angles.
    - Adds fields used by the pipeline overlay logic: {"aruco_id", "center_px", optionally yaw/pitch/roll}.
    Returns: (anchors, meta)
      meta = {"pose_enabled": bool, "pose_available": bool, "intrinsics_error": str|None}
    """
    global _last_ts, _last_anchors, _k_runtime, _dist_runtime, _POSE_WARNED
    now = time.time()
    if (now - _last_ts) < _min_interval_s and _last_anchors:
        # Recompute meta without re-detecting
        _, _, ok, err = load_camera_intrinsics(intrinsics_path)
        meta = {
            "pose_enabled": bool(pose_enabled),
            "pose_available": bool(pose_enabled and ok),
            "intrinsics_error": (None if ok else err),
        }
        return _last_anchors, meta
    _last_ts = now

    try:
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        frame_bgr = frame_rgb

    try:
        markers = detect_markers(frame_bgr, dict_name=dict_name)
    except ImportError:
        # aruco not available; surface empty list (pipeline handles gracefully)
        _last_anchors = []
        meta = {"pose_enabled": bool(pose_enabled), "pose_available": False, "intrinsics_error": "aruco not available"}
        return _last_anchors, meta
    # Try loading intrinsics once (cached at module level)
    k, dist, ok, err = load_camera_intrinsics(intrinsics_path)
    if ok:
        _k_runtime, _dist_runtime = k, dist
    pose_available = bool(pose_enabled and ok)
    if pose_enabled and not ok and not _POSE_WARNED:
        LOGGER.warning("Pose requested but intrinsics unavailable; proceeding in 2D mode: %s", err)
        _POSE_WARNED = True
    if pose_available and _k_runtime is not None and _dist_runtime is not None:
        markers = estimate_pose(markers, _k_runtime, _dist_runtime, marker_size_m=marker_size_m)

    anchors: List[Dict[str, Any]] = []
    for m in markers:
        mid = int(m["id"])  # type: ignore[index]
        cx = float(m["center_px"]["x"])  # type: ignore[index]
        cy = float(m["center_px"]["y"])  # type: ignore[index]
        sx, sy = _smooth_pair(mid, (cx, cy))
        anchor: Dict[str, Any] = {
            "aruco_id": mid,
            "center_px": {"x": sx, "y": sy},
        }
        if "yaw_deg" in m and "pitch_deg" in m and "roll_deg" in m:
            yaw, pitch, roll = _smooth_angles(mid, (float(m["yaw_deg"]), float(m["pitch_deg"]), float(m["roll_deg"])) )
            anchor.update({
                "yaw_deg": yaw,
                "pitch_deg": pitch,
                "roll_deg": roll,
            })
        anchors.append(anchor)

    _last_anchors = anchors
    meta = {
        "pose_enabled": bool(pose_enabled),
        "pose_available": pose_available,
        "intrinsics_error": (None if pose_available else err),
    }
    return anchors, meta