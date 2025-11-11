# MUTT v2.5 - Rebuild Bundle Index

**Purpose:** Complete document package for rebuilding MUTT v2.5 from scratch
**Target:** Humans or AI assistants (Copilot, ChatGPT, Claude, etc.)
**Approach:** Specification-driven rebuild (no code copying)

---

## How to Use This Bundle

### For AI Assistants (Copilot, ChatGPT, Claude, etc.)

**Step 1: Load Context**
Upload or reference ALL documents in this bundle to your context.

**Step 2: Read in This Order**
Follow the reading order below sequentially.

**Step 3: Implement**
Use the specifications to write code from scratch.

**Step 4: Validate**
Use the test specifications to verify your implementation.

### For Human Developers

**Step 1: Read Architecture First**
Understand the system design before coding.

**Step 2: Follow the Rebuild Guide**
Use `REBUILD_GUIDE.md` as your implementation roadmap.

**Step 3: Reference Specifications**
Use the specification documents for exact requirements.

**Step 4: Test as You Go**
Validate each phase before moving to the next.

---

## Bundle Contents

### Essential Documents (Must Have)

These documents are REQUIRED for a successful rebuild:

#### 1. Master Guide
- **`docs/REBUILD_GUIDE.md`** (THIS IS YOUR PRIMARY GUIDE)
  - Step-by-step implementation instructions
  - ~50% complete (Foundation + Database + Utilities + Ingestor)
  - Phase-based approach with specifications
  - Test cases for each component

#### 2. Architecture Documentation (6 documents, 90-110 pages)
**Location:** `docs/architecture/`

Read in this order:
1. **`SYSTEM_ARCHITECTURE.md`** (18-20 pages) - CRITICAL
   - What MUTT is and how it works
   - 5 microservices explained
   - Data flow diagrams
   - Core patterns (BRPOPLPUSH, Janitor, Circuit Breaker)
   - External dependencies

2. **`DESIGN_RATIONALE.md`** (16-18 pages) - CRITICAL
   - WHY each design decision was made
   - Trade-offs considered
   - Alternatives rejected and why
   - Evolution from v2.3 to v2.5

3. **`INTEGRATION_PATTERNS.md`** (14-16 pages)
   - How to integrate with external systems
   - rsyslog configuration
   - SNMP integration
   - Moogsoft webhook format
   - Prometheus/Grafana setup

4. **`SCALABILITY_GUIDE.md`** (16-18 pages)
   - When to scale each service
   - Horizontal vs vertical scaling
   - Performance tuning
   - Capacity planning

5. **`DEPLOYMENT_ARCHITECTURE.md`** (18-20 pages)
   - RHEL standalone deployment (PRIMARY model)
   - Kubernetes/OpenShift deployment
   - systemd service configuration
   - High availability patterns

6. **`EVOLUTION_ROADMAP.md`** (12-14 pages)
   - Future enhancements
   - Technical debt
   - v2.6 and v3.0 roadmap

#### 3. Architecture Decision Records (6 documents, ~12 pages)
**Location:** `docs/adr/`

Read ALL of these - they explain critical design choices:

1. **`ADR-001-redis-vs-kafka.md`**
   - Why Redis for message queuing instead of Kafka

2. **`ADR-002-vault-vs-k8s-secrets.md`**
   - Why HashiCorp Vault for secrets management

3. **`ADR-003-single-threaded-workers.md`**
   - Why single-threaded workers instead of multi-threaded

4. **`ADR-004-postgres-for-audit-logs.md`**
   - Why PostgreSQL for audit trail

5. **`ADR-005-circuit-breaker-moog-forwarder.md`**
   - Why circuit breaker pattern for external calls

6. **`ADR-006-api-versioning.md`**
   - Why v1/v2 API versioning approach

#### 4. Technical Specifications

**Database Schema:**
- **`docs/db/SCHEMA.md`** - Complete PostgreSQL schema
  - Tables: alert_rules, development_hosts, device_teams, event_audit_log, config_audit_log
  - Partitioning strategy
  - Indexes
  - Functions

**API Reference:**
- **`docs/api/REFERENCE.md`** - Complete API documentation
  - All endpoints for all services
  - Request/response formats
  - Authentication
  - Error codes

