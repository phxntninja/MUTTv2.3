# MUTT v2.5 – Phase 2 Handoff

Status: Implemented core Phase 2 deliverables. Unit tests added. One unrelated test area remains to be aligned (tracing utils). This document captures what changed, how to validate, and recommended next steps.

## Scope
- Complete Configuration Hot‑Reloading APIs in Web UI and add an admin view in Ingestor.
- Add zero‑downtime secret rotation via dual‑password connectors for PostgreSQL and Redis.
- Update Vault initialization to provision dual secrets; add an operator runbook.

## What’s Implemented
- Web UI config management API (services/web_ui_service.py)
  - GET `/api/v1/config` – returns dynamic config values.
  - PUT `/api/v1/config/<key>` – updates a single key; best‑effort audit via `audit_logger.log_config_change`.
  - GET `/api/v1/config/history` – paginated history from `config_audit_log` where `table_name='dynamic_config'`.
  - Notes: Uses existing API‑key auth decorator; request/response logging leverages existing hooks.

- Ingestor admin config view (services/ingestor_service.py)
  - GET `/admin/config` – returns `static` (validated env config), `dynamic` (DynamicConfig get_all), and flag `dynamic_config_enabled`.

- Dual‑password connectors
  - New: `services/postgres_connector.py` – `get_postgres_pool(...)` tries `DB_PASS_CURRENT` then `DB_PASS_NEXT`, validates with `SELECT 1`.
  - New: `services/redis_connector.py` – `get_redis_pool(...)` tries `REDIS_PASS_CURRENT` then `REDIS_PASS_NEXT`, validates with `PING`.
  - Refactors to use helpers:
    - `services/web_ui_service.py` (DB + Redis pools)
    - `services/ingestor_service.py` (Redis pool)
    - `services/alerter_service.py` (DB + Redis)
    - `services/moog_forwarder_service.py` (Redis)
  - Vault loaders updated to accept dual keys with back‑compat: `*_PASS_CURRENT`, `*_PASS_NEXT` (and legacy `*_PASS`).

- Vault + Docs
  - Updated: `scripts/vault-init.sh` now writes `DB_PASS_CURRENT/NEXT`, `REDIS_PASS_CURRENT/NEXT` for prod and dev.
  - New: `docs/SECRET_ROTATION_PROCEDURE.md` – operator runbook for zero‑downtime rotation.
  - New earlier in this effort: `docs/observability.md`; README link added.

## Validation
- Quick test targets (all passed locally):
  - Dynamic config API: `tests/test_webui_unit.py::TestDynamicConfigAPI`
  - Connectors: `tests/test_postgres_connector.py`, `tests/test_redis_connector.py`

- Full test suite snapshot
  - Command: `./venv310/Scripts/python -m pytest -q`
  - Result: Majority pass. Remaining failures are limited to `tracing_utils` tests that patch attributes not present in the module (pre‑existing and unrelated to Phase 2).

## How to Run
- Unit tests
  - All: `./venv310/Scripts/python -m pytest -q`
  - Focused:
    - Web UI config API: `./venv310/Scripts/python -m pytest -q tests/test_webui_unit.py::TestDynamicConfigAPI`
    - Connectors: `./venv310/Scripts/python -m pytest -q tests/test_postgres_connector.py tests/test_redis_connector.py`

- Local run hints
  - Web UI requires minimal Vault env for Config validation during app startup:
    - `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID_FILE`, `VAULT_SECRETS_PATH`
  - Observability toggles: see `docs/observability.md` and venv activation defaults in `venv/Scripts/Activate.ps1` (`MUTT_OTEL_MODE`).

## Notes on Code Changes
- `services/web_ui_service.py`
  - Added imports for connector helpers (`services.*_connector`).
  - Initialized DynamicConfig using the existing Redis pool when available; endpoints guarded if unavailable.
  - Normalized indentation and replaced non‑ASCII whitespace.
  - Auth decorator updated to use `flask.current_app`.

- `services/ingestor_service.py`
  - Added `/admin/config` endpoint.
  - Redis pool now uses `get_redis_pool` with dual‑password support.

- `services/alerter_service.py`, `services/moog_forwarder_service.py`
  - Switched connection setup to dual‑password helpers.
  - Vault secret loaders accept CURRENT/NEXT with back‑compat.

## Acceptance Criteria Mapping
- View/update config at runtime via Web UI without restarts – Implemented (GET/PUT endpoints, dynamic cache invalidation handled by DynamicConfig; best‑effort audit).
- Config changes recorded in `config_audit_log` – Implemented for PUT via `audit_logger.log_config_change`.
- All services handle DB/Redis password rotation without downtime – Implemented via dual‑password helpers and refactors.
- Unit tests cover new code – Added for Web UI config API and connectors; suite runs with unrelated tracing tests still failing.
- Operator runbook for rotation – `docs/SECRET_ROTATION_PROCEDURE.md` added.

## Known Issues / Deferred
- Tracing utils tests (`tests/test_tracing_utils.py`) patch attributes (`BatchSpanProcessor`, `StatusCode`, etc.) not exported by `services/tracing_utils.py`. These are pre‑existing and out of Phase 2 scope. Options to resolve:
  - Update tests to patch symbols where they exist (from OpenTelemetry SDK), or
  - Add minimal shims in `services/tracing_utils.py` to expose the expected names.

## Next Steps
- Align tracing tests and/or module exports; get the suite fully green.
- Verify Web UI config APIs against a real Postgres (for audit log writes) and Redis (for DynamicConfig); confirm RBAC and credentials in Vault are set.
- Add minimal API docs snippet linking the new endpoints in `README.md` (optional).
- Consider adding minimal authorization/role checks for config updates if multi‑user scenarios are expected.

## Rollback
- Endpoints can be disabled by removing the config routes in `services/web_ui_service.py`.
- Services remain compatible with legacy single‑secret keys (`DB_PASS`, `REDIS_PASS`) if dual‑password rotation is not adopted.

## File Index (changed/added)
- Added
  - `services/postgres_connector.py`
  - `services/redis_connector.py`
  - `docs/SECRET_ROTATION_PROCEDURE.md`
  - `docs/PHASE_2_HANDOFF.md` (this doc)
- Modified
  - `services/web_ui_service.py`
  - `services/ingestor_service.py`
  - `services/alerter_service.py`
  - `services/moog_forwarder_service.py`
  - `scripts/vault-init.sh`
  - `tests/test_webui_unit.py` (added TestDynamicConfigAPI)
  - `tests/test_postgres_connector.py`
  - `tests/test_redis_connector.py`

