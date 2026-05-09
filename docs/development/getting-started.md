# Getting Started

This guide walks you through setting up the NatHacks Assistive Mirror codebase for local development.

## 1. System Requirements
- OS: Linux (Ubuntu/Debian recommended), macOS, or Windows via WSL2.
- Node.js: >= 18.18.0
- Python: 3.10 or 3.11
- Hardware: A working webcam (built-in or USB).

## 2. Backend Setup
The backend runs on Python and FastAPI. It relies on OpenCV and MediaPipe.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   # .venv\Scripts\activate   # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the development server:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

*Note on Mac/Windows:* If you encounter issues with camera permissions via OpenCV, ensure your terminal application is granted camera access in your OS privacy settings.

## 3. Frontend Setup
The project contains a modern Next.js 15 application.

1. Navigate to the root directory (or `/webapp` depending on your active branch):
   ```bash
   cd ..
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to `http://localhost:3000`.

## 4. Camera Calibration (Optional)
If you intend to use physical ArUco markers for positional tracking, you should calibrate your camera to get accurate distortion matrices.

1. Print a standard OpenCV checkerboard pattern.
2. Run the calibration script:
   ```bash
   python scripts/calibrate_cam.py
   ```
3. Hold the checkerboard in front of your camera in various orientations until calibration succeeds. The generated `camera_matrix.npy` will be saved to the `config/` directory.

## 5. Environment Variables
If you wish to enable the Google Cloud Vision fallback or Gemini AI Assistant:
1. Create a `.env` file in the `backend/` directory.
2. Provide your GCP credentials:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json
   GEMINI_API_KEY=your_api_key_here
   ```
