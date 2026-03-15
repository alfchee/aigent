# NaviBot 2.0 (The Phoenix) - Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for Playwright, SQLite, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (if needed, though 'browserless' is preferred in PRD)
RUN playwright install-deps
RUN playwright install chromium

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Start command (using Uvicorn)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