**Code Organization:**
- **`docs/code/MODULES.md`** - Module structure
  - Service files
  - Shared utilities
  - Import patterns

**Code Examples:**
- **`docs/code/EXAMPLES.md`** - Example implementations
  - Common patterns
  - Code snippets

#### 5. Operations Documentation (8 documents, 170 pages)
**Location:** `docs/operations/`

Reference these for operational requirements:

1. **`INSTALLATION_GUIDE.md`** (25-30 pages)
   - Complete deployment guide for RHEL
   - systemd service setup
   - Firewall/SELinux configuration

2. **`SERVICE_OPERATIONS.md`** (22 pages)
   - How services should operate
   - Dependencies and startup order
   - Scaling procedures

3. **`TROUBLESHOOTING_GUIDE.md`** (38 pages)
   - Problem diagnosis methodology
   - Common errors and solutions

4. **`CONFIG_MANAGEMENT.md`** (18-20 pages)
   - Static, dynamic, and secret configuration
   - Zero-downtime rotation procedures

5. **`MONITORING_ALERTING.md`** (24-25 pages)
   - Complete metrics catalog (100+ metrics)
   - Prometheus setup
   - Alert rules

6. **`BACKUP_RECOVERY.md`** (16-17 pages)
   - Backup strategy
   - Disaster recovery procedures

7. **`INCIDENT_RESPONSE.md`** (14-15 pages)
   - On-call procedures
   - Incident severity classification

8. **`DOCUMENTATION_PLAN.md`** - Master plan for operations docs

#### 6. Project History & Context

- **`docs/PROJECT_HISTORY_COMPLETE.md`** (1000+ lines)
  - Complete chronicle of the project evolution
  - All 31 handoff documents indexed
  - Phase-by-phase breakdown
  - What was built and why
  - Use this for context and understanding

#### 7. Configuration Reference

- **`README.md`** (root directory)
  - Project overview
  - Complete environment variable reference
  - Service ports
  - Quick start examples

- **`.env.template`**
  - All configuration variables with defaults
  - Comments explaining each setting

---

## Reading Order for AI Assistants

Follow this sequence for maximum comprehension:

### Phase 1: Understanding (30 minutes reading)

1. `docs/PROJECT_HISTORY_COMPLETE.md` (skim for context)
2. `README.md` (overview and config reference)
3. `docs/architecture/SYSTEM_ARCHITECTURE.md` (CRITICAL - read fully)
4. `docs/architecture/DESIGN_RATIONALE.md` (CRITICAL - read fully)
5. All 6 ADRs in `docs/adr/` (understand design decisions)

**Checkpoint:** Can you explain:
- What MUTT does?
- Why Redis not Kafka?
- What is the BRPOPLPUSH pattern?
- What are the 5 microservices?

### Phase 2: Technical Specifications (20 minutes reading)

6. `docs/db/SCHEMA.md` (database structure)
7. `docs/api/REFERENCE.md` (API specifications)
8. `docs/code/MODULES.md` (code organization)
9. `docs/architecture/INTEGRATION_PATTERNS.md` (how things connect)

**Checkpoint:** Can you describe:
- The database schema?
- The API endpoints?
- How services communicate?

### Phase 3: Implementation Guide (60+ minutes reading + coding)

10. **`docs/REBUILD_GUIDE.md`** (YOUR IMPLEMENTATION ROADMAP)
    - Follow phase by phase
    - Implement as specified
    - Test each phase

**Important:** Reference the operations docs as needed:
- For deployment details: `docs/operations/INSTALLATION_GUIDE.md`
- For monitoring specs: `docs/operations/MONITORING_ALERTING.md`
- For troubleshooting: `docs/operations/TROUBLESHOOTING_GUIDE.md`

---

## Document Categories

### Category A: CRITICAL (Must Read Before Coding)
- `docs/REBUILD_GUIDE.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/DESIGN_RATIONALE.md`
- All 6 ADRs in `docs/adr/`
- `docs/db/SCHEMA.md`
- `docs/api/REFERENCE.md`

