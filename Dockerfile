# Dockerfile
ARG BASE=slim

ARG RESTIC_VERSION=0.19.1
FROM docker.io/restic/restic:${RESTIC_VERSION} AS restic-bin


FROM python:3.14-${BASE} AS builder
WORKDIR /app
# Create a dedicated venv for runtime dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m compileall -q /opt/venv

RUN /usr/local/bin/pip install --no-cache-dir pip-licenses
RUN PYTHONPATH=/opt/venv/lib/python3.14/site-packages \
    /usr/local/bin/pip-licenses \
        --with-license-file \
        --format=plain-vertical \
        --output-file=THIRD_PARTY_LICENSES.txt

######
# Stage 1: Sys image
# - System deps
# - Non-root user
######

# Debian
FROM python:3.14-slim AS slim
WORKDIR /app

# Install openssh-client and other system dependencies
# This needs to be done as root before switching to appuser
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -U -u 1000 appuser

# Alpine
FROM python:3.14-alpine AS alpine

# Install openssh-client and other system dependencies
# This needs to be done as root before switching to appuser
RUN apk add --no-cache openssh-client

# Create a non-root user and group
RUN addgroup -g 1000 appuser \
    && adduser -D -u 1000 -G appuser appuser

######
# Stage 2: Base image
# - Python deps (cached)
# - restic installed
######
# Second stage - your main image
FROM ${BASE} AS base

# Create virtualenv as root (standard 0755 permissions)
ENV VIRTUAL_ENV=/opt/venv
# RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy the requirements file and install dependencies
#COPY requirements.txt /tmp/requirements.txt
#RUN --mount=type=cache,target=/root/.cache/pip \
#    pip install --no-input -r /tmp/requirements.txt

# Copy installed Python packages and license notice from builder
COPY --from=builder /opt/venv /opt/venv

COPY --chmod=0755 entrypoint.sh /usr/local/bin/entrypoint.sh
# Use ENTRYPOINT with the script to run flask key generate before starting the application
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=src \
    HOME=/home/appuser \
    CONFIG_FILE=/app/config.toml

# Set the working directory in the container
WORKDIR /app

# Copy restic from downloader
# COPY --from=restic-downloader /restic /usr/local/bin/restic
COPY --from=restic-bin /usr/bin/restic /usr/local/bin/restic

COPY --from=builder /app/THIRD_PARTY_LICENSES.txt /app/THIRD_PARTY_LICENSES.txt

# Create mount points for logs/cache/repo (optional)
RUN mkdir -p /app/logs /app/cache /app/repo \
    && chmod 0755 /app/logs /app/cache /app/repo \
    && chown -R appuser:appuser /app /home/appuser

RUN mkdir -p /app/cache \
    && chown appuser:appuser /app/cache \
    && chmod 0775 /app/cache

######
# Stage 3: Development image (dev)
# - Use bind mount for source code
# - no COPY .
######
FROM base AS dev

WORKDIR /app

# We will mount the code directly and so not copying it into the container

USER appuser

ENV FLASK_DEBUG=1 \
    FLASK_APP=run:app

# Expose the port flask is running on (e.g., 5000)
EXPOSE 5000

# podman
# VOLUME ["/app/logs", "/app/cache", "/app/repo"]

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

######
# Stage 4: Production image (prod)
# - Copies app code
# - Gunicorn + entrypoint
######

FROM base AS prod

WORKDIR /app

# Copy the rest of the application code
COPY --chown=appuser:appuser --chmod=0755 . .
RUN python -m compileall -q .

USER appuser

# Expose the port Gunicorn is running on (e.g., 5000)
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
	CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=2)"
#	CMD curl -f http://localhost:5000/health || exit 1

# Document the mount points
# VOLUME ["/app/logs", "/app/cache", "/app/repo"]

ENV FLASK_DEBUG=0 \
    FLASK_APP=run:app

# Command to run the application using a production-ready server like Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers=2", "--threads=4", "--timeout=120", "--worker-tmp-dir=/dev/shm", "run:app"]
