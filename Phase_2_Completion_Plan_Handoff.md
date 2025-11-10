# MUTT v2.5 - Phase 2 Completion Plan Handoff

**Generated:** 2025-11-09
**Status:** Ready for Implementation

---

## 1. Executive Summary

This document outlines the remaining work required to complete **Phase 2: Core Features - Hot Reload & Secrets** as defined in the `V2.5_IMPLEMENTATION_PLAN.md`.

The original implementation was partially completed. This plan details the specific tasks needed to finish the work, providing a clear path for any developer or AI assistant to follow.

### Current Status
- **Section 2.1 (Configuration Hot-Reloading):** ⚠️ **Partially Complete.** The core backend logic is implemented across all services, but the API endpoints for managing configuration at runtime are missing.
- **Section 2.2 (Zero-Downtime Secret Rotation):** ❌ **Not Started.** None of the required files or logic for this section have been implemented.

### Goal
To fully implement all remaining tasks for Phase 2, enabling enterprise-grade configuration hot-reloading and zero-downtime secret rotation.

---

## 2. Detailed Implementation Plan

The work is divided into two parts, corresponding to the sections in the original plan.

### Part 1: Complete Configuration Hot-Reloading (Section 2.1)

#### Task 1.1: Implement Config Management API (Original Task: 2.1.5)
- **File:** `services/web_ui_service.py`
- **Action:** Implement the following REST API endpoints:
  - `GET /api/v1/config`: List all dynamic configuration values from the `DynamicConfig` service.
  - `PUT /api/v1/config/<key>`: Update a specific configuration value. This should use the `DynamicConfig.set()` method.
  - `GET /api/v1/config/history`: Show a history of recent configuration changes. This will require querying the `config_audit_log` table.
- **Integration:** Ensure that all `PUT` operations are logged using the `audit_logger.py` service, as specified in the original plan.

#### Task 1.2: Add Admin View Endpoint (Original Task: 2.1.2)
- **File:** `services/ingestor_service.py`
- **Action:** Add a new read-only endpoint, `/admin/config`.
- **Details:** This endpoint should return a JSON object of the currently loaded configuration values within the Ingestor service, allowing for easy debugging and verification.

#### Task 1.3: Add Unit Tests
- **File:** `tests/test_webui_unit.py`
- **Action:** Add new unit tests to validate the functionality of the new API endpoints created in Task 1.1.
- **Coverage:** Tests should cover success cases, error cases (e.g., invalid key), and authentication.

---

### Part 2: Implement Zero-Downtime Secret Rotation (Section 2.2)

#### Task 2.1: Create Dual-Password Connection Helpers (Original Tasks: 2.2.2 & 2.2.3)
- **Action:** Create two new modules with corresponding unit tests.
- **Files to Create:**
  - `services/postgres_connector.py`: Will contain a `get_postgres_connection` function that tries to connect with a `_CURRENT` password and falls back to a `_NEXT` password.
  - `tests/test_postgres_connector.py`: Unit tests for the PostgreSQL connector.
  - `services/redis_connector.py`: Will contain a `get_redis_connection` function with the same dual-password logic for Redis.
  - `tests/test_redis_connector.py`: Unit tests for the Redis connector.

#### Task 2.2: Integrate Connection Helpers (Original Task: 2.2.4)
- **Action:** Refactor all four services to use the new connection helpers.
- **Files to be Modified:**
  - `services/ingestor_service.py`
  - `services/alerter_service.py`
  - `services/moog_forwarder_service.py`
  - `services/web_ui_service.py`
- **Details:** Replace all direct calls to `psycopg2.pool.ThreadedConnectionPool` and `redis.Redis` with the new functions from `postgres_connector.py` and `redis_connector.py`.

#### Task 2.3: Update Vault Initialization Script (Original Task: 2.2.1)
- **File:** `scripts/vault-init.sh`
- **Action:** Modify the script to create secrets with a dual structure to support rotation (e.g., `DB_PASS_CURRENT`, `DB_PASS_NEXT`).

#### Task 2.4: Create Rotation Procedure Document (Original Task: 2.2.5)
- **File to Create:** `docs/SECRET_ROTATION_PROCEDURE.md`
- **Action:** Write a clear, step-by-step guide for operators explaining how to perform a zero-downtime secret rotation using the newly implemented system. This should include Vault commands and verification steps.

---

## 3. File Manifest

### Files to be Modified
- `services/web_ui_service.py`
- `services/ingestor_service.py`
- `tests/test_webui_unit.py`
- `services/alerter_service.py`
- `services/moog_forwarder_service.py`
- `scripts/vault-init.sh`

### Files to be Created
- `Phase_2_Completion_Plan_Handoff.md` (this document)
- `services/postgres_connector.py`
- `tests/test_postgres_connector.py`
- `services/redis_connector.py`
- `tests/test_redis_connector.py`
- `docs/SECRET_ROTATION_PROCEDURE.md`

---

## 4. Acceptance Criteria

Phase 2 will be considered complete when:
- ✅ All tasks listed in this document are finished.
- ✅ Configuration values can be viewed and updated at runtime via the new API endpoints without service restarts.
- ✅ All configuration changes made via the API are recorded in the `config_audit_log` table.
- ✅ All four services can automatically handle a database or Redis password rotation without downtime or manual intervention.
- ✅ All new code is covered by unit tests.
- ✅ The `SECRET_ROTATION_PROCEDURE.md` document provides clear and actionable instructions for operators.
