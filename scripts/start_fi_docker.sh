#!/usr/bin/env bash

# Start Fuzz Introspector in a background Docker container using the
# main `logicfuzz` image. This script is idempotent: if a container
# named `logicfuzz-fi` is already running, it prints a message and exits.

set -euo pipefail

CONTAINER_NAME="logicfuzz-fi"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Fuzz Introspector container '${CONTAINER_NAME}' is already running."
  exit 0
fi

echo "Starting Fuzz Introspector container '${CONTAINER_NAME}' on port 8080..."

docker run -d --rm \
  --name "${CONTAINER_NAME}" \
  -p 8080:8080 \
  -v "$PWD":/experiment \
  -w /experiment \
  logicfuzz \
  bash report/launch_introspector.sh --source benchmark

echo "Fuzz Introspector started. Check health with:"
echo "  curl http://127.0.0.1:8080/api/healthz"


