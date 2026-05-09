# Vision Pipeline

The vision pipeline is the core mechanism that translates raw camera pixels into actionable user instructions and AR overlays.

## `vision_pipeline.py`

This module runs a background thread that continuously reads from the camera (via `camera_capture.py`) and passes frames through various detectors.

### MediaPipe Integration
The system relies on Google's MediaPipe Tasks API for low-latency, on-device inference.
- **HandLandmarker**: Extracts 21 3D coordinates per hand. These coordinates are used to detect where a user's hands are in relation to specific targets.
- **FaceLandmarker**: Extracts 478 facial landmarks. The pipeline calculates a "Face ROI" (Region of Interest) by looking at the bounding box of the face, and specifically targets the mouth (for brushing) or eyes/cheeks (for washing).

### Coordinate Mapping
MediaPipe returns normalized coordinates (`0.0` to `1.0`). The pipeline scales these based on the `detect_scale` configuration to generate the absolute `Anchor` coordinates sent to the frontend.

## Motion Heuristics
Rather than simply tracking position, the system validates tasks by tracking *motion over time*.
- A buffer of the last 30 frames is maintained for hand positions.
- **Circular Motion**: Calculated by measuring the directional vector changes of the hand. If the sum of directional angles exceeds a threshold within a time window, it's classified as circular (e.g., brushing teeth).
- **Vertical Motion**: Counted by analyzing Y-axis inflection points.

## Cloud Vision Fallback (`cloud_vision.py`)

If a specific routine requires object detection that MediaPipe cannot handle (e.g., verifying the user is holding toothpaste and not a hairbrush), the pipeline falls back to the Google Cloud Vision API.

### Circuit Breaker Pattern
To prevent API cost overruns and latency spikes, the Cloud Vision module implements a strict circuit breaker:
- **Rate Limiting**: Configured via `cloud_rps` (Requests Per Second) and `cloud_min_interval_ms`.
- **Circuit Breaker**: If the Cloud API returns successive errors or timeouts, the circuit "opens", falling back entirely to local heuristics to ensure the mirror remains responsive.