### Category B: Reference (Use During Implementation)
- `docs/code/MODULES.md`
- `docs/code/EXAMPLES.md`
- `docs/architecture/INTEGRATION_PATTERNS.md`
- `docs/operations/CONFIG_MANAGEMENT.md`
- `README.md` (config reference)
- `.env.template`

### Category C: Operational (For Deployment & Testing)
- `docs/operations/INSTALLATION_GUIDE.md`
- `docs/operations/SERVICE_OPERATIONS.md`
- `docs/operations/MONITORING_ALERTING.md`
- `docs/architecture/DEPLOYMENT_ARCHITECTURE.md`
- `docs/architecture/SCALABILITY_GUIDE.md`

### Category D: Context (Background Information)
- `docs/PROJECT_HISTORY_COMPLETE.md`
- `docs/operations/TROUBLESHOOTING_GUIDE.md`
- `docs/operations/BACKUP_RECOVERY.md`
- `docs/operations/INCIDENT_RESPONSE.md`
- `docs/architecture/EVOLUTION_ROADMAP.md`

---

## Minimum Viable Bundle

If context is limited, prioritize these 10 documents:

1. ✅ `docs/REBUILD_GUIDE.md` (implementation instructions)
2. ✅ `docs/architecture/SYSTEM_ARCHITECTURE.md` (what it is)
3. ✅ `docs/architecture/DESIGN_RATIONALE.md` (why decisions were made)
4. ✅ `docs/db/SCHEMA.md` (database spec)
5. ✅ `docs/api/REFERENCE.md` (API spec)
6. ✅ `docs/adr/ADR-001-redis-vs-kafka.md` (Redis choice)
7. ✅ `docs/adr/ADR-003-single-threaded-workers.md` (Worker design)
8. ✅ `docs/operations/MONITORING_ALERTING.md` (metrics catalog)
9. ✅ `README.md` (config reference)
10. ✅ `.env.template` (all configuration variables)

---

## Complete File List

### Documentation (85+ files, 300+ pages)

```
docs/
├── REBUILD_GUIDE.md                          ← START HERE (implementation guide)
├── REBUILD_BUNDLE_INDEX.md                   ← THIS FILE (bundle index)
├── PROJECT_HISTORY_COMPLETE.md               ← Context and history
├── INDEX.md                                  ← Master documentation index
│
├── architecture/                             ← Architecture docs (6 files, 90-110 pages)
│   ├── SYSTEM_ARCHITECTURE.md                ← CRITICAL
│   ├── DESIGN_RATIONALE.md                   ← CRITICAL
│   ├── INTEGRATION_PATTERNS.md
│   ├── SCALABILITY_GUIDE.md
│   ├── DEPLOYMENT_ARCHITECTURE.md
│   └── EVOLUTION_ROADMAP.md
│
├── adr/                                      ← Architecture decisions (6 files)
│   ├── ADR-001-redis-vs-kafka.md             ← CRITICAL
│   ├── ADR-002-vault-vs-k8s-secrets.md
│   ├── ADR-003-single-threaded-workers.md    ← CRITICAL
│   ├── ADR-004-postgres-for-audit-logs.md
│   ├── ADR-005-circuit-breaker-moog-forwarder.md
│   ├── ADR-006-api-versioning.md
│   └── README.md
│
├── api/                                      ← API specifications
│   └── REFERENCE.md                          ← Complete API docs
│
├── code/                                     ← Code organization
│   ├── MODULES.md                            ← Module structure
│   └── EXAMPLES.md                           ← Code examples
│
├── db/                                       ← Database specifications
│   └── SCHEMA.md                             ← Complete schema
│
├── operations/                               ← Operations docs (8 files, 170 pages)
│   ├── README.md                             ← Quick access
│   ├── DOCUMENTATION_PLAN.md
│   ├── INSTALLATION_GUIDE.md                 ← Deployment guide
│   ├── SERVICE_OPERATIONS.md
│   ├── TROUBLESHOOTING_GUIDE.md
│   ├── CONFIG_MANAGEMENT.md
│   ├── MONITORING_ALERTING.md                ← Metrics catalog
│   ├── BACKUP_RECOVERY.md
│   └── INCIDENT_RESPONSE.md
│
├── dev/                                      ← Developer docs
│   └── ONBOARDING.md
│
├── prometheus/                               ← Monitoring configs
│   ├── alerts-v25.yml
│   ├── recording-rules-v25.yml
│   └── README.md
│
├── grafana/                                  ← Dashboards
│   ├── mutt-dashboard-v25.json
│   └── provisioning/
│
├── alertmanager/                             ← Alert routing
│   └── config-v25.yml
│
├── images/                                   ← Diagrams
│   └── README.md
│
├── DEV_QUICKSTART.md
├── DEVELOPMENT_STANDARDS.md
├── DYNAMIC_CONFIG_USAGE.md
├── DYNAMIC_CONFIG_CHEATSHEET.md
├── ALERTER_BACKPRESSURE.md
├── SLOs.md
├── API_VERSIONING.md
├── API_CONFIG_ENDPOINTS.md
├── API_CONFIG_AUDIT_ENDPOINTS.md
├── SECRET_ROTATION_PROCEDURE.md
├── UPGRADE_GUIDE_v2_3_to_v2_5.md
├── DATA_RETENTION_GUIDE.md
├── INTEGRATION_TESTING.md
├── OPERATOR_VALIDATION_GUIDE.md
├── FEATURE_MATRIX.md
└── observability.md
```

