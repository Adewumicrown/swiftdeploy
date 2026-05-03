# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.12-alpine AS builder

WORKDIR /install

COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-alpine

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy application source
COPY app/ .

# Give appuser ownership of workdir
RUN chown -R appuser:appgroup /app

USER appuser

# Environment defaults (overridden by docker-compose)
ENV MODE=stable \
    APP_VERSION=1.0.0 \
    APP_PORT=3000

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/healthz')" || exit 1

# Log to stdout/stderr
CMD ["/bin/sh", "-c", "exec gunicorn --bind 0.0.0.0:${APP_PORT} --workers 2 --timeout 60 --access-logfile - --error-logfile - main:app"]
