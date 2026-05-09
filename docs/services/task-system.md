# Task & Session System

The `task_system.py` module orchestrates the logical flow of user routines. It defines what actions a user needs to perform, tracks their progress, and determines when to advance to the next step.

## Task Definitions (`tasks.json`)

Routines are defined declaratively in JSON files (e.g., `config/tasks.json`). Each routine consists of a series of "Steps". 

A step definition includes:
- `title` / `subtitle`: User-facing text.
- `min_time_s`: Minimum duration the user must perform the action before advancing.
- `hint`: Textual guidance.
- `voice_prompt`: Spoken instructions triggered when the step begins.
- **Validation Criteria**: What computer vision heuristics are required (e.g., `target_zone="mouth"`, `motion_type="circular"`).

## `TaskSession` Class

When a user begins a routine via `POST /tasks/{task_id}/start`, a `TaskSession` object is instantiated.

### Responsibilities:
1. **State Tracking**: Knows which step is currently active and how much time remains.
2. **Progress Calculation**: Receives raw heuristic data from the `vision_pipeline` (e.g., "hand is near mouth and moving circularly") and updates the step's completion percentage (0.0 to 1.0).
3. **Payload Generation**: Converts the current state into a `HUDPayload` and generates contextual `Shape` arrays (like progress rings and arrows) to be broadcast over WebSockets.

### Step Advancement
A step is only considered complete when:
1. `min_time_s` has elapsed.
2. The heuristic progress score reaches `100%`.

Once complete, `advance_step()` is called. If there are no steps remaining, the task concludes with a congratulatory TTS prompt and the HUD is cleared.
