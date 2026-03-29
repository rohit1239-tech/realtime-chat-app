#!/usr/bin/env bash

set -euo pipefail

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Docker Compose is not installed. Install 'docker compose' or 'docker-compose' and try again."
  exit 1
fi

BUILD_ARGS=()
if [[ "${1:-}" == "--no-cache" ]]; then
  BUILD_ARGS+=(--no-cache)
fi

echo "Building application images..."
"${COMPOSE_CMD[@]}" build "${BUILD_ARGS[@]}"

echo "Starting services..."
"${COMPOSE_CMD[@]}" up -d

echo "Applying database migrations..."
"${COMPOSE_CMD[@]}" exec web python manage.py migrate

echo "Build complete."
echo "Application: http://localhost:8000"
