FROM python:3.12-slim AS backend

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium with system dependencies
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN python -m playwright install --with-deps chromium \
    && chmod -R 777 /opt/playwright

# ── Build frontend ───────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# ── Final image ──────────────────────────────────────────────────────────────
FROM backend AS final

# Copy backend application code
COPY backend/ /app/

# Copy built frontend into backend's static directory
COPY --from=frontend-builder /frontend/dist /app/static

# Create temp directory
RUN mkdir -p /tmp/postgrab

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /tmp/postgrab
USER appuser

ENV TEMP_DIR=/tmp/postgrab
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
