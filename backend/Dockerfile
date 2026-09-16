FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-telu \
    fonts-deva \
    fonts-taml \
    fonts-knda \
    fonts-beng \
    fonts-mlym \
    fonts-arabeyes \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium with system dependencies
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN python -m playwright install --with-deps chromium \
    && chmod -R 777 /opt/playwright

# Copy application code
COPY . .

# Create temp directory
RUN mkdir -p /tmp/postgrab

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /tmp/postgrab
USER appuser

ENV TEMP_DIR=/tmp/postgrab
ENV PORT=8000

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
