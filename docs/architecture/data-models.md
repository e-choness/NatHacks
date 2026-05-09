# Core Data Models

This document outlines the primary Pydantic models used to serialize data between the FastAPI backend and the Next.js frontend over WebSockets and REST.

## Core Overlay Models

### `Anchor`
Defines a specific coordinate or targeted body part to lock an AR overlay onto.
- `landmark` (str, optional): Name of the tracked landmark (e.g., "index_finger_tip", "mouth").
- `aruco_id` (int, optional): ID of a physical ArUco marker.
- `pixel` (Dict[str, float], optional): Hardcoded X/Y coordinates on the screen.

### `Shape`
Represents a geometric or informational element to be rendered on the frontend canvas.
- `kind` (str): Type of shape (`"ring"`, `"arrow"`, `"badge"`).
- `anchor` (Anchor): The primary anchor point for the shape.
- `to` (Anchor, optional): The target anchor (required for `"arrow"` types).
- `radius_px` (int, optional): Size of the shape.
- `text` (str, optional): Text to display inside or alongside the shape.
- `accent` (str, optional): Styling hint (e.g., color variant).

### `HUDPayload`
Heads-Up Display data containing state about the current routine step.
- `title` (str): Task title (e.g., "Brush Teeth").
- `step` (str): Current step string (e.g., "Step 1 of 4").
- `time_left_s` (int): Remaining time for the current task.
- `max_time_s` (int): Total expected time.
- `progress` (float): Percentage (0.0 - 1.0) of task completion based on motion analysis.
- `instruction` / `hint` (str): Textual instructions for the user.

### `OverlayMessage`
The main payload broadcast over WebSockets.
- `type` (str): Type of message (`"overlay.set"`, `"status"`, `"tts"`, `"safety.alert"`).
- `hud` (HUDPayload, optional): Encapsulated HUD state.
- `shapes` (List[Shape], optional): Array of AR shapes to render.
- `camera`, `lighting`, `fps`: System health diagnostic metrics.

## State Models

### `HealthState`
Tracks the internal health and performance metrics of the computer vision pipeline.
- `camera` (str): Camera state (`"on"`, `"off"`, `"error"`).
- `fps` (float): Processing speed.
- `latency_ms` (float): Pipeline latency.
- `cloud_enabled` (bool): Whether Google Cloud fallback is active.

### `SessionState`
Tracks the user's active routine progress.
- `patient_id` (str, optional): Active user profile.
- `routine_id` (str, optional): Active task sequence ID.
- `step_index` (int): Current zero-indexed step in the routine.
- `started_at` (datetime): Initial launch timestamp.

### `SettingsPayload`
Configuration payload sent from the frontend to tune backend behavior.
- `face` / `hands` / `aruco` (bool): Toggles for specific vision pipelines.
- `reduce_motion` (bool): Accessibility toggle to suppress excess animations.
- `cloud_rps` (int): Rate limiting for Cloud Vision API fallback.
