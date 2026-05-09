# Frontend Architecture

The user interface of the Assistive Mirror is built as a Next.js 15 application utilizing the new App Router. It is designed to be highly responsive, accessible, and capable of rendering 60 FPS Canvas animations alongside standard DOM elements.

## Core Technologies

- **Framework**: Next.js 15 (React 19 RC)
- **State Management**: Zustand
- **Styling**: Tailwind CSS, class-variance-authority (cva)
- **Components**: Radix UI primitives for accessible, unstyled interactive components (Tabs, Dialogs, Progress bars).
- **Icons**: Lucide React
- **Data Fetching**: TanStack Query (React Query)

## Application Structure

- `app/layout.tsx`: Main application shell. Includes global providers (Zustand store context, QueryClient).
- `app/mirror/page.tsx`: The primary "Smart Mirror" interface. This page operates in full-screen, removing standard navigation, to serve as the default MagicMirror view.
- `app/dashboard/page.tsx`: Clinician or caregiver dashboard to configure routines, track patient progress, and view analytics.
- `app/practice/page.tsx`: A sandboxed environment for users to practice specific motions (e.g., circular brushing) without the pressure of a timed routine.

## The AR Overlay Engine

The standout feature of the frontend is the AR (Augmented Reality) Overlay Engine.
Rather than manipulating DOM elements (which is slow and memory-intensive at 30+ updates per second), the app uses an HTML5 `<canvas>` positioned absolutely over the user's camera feed or mirror reflection.

### Render Loop
1. The `useWebSocket` hook listens to `ws://localhost:8000/ws`.
2. When a `"overlay.set"` message is received, it pushes the `Shape[]` array to the Zustand store.
3. A `requestAnimationFrame` loop continuously clears and redraws the canvas based on the latest shapes.

### Responsive Scaling
The backend sends coordinates normalized to the camera's resolution. The frontend must map these to the dynamic viewport size. The canvas includes `ResizeObserver` logic to maintain an internal coordinate matrix, ensuring that an AR arrow pointing to the mouth remains anchored exactly on the mouth regardless of window resizing.

## MagicMirror Embedding

The frontend includes a specific build script (`npm run build:mm`) which creates a static export. The MagicMirror wrapper (`MMM-AssistiveCoach`) loads `index.html` within an `<iframe>`.

### CSS Considerations for Mirrors
- The background is explicitly set to `transparent` or pure black (`#000000`). On a two-way mirror, pure black becomes completely transparent, revealing the reflection behind the glass.
- High-contrast, thick typography (Slate 900 or white, depending on the theme) ensures readability against the physical reflection.
- `prefers-reduced-motion` is actively respected; if the backend signals `reduce_motion=true` (or the OS requests it), all non-essential CSS transitions and Canvas particle effects are disabled.
