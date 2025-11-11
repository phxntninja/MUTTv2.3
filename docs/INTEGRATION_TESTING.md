Integration Testing (docker-compose)

Overview
- A lightweight compose stack is provided to run a smoke end-to-end test locally.
- Components: Redis, Postgres (preloaded schema), Vault (dev), Vault setup job, Mock Moog, Ingestor, Alerter, Forwarder, Web UI.

Files
- `docker-compose.test.yml`: defines the stack
- `scripts/run_e2e.sh`: builds/starts services, waits for health, runs the smoke test
- `services/mock_moog.py`: mock Moog webhook service (receives events)
- `tests/integration/test_e2e_flow.py`: smoke test (opt-in via env)

Usage
```bash
# Start and run test
bash scripts/run_e2e.sh

# Manually check health
curl -f http://localhost:8080/health   # ingestor
curl -f http://localhost:8084/health   # forwarder
curl -f http://localhost:8090/health   # webui
curl -f http://localhost:18083/health  # mock-moog

# Post a test event (if needed)
curl -s -X POST http://localhost:8080/api/v2/ingest \
  -H 'Content-Type: application/json' -H 'X-API-KEY: test-ingest' \
  -d '{"timestamp":"2025-11-10T12:00:00Z","message":"hello","hostname":"e2e","syslog_severity":4}'

# Stop the stack
docker compose -f docker-compose.test.yml down -v
```

Notes
- The runner sets `E2E_COMPOSE=true` so the smoke test is enabled.
- Vault dev mode and `vault-setup` container provision AppRole and secrets, writing SecretID/RoleID to `./dev/secrets/` which is mounted by services.

