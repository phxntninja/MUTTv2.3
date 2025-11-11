# ADR-006: API Versioning Strategy

Date: 2025-11-10
Status: Accepted

## Context

MUTT exposes HTTP APIs across multiple services. Backward compatibility and operator tooling
require a predictable versioning approach that allows gradual migration between major versions.

## Decision

Adopt a header + path strategy with explicit version headers and parallel path aliases.

- Current canonical API version: v2.5
- Headers on all responses:
  - `X-API-Version`: current service API version (e.g., v2.5)
  - `X-API-Deprecated`: `true` for deprecated v1 paths; `false` for v2 paths
  - `X-API-Supported-Versions`: comma-separated list (e.g., v2.5, v2.0, v1.0)
- Path aliases: maintain `/api/v1/*` while providing `/api/v2/*` equivalents

Provide a small `services/api_versioning.py` helper to standardize behaviors and allow future
negotiation via `Accept-Version`, `X-API-Version`, or `?api_version=`.

## Rationale

- Explicit, visible headers help clients audit usage and detect deprecated paths without breaking.
- Dual paths allow incremental migration and reduce risk during upgrades.
- Keeping version logic in a helper enables consistency across services.

## Consequences

- Clients should migrate to `/api/v2/*` paths and validate `X-API-Deprecated`.
- Test parity is required to ensure v1 and v2 remain functionally identical until removal.

## Implementation

- Web UI: adds v2 aliases for metrics, rules, audit, dev-hosts, teams; after_request injects headers.
- Ingestor: adds `/api/v2/ingest`; injects version headers (including supported versions).
- Alerter/Forwarder health endpoints include version headers.
- Tests: `tests/test_api_v2_parity.py` verify v1/v2 parity.

## Removal Policy

- Deprecate v1 in current minor (headers set X-API-Deprecated: true on v1 paths).
- Announce removal timeline in release notes; consider `X-API-Sunset` if date known.

