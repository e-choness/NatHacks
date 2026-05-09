# Stage 1: Build & Test
FROM python:3.10-slim AS test-runner

WORKDIR /app

# Install system dependencies for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
# Install dependencies, including test frameworks
RUN pip install --no-cache-dir -r requirements.txt pytest httpx

COPY backend/ .

# Stage 2: Production
FROM python:3.10-slim AS production

WORKDIR /app

# System dependencies for OpenCV and healthcheck
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root user for security (Least Privilege)
RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
