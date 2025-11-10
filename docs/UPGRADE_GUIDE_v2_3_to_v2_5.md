# Upgrade Guide: v2.3 → v2.5

This guide walks operators through upgrading to v2.5 with minimal risk.

## Prerequisites
- Postgres and Redis reachable from services.
- Vault available with KV v2 at your configured path.
- Ability to restart services if needed for rollback.

## High‑Level Steps
1) Prepare Vault secrets
- Run or adapt `scripts/vault-init.sh` to create dual secrets:
  - `DB_USER`, `DB_PASS_CURRENT`, `DB_PASS_NEXT`
  - `REDIS_PASS_CURRENT`, `REDIS_PASS_NEXT`
- Keep legacy `DB_PASS`/`REDIS_PASS` for compatibility if needed.

2) Deploy v2.5 services
- Update your container images/manifests or Python env to v2.5 code.
- Ensure env vars for Vault (e.g., `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID_FILE`, `VAULT_SECRETS_PATH`) are set.

3) Validate after deploy
- Health endpoints (`/health`) report connected.
- Web UI reachable; `GET /api/v1/config` (with API key) works.
- Metrics functional at `/metrics`.

4) Secret rotation drill (optional but recommended)
- Follow `docs/SECRET_ROTATION_PROCEDURE.md` to promote `*_NEXT → *_CURRENT` and set a fresh NEXT.
- Ensure services remain healthy throughout; examine logs for transient warnings.

5) Config hot‑reload drill
- Use Web UI APIs to update a dynamic key and observe immediate effect.

## Rollback Plan
- If issues arise, revert to v2.3 images/manifests.
- Keep legacy single‑secret keys in Vault for compatibility.
- Rotation: revert `*_CURRENT` to previous working value and keep both passwords valid in backing services.

## Post‑Upgrade Tasks
- Update runbooks to reference the config APIs and rotation procedure.
- Share `docs/FEATURE_MATRIX.md` and `docs/PHASE_2_HANDOFF.md` with stakeholders.

