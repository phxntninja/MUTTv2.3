# MUTT v2.5 - Phase 7 Plan

**Last Updated:** 2025-11-11
**Status:** Not Started
**Progress:** 1/27 tasks (3%)

---

## Quick Progress View

```
Priority 1: Establish Coverage Baseline & Expand Test Suite      [x] 1/6   (17%)
Priority 2: Integration Test Suite & CI Enhancement             [ ] 0/5   (0%)
Priority 3: Execute Operator Validation in Staging              [ ] 0/5   (0%)
Priority 4: Documentation Consolidation & Cleanup               [ ] 0/6   (0%)
Priority 5: Service-Specific Test Coverage                      [ ] 0/5   (0%)
                                                                ───────────────
                                                          TOTAL: [x] 1/27  (3%)
```

---

## Priority 1: Establish Coverage Baseline & Expand Test Suite (0/6)

**Rationale**: Coverage enforcement is configured but we don't know current coverage. We need a baseline.

- [x] **1.1** - Run full test suite with coverage across all services
- [ ] **1.2** - Document current coverage percentage per service
- [ ] **1.3** - Identify critical untested code paths
- [ ] **1.4** - Adjust codecov.yml thresholds to realistic targets
- [ ] **1.5** - Add tests for core business logic (alerter rule matching, moog forwarding, etc.)
- [ ] **1.6** - Target: Achieve minimum 60% overall coverage before enforcing drops

---

## Priority 2: Integration Test Suite & CI Enhancement (0/5)

**Rationale**: Current CI only runs unit tests. Need end-to-end validation.

- [ ] **2.1** - Create integration test suite:
    - [ ] Test full pipeline: Ingestor → Redis → Alerter → Moog Forwarder
    - [ ] Test dynamic config hot-reload in containerized environment
    - [ ] Test janitor recovery mechanisms
    - [ ] Test backpressure and DLQ handling
- [ ] **2.2** - Add integration test job to CI workflow:
    - [ ] Use docker-compose to spin up test environment
    - [ ] Run integration tests after unit tests pass
    - [ ] Publish integration test results
- [ ] **2.3** - Consider adding smoke tests for deployment validation

---

## Priority 3: Execute Operator Validation in Staging (0/5)

**Rationale**: Operational tooling needs real-world validation before production.

- [ ] **3.1** - Deploy branch to staging environment
- [ ] **3.2** - Execute [docs/OPERATOR_VALIDATION_GUIDE.md](docs/OPERATOR_VALIDATION_GUIDE.md) procedures
- [ ] **3.3** - Document results and any issues discovered
- [ ] **3.4** - Update guide with lessons learned
- [ ] **3.5** - Train operators on new tooling

---

## Priority 4: Documentation Consolidation & Cleanup (0/6)

**Rationale**: Multiple overlapping status/handoff documents create confusion.

- [ ] **4.1** - Review all `PHASE_*_HANDOFF*.md` and `*_STATUS_*.md` files
- [ ] **4.2** - Determine which are superseded/obsolete
- [ ] **4.3** - Move obsolete docs to `docs/archive/` or delete
- [ ] **4.4** - Create single source of truth for project status
- [ ] **4.5** - Update main README to point to consolidated docs
- [ ] **4.6** - Consider creating `docs/CHANGELOG.md` for version history

---

## Priority 5: Service-Specific Test Coverage (0/5)

**Focus Areas**:
- [ ] **5.1** - **Alerter Service**: Rule matching logic, environment detection, unhandled event aggregation
- [ ] **5.2** - **Moog Forwarder**: Rate limiting, retry/backoff logic, DLQ handling
- [ ] **5.3** - **Ingestor**: Backpressure, API key validation, metrics caching
- [ ] **5.4** - **Web UI**: API endpoints, authentication, SLO calculations
- [ ] **5.5** - **Remediation**: DLQ processing, poison message handling

**Target**: 70%+ coverage for each service.