### Source Code Organization (for reference structure)

```
services/                                     ← All microservices
├── ingestor_service.py                       ← HTTP ingestion (port 8080)
├── alerter_service.py                        ← Event processing (ports 8081/8082)
├── moog_forwarder_service.py                 ← External forwarding (ports 8083/8084)
├── web_ui_service.py                         ← Management UI (port 8090)
├── remediation_service.py                    ← Self-healing (ports 8086/8087)
├── audit_logger.py                           ← Shared utility
├── dynamic_config.py                         ← Shared utility
├── logging_utils.py                          ← Shared utility
├── tracing_utils.py                          ← Shared utility
├── redis_connector.py                        ← Shared utility
├── postgres_connector.py                     ← Shared utility
└── rate_limiter.py                           ← Shared utility

database/                                     ← Database schemas
├── mutt_schema_v2.1.sql
├── config_audit_schema.sql
└── partitioned_event_audit_log.sql

scripts/                                      ← Operational scripts
├── create_monthly_partitions.py
├── archive_old_events.py
├── init_dynamic_config.py
└── muttdev.py

tests/                                        ← Test suite
├── test_ingestor.py
├── test_alerter.py
├── test_moog_forwarder.py
├── test_webui.py
├── test_remediation.py
├── test_audit_logger.py
├── test_dynamic_config.py
└── test_integration.py
```

---

## Implementation Phases

Follow this sequence (detailed in REBUILD_GUIDE.md):

### Phase 0: Foundation
- Read architecture docs
- Understand core patterns
- Set up environment

### Phase 1: Database Layer
- PostgreSQL schema
- Partitioning
- Functions
- Initial data

### Phase 2: Core Services
- Shared utilities first (audit_logger, dynamic_config, connectors, etc.)
- Ingestor Service
- Alerter Service
- Moog Forwarder Service
- Web UI Service
- Remediation Service

### Phase 3: Infrastructure Services
- Vault integration
- Redis setup
- PostgreSQL setup

### Phase 4: Integration & Reliability
- BRPOPLPUSH pattern
- Janitor recovery
- Circuit breaker
- Backpressure handling
- Rate limiting

### Phase 5: Observability
- JSON logging
- OpenTelemetry tracing
- Prometheus metrics
- Grafana dashboards

### Phase 6: API & Compliance
- API versioning
- Configuration audit
- Data retention

### Phase 7: Testing
- Unit tests (350+)
- Integration tests (100+)
- Coverage validation

### Phase 8: Deployment
- systemd services
- Kubernetes manifests
- Docker Compose

### Phase 9: Documentation
- Update all docs with any changes

---

## Validation Checklist

After completing the rebuild, validate:

### ✅ Architecture
- [ ] 5 microservices implemented
- [ ] BRPOPLPUSH pattern used
- [ ] Janitor recovery implemented
- [ ] Circuit breaker in Moog Forwarder
- [ ] Backpressure in Alerter
- [ ] Rate limiting in Moog Forwarder

