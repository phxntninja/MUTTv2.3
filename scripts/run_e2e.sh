#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.test.yml}

echo "Bringing up docker-compose test stack..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Waiting for services to be healthy..."
sleep 10

check() {
  curl -sf "$1" >/dev/null
}

for i in {1..60}; do
  if check http://localhost:8080/health && \
     check http://localhost:8084/health && \
     check http://localhost:8090/health && \
     check http://localhost:18083/health; then
    echo "Services are responding."
    break
  fi
  sleep 2
done

export E2E_COMPOSE=true
export E2E_API_KEY=${E2E_API_KEY:-test-ingest}

echo "Running E2E test..."
pytest -k test_e2e_flow -v

echo "Done. To bring the stack down:"
echo "  docker compose -f $COMPOSE_FILE down -v"

