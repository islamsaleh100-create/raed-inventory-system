FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway / Render / Fly inject $PORT at runtime; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/v1/ready || exit 1

# Start the API directly on the platform-provided port. Database migrations
# should be executed as an explicit deploy step rather than blocking service
# startup and Railway healthchecks.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