### ✅ Database
- [ ] All 5 tables created
- [ ] Partitioning working
- [ ] Functions created
- [ ] Indexes present

### ✅ Services
- [ ] Ingestor accepts events
- [ ] Alerter processes events
- [ ] Moog Forwarder forwards to external system
- [ ] Web UI shows dashboard
- [ ] Remediation replays from DLQ

### ✅ Configuration
- [ ] Dynamic config working
- [ ] Vault integration working
- [ ] Zero-downtime rotation supported

### ✅ Observability
- [ ] 100+ Prometheus metrics exposed
- [ ] JSON logging (if enabled)
- [ ] OpenTelemetry tracing (if enabled)

### ✅ Testing
- [ ] 75%+ code coverage
- [ ] All unit tests passing
- [ ] Integration tests passing

### ✅ Deployment
- [ ] systemd services work
- [ ] Kubernetes manifests work
- [ ] Health checks respond

---

## Getting Help

### If Something is Unclear

**For AI Assistants:**
1. Re-read the relevant architecture document
2. Check the ADR for that design decision
3. Reference the operations docs for expected behavior
4. Look at the complete history in PROJECT_HISTORY_COMPLETE.md

**For Humans:**
1. Check the troubleshooting guide: `docs/operations/TROUBLESHOOTING_GUIDE.md`
2. Review the architecture: `docs/architecture/SYSTEM_ARCHITECTURE.md`
3. Check the ADRs: `docs/adr/`
4. Look for examples: `docs/code/EXAMPLES.md`

### If Implementation Differs

If your environment requires changes:
1. Document why in an ADR (use ADR_TEMPLATE.md)
2. Update the relevant architecture document
3. Ensure tests still pass
4. Update operations documentation

---

## Success Criteria

You have successfully rebuilt MUTT v2.5 when:

1. ✅ All 5 services start without errors
2. ✅ Events flow from Ingestor → Alerter → Moog Forwarder
3. ✅ Web UI displays real-time metrics
4. ✅ Rules matching works correctly
5. ✅ DLQ and recovery working
6. ✅ All health checks return 200
7. ✅ 100+ Prometheus metrics exposed
8. ✅ Test suite passes (75%+ coverage)
9. ✅ Configuration changes without restart
10. ✅ Zero-downtime secret rotation works

---

## Estimated Effort

**For AI Assistant:**
- Context loading: 10-15 minutes
- Reading: 60-90 minutes
- Implementation: 4-8 hours
- Testing: 2-4 hours
- **Total: 1-2 days**

**For Human Developer (experienced):**
- Reading: 4-6 hours
- Implementation: 2-3 weeks
- Testing: 1 week
- **Total: 3-4 weeks**

**For Human Developer (learning):**
- Reading: 1-2 days
- Implementation: 4-6 weeks
- Testing: 1-2 weeks
- **Total: 6-8 weeks**

---

## Bundle Versions

**Current Bundle Version:** 1.0
**MUTT Version:** 2.5
**Last Updated:** 2025-11-10

**Bundle Completeness:**
- REBUILD_GUIDE.md: ~50% complete (Foundation through Ingestor)
- Architecture Docs: 100% complete
- Operations Docs: 100% complete
- API Specs: 100% complete
- Database Specs: 100% complete

**Known Gaps:**
- REBUILD_GUIDE.md needs completion for:
  - Alerter Service detailed specifications
  - Moog Forwarder Service detailed specifications
  - Web UI Service detailed specifications
  - Remediation Service detailed specifications
  - Testing phase details
  - Deployment phase details

**Workaround for Gaps:**
Reference the architecture and operations documents for missing details. They contain the specifications needed.

---

## License & Attribution

This documentation bundle was created through AI collaboration (Gemini + Claude Code) for the MUTT v2.5 project. Use freely for rebuilding MUTT in any environment.

**Attribution:**
- Original architecture: Gemini (Google)
- Implementation & documentation: Claude Code (Anthropic) + Gemini
- Project vision: Human project owner

---

**END OF BUNDLE INDEX**

**Next Steps:**
1. Read this document
2. Follow the reading order
3. Use REBUILD_GUIDE.md for implementation
4. Reference specs as needed
5. Validate with checklist

Good luck with your rebuild! 🚀
