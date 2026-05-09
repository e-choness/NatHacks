# Testing Guide

Quality assurance for the NatHacks Assistive Mirror spans both Python backend tests and TypeScript frontend tests.

## Backend Testing (Pytest)

We use `pytest` for the backend logic, particularly for the vision pipeline thresholds, task system progressions, and API endpoints.

### Running Backend Tests
Ensure your virtual environment is activated, then run:

```bash
cd backend
python -m pytest tests/ -v
```

### Key Test Areas
- **Task System (`test_task_system.py`)**: Asserts that `TaskSession` correctly tracks step progression, verifies motion requirements, and returns the expected `HUDPayload`.
- **Vision Pipeline (`test_vision_pipeline.py`)**: Mocks OpenCV frames and tests if MediaPipe callbacks trigger correctly without throwing memory leaks.

## Frontend Testing (Vitest & React Testing Library)

The Next.js application uses `vitest` for fast execution and `@testing-library/react` for component testing.

### Running Frontend Tests
```bash
# In the root or webapp directory
npm run test
```

### Key Test Areas
- **AR Overlay Rendering**: Tests that coordinate mapping functions properly translate backend absolute coordinates to the local canvas `width`/`height`.
- **State Store**: Validates `zustand` persistence and action dispatches.

## Manual & Integration Testing

Because this project heavily relies on real-time webcam data and physical motion, automated tests cannot cover 100% of the use cases.
When adding a new feature:
1. **Mock Camera**: Use the backend's mocked video feed feature (if available) or hold up reference images (like `sample_human_face.jpeg`) to the webcam.
2. **Latency Check**: Monitor the `HealthState` diagnostic tab on the frontend. The `latency_ms` should remain under 150ms. High latency indicates blocking code in the WebSocket loop or vision processing thread.
3. **MagicMirror Validation**: Run `npm run build:mm` and test the output iframe within a local MagicMirror² instance to ensure CSP rules or CSS scaling do not break the UI.
