# Zero‑Downtime Secret Rotation

This document describes how to rotate Redis and PostgreSQL passwords without downtime using the dual‑password connectors.

Overview
- Services attempt `*_CURRENT` first; on auth failure they fall back to `*_NEXT`.
- During rotation, you “promote” NEXT to CURRENT and generate a new NEXT.
- All services keep running; new connections succeed throughout.

Prerequisites
- Vault KV v2 path used by services (e.g., `secret/mutt/prod`).
- Keys provisioned by `scripts/vault-init.sh`:
  - `DB_USER`, `DB_PASS_CURRENT`, `DB_PASS_NEXT`
  - `REDIS_PASS_CURRENT`, `REDIS_PASS_NEXT`

Rotation Steps
1) Prepare the new password as NEXT (no service changes yet)
- Generate new strong password values.
- Write to Vault:
  - `DB_PASS_NEXT = <new_db_password>`
  - `REDIS_PASS_NEXT = <new_redis_password>`

2) Apply NEXT to the backing services
- Update the actual database and Redis user passwords to accept both the existing CURRENT and the new NEXT value concurrently.
  - Postgres: add `PASSWORD` for the same user to the new NEXT value, keeping existing CURRENT valid until cutover.
  - Redis: configure to accept the new NEXT password (ACL user can have multiple passwords) while keeping CURRENT.

3) Promote NEXT -> CURRENT in Vault
- Copy values:
  - `DB_PASS_CURRENT = <previous DB_PASS_NEXT>`
  - `REDIS_PASS_CURRENT = <previous REDIS_PASS_NEXT>`
- Generate a fresh NEXT for the next cycle (optional now or later):
  - `DB_PASS_NEXT = <fresh_random>`
  - `REDIS_PASS_NEXT = <fresh_random>`

4) Verify
- Web UI health and metrics endpoints should be green.
- Web UI API: `GET /api/v1/config` (auth required) loads fine.
- Alerter health endpoint (if enabled) reports DB/Redis connected.
- Logs do not show “auth failed” loops; brief warnings during cutover are acceptable.

5) Decommission old password in the backing services
- Remove the previously old CURRENT password from Postgres/Redis.
- Confirm no errors appear in logs.

Rollback
- If issues occur post‑promotion, revert Vault `*_CURRENT` to the previous value and ensure backing services still accept it.

Notes
- Services read secrets at startup; connection pools use the dual‑password logic on new connections.
- You do not need to restart services during rotation.
- For safety, stagger removal of old passwords after confirming all instances have new connections.

