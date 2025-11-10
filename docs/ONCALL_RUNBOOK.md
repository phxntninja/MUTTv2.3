# On‑Call Runbook

Common checks and remedies for MUTT v2.5 services.

## Health & Basics
- Web UI: `GET /health` on port 8090
- Ingestor: `GET /health` on port 8080
- Alerter: `GET /health` on port 8081
- Moog Forwarder: `GET /health` on port 8082

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

## Rate Limiting (Moog Forwarder)
- Hits metric: `mutt_moog_rate_limit_hits_total`
- Adjust via env vars or DynamicConfig (if wired) and restart if env based

## Logs & Correlation IDs
- All services log correlation IDs
- Use `X-Correlation-ID` in requests to trace across services

