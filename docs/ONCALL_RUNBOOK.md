# On‑Call Runbook

Common checks and remedies for MUTT v2.5 services.

## Health & Basics
- Web UI: `GET /health` on port 8090
- Ingestor: `GET /health` on port 8080
- Alerter: `GET /health` on port 8081
- Moog Forwarder: `GET /health` on port 8084

## Vault Issues
- Check Vault reachability: `curl -s $VAULT_ADDR/v1/sys/health | jq`
- Verify AppRole credentials (Role ID, Secret ID file path)
- Restart service if non‑renewable token TTL is low and cannot be extended

## Redis Queues
- Queue depth (CLI): `redis-cli LLEN mutt:ingest_queue`
- DLQs: `redis-cli LRANGE mutt:dlq:alerter 0 10`
- Orphans: `redis-cli KEYS "mutt:processing:*"`
- Remediation: restart worker (alerter) to trigger janitor cleanup

## Dynamic Config
- View: `GET /api/v1/config` (Web UI + API key)
- Update: `PUT /api/v1/config/<key>` with JSON body `{ "value": "..." }`
- History: `GET /api/v1/config/history`

## Secret Rotation (Zero‑Downtime)
- Follow `docs/SECRET_ROTATION_PROCEDURE.md`
- Always keep both CURRENT and NEXT valid in backends during promotion window

## API Key Rotation (Ingestor/Web UI)

MUTT uses API keys for Ingestor (`X-API-KEY` on /api/v2/ingest) and Web UI APIs. Unlike DB/Redis credentials,
dual-key rotation is not currently supported in-app; plan a brief restart window.

Recommended procedure (staging → prod):
1. Generate new keys and store in Vault at `secret/mutt`:
   - `INGEST_API_KEY`, `WEBUI_API_KEY`
2. In staging, restart the corresponding service(s) to pick up new keys (watch `/health` + logs).
3. Validate with curl:
   - Ingest: `curl -s -X POST http://<ingestor>:8080/api/v2/ingest -H 'X-API-KEY: <NEW>' -d '{...}'`
   - Web UI: `curl -s -H 'X-API-KEY: <NEW>' http://<webui>:8090/api/v2/rules`
4. For production, schedule a maintenance window:
   - Restart Ingestor and Web UI to load new keys
   - Update upstream senders/clients to the new key
5. Confirm new key works, then remove the old key from Vault.

Notes:
- Keys are compared using constant-time checks to mitigate timing attacks.
- If strict zero-downtime is needed, consider introducing a temporary dual-key check in code or a proxy layer.

## Rate Limiting (Moog Forwarder)
- Hits metric: `mutt_moog_rate_limit_hits_total`
- Adjust via env vars or DynamicConfig (if wired) and restart if env based

## Logs & Correlation IDs
- All services log correlation IDs
- Use `X-Correlation-ID` in requests to trace across services

## Circuit Breaker (Moog Forwarder)

When Moogsoft is degraded or unreachable, the forwarder opens a Redis‑backed circuit breaker to avoid wasteful retries.

- Symptoms
  - Alerts delayed; forwarder re‑queues instead of sending
  - `mutt_moog_circuit_open == 1`
  - Rising `mutt_moog_circuit_trips_total` and `mutt_moog_circuit_blocked_total`

- What to check
  - Moog webhooks reachable (forwarder health logs, curl the webhook URL from the cluster/node)
  - Network/TLS issues (timeouts, cert errors)
  - Forwarder metrics: `:8083/metrics` (Prometheus: `mutt_moog_*` series)

- Tuning (env on forwarder)
  - `MOOG_CB_FAILURE_THRESHOLD` (default 5)
  - `MOOG_CB_OPEN_SECONDS` (default 60)
  - `MOOG_RETRY_BASE_DELAY`, `MOOG_RETRY_MAX_DELAY`

- Manual reset (last resort)
  - Clear CB keys in Redis (shared across replicas):
    - `DEL mutt:circuit:moog:open`
    - `DEL mutt:circuit:moog:failures`
  - Only after Moog is healthy to avoid immediate re‑trip.

- Alerts
  - `MUTTMoogCircuitOpen` (see `docs/prometheus/alerts-v25.yml`)
  - Consider paging if open > N minutes in production
