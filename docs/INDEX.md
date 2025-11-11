# MUTT v2.5 - Complete Documentation Index

**Last Updated:** 2025-11-10

This is the master index for all MUTT v2.5 documentation. Use this guide to quickly find the documentation you need.

---

## 🤖 AI Collaboration & Handoff

**Target Audience:** AI Assistants, Project Managers

| Document | Description |
|----------|-------------|
| [AI Collaboration Handoff](../AI_COLLABORATION_HANDOFF_completed.md) | Handoff document for AI collaboration |
| [AI Coordination Status](../AI_COORDINATION_STATUS.md) | Status of AI coordination |
| [Architect Sign-off](../ARCHITECT_SIGN_OFF.md) | Architect sign-off for v2.5 |
| [Architect Status for Gemini](../ARCHITECT_STATUS_FOR_GEMINI.md) | Status and next steps for Gemini |
| [Gemini's Handoff Part 1](../Gemini's%20handoff%20part%201_completed.md) | Gemini's handoff part 1 |
| [Gemini's Handoff Part 2](../Gemini's%20handoff%20part%202_completed.md) | Gemini's handoff part 2 |
| [Gemini's Handoff Part 3](../Gemini's%20handoff%20part%203_completed.md) | Gemini's handoff part 3 |
| [Gemini's Handoff Part 4](../Gemini's%20handoff%20part%204_completed.md) | Gemini's handoff part 4 |
| [Gemini's Handoff Part 5](../Gemini's%20handoff%20part%205%20-%20Ingest%20Webhook%20Service_completed.md) | Gemini's handoff part 5 |
| [Gemini's Handoff Part 6](../Gemini's%20handoff%20part%206%20-%20Database%20Schema%20-%20Setup_completed.md) | Gemini's handoff part 6 |
| [Gemini's Handoff Part 7](../Gemini's%20handoff%20part%207%20-%20Vault%20Setup%20Guide_completed.md) | Gemini's handoff part 7 |
| [Gemini's Handoff Part 8](../Gemini's%20handoff%20part%208%20-%20Monitoring%20&%20Alerting_completed.md) | Gemini's handoff part 8 |
| [Gemini's Handoff Part 9](../Gemini's%20handoff%20part%209%20-%20v2.5%20Roadmap%20&%20Enhancement%20Guide_completed.md) | Gemini's handoff part 9 |
| [Gemini's Handoff Part 10](../Gemini's%20handoff%20part%2010%20-%20Enterprise%20Readiness%20Checklist_completed.md) | Gemini's handoff part 10 |
| [Handoff 2025-11-09](../HANDOFF_2025-11-09_65PCT_completed.md) | Handoff document from 2025-11-09 |
| [Handoff Completed](../HANDOFF_completed.md) | Completed handoff document |
| [Phase 2 Completion Plan Handoff](../Phase_2_Completion_Plan_Handoff_completed.md) | Handoff for Phase 2 completion plan |
| [Phase 3 Handoff to Codex](../Phase_3_Handoff_to_Codex_completed.md) | Handoff to Codex for Phase 3 |
| [Phase 4 Handoff](../PHASE_4_HANDOFF.md) | Handoff for Phase 4 |
| [Phase 6 Completion Status](../PHASE_6_COMPLETION_STATUS.md) | Completion status for Phase 6 |
| [Phase3 Questions for Gemini](../Phase3_questions_for_Gemini.md) | Questions for Gemini for Phase 3 |

---

## 📖 Quick Start

**New to MUTT?** Start here:
1. [README.md](../README.md) - Project overview, quick start, service ports
2. [DEV_QUICKSTART.md](DEV_QUICKSTART.md) - Developer setup and CLI usage
3. [Installation Guide](operations/INSTALLATION_GUIDE.md) - Production deployment on RHEL
4. [RHEL Standalone Checklist](architecture/RHEL_STANDALONE_CHECKLIST.md) - One-page install checklist

---

## 🚀 Operations Documentation (Priority 1 & 2)

**Target Audience:** System Administrators, DevOps Engineers, SREs

### Priority 1 (Critical - Must Read)

| Document | Description | Pages |
|----------|-------------|-------|
| **[Installation & Deployment Guide](operations/INSTALLATION_GUIDE.md)** | Complete guide for deploying MUTT on standalone RHEL servers with systemd | 25-30 |
| **[Service Operations Guide](operations/SERVICE_OPERATIONS.md)** | Service management, starting/stopping, scaling, performance tuning | 22 |
| **[Comprehensive Troubleshooting Guide](operations/TROUBLESHOOTING_GUIDE.md)** | Systematic troubleshooting for all services and infrastructure components | 38 |

### Priority 2 (High - Essential)

| Document | Description | Pages |
|----------|-------------|-------|
| **[Configuration Management Guide](operations/CONFIG_MANAGEMENT.md)** | Static/dynamic configuration, secrets management with Vault, rotation procedures | 18-20 |
| **[Monitoring & Alerting Setup Guide](operations/MONITORING_ALERTING.md)** | Prometheus setup, metrics catalog, alerting rules, Grafana dashboards | 24-25 |
| **[Backup & Recovery Guide](operations/BACKUP_RECOVERY.md)** | Automated backups, restoration procedures, disaster recovery scenarios | 16-17 |
| **[Incident Response Runbook](operations/INCIDENT_RESPONSE.md)** | On-call procedures, incident classification, response workflows | 14-15 |

### Additional Operations Guides

| Document | Description |
|----------|-------------|
| [On-Call Runbook](ONCALL_RUNBOOK.md) | Quick reference for on-call engineers (legacy) |
| [Data Retention Guide](DATA_RETENTION_GUIDE.md) | Data retention policies and cleanup procedures |
| [Operator Validation Guide](OPERATOR_VALIDATION_GUIDE.md) | Validation procedures for dynamic config and log streaming |
| [Secret Rotation Procedure](SECRET_ROTATION_PROCEDURE.md) | Zero-downtime password rotation for Redis/PostgreSQL |
| [Upgrade Guide v2.3 to v2.5](UPGRADE_GUIDE_v2_3_to_v2_5.md) | Migration guide from v2.3 to v2.5 |
| [Integration Testing](INTEGRATION_TESTING.md) | Integration test procedures |

**📋 Operations Documentation Plan:** [DOCUMENTATION_PLAN.md](operations/DOCUMENTATION_PLAN.md)

---

## 🏗️ Architecture Documentation

**Target Audience:** Architects, Senior Engineers, Technical Leadership

| Document | Description | Pages |
|----------|-------------|-------|
| **[System Architecture Guide](architecture/SYSTEM_ARCHITECTURE.md)** | High-level architecture, component interactions, data flow | 18-20 |
| **[Design Rationale](architecture/DESIGN_RATIONALE.md)** | Design decisions, trade-offs, ADR deep-dives | 22-25 |
| **[Integration Patterns Guide](architecture/INTEGRATION_PATTERNS.md)** | External integrations, API contracts, event flow | 16-18 |
| **[Scalability Guide](architecture/SCALABILITY_GUIDE.md)** | Scaling strategies, performance characteristics, capacity planning | 13-15 |
| **[Deployment Architecture](architecture/DEPLOYMENT_ARCHITECTURE.md)** | Deployment models (standalone, K8s, Docker Compose), infrastructure requirements | 20-22 |
| **[Evolution Roadmap](architecture/EVOLUTION_ROADMAP.md)** | Future architectural direction, planned improvements | 11-13 |

**Legacy Architecture Docs:**
- [architecture.md](architecture.md) - Original architecture notes (may be outdated)
- [observability.md](observability.md) - Observability patterns

---

## 🔧 Configuration & Features

**Target Audience:** Operators, Developers

### Configuration Management

| Document | Description |
|----------|-------------|
| [Dynamic Config Usage Guide](DYNAMIC_CONFIG_USAGE.md) | How to use dynamic configuration (Redis-backed, zero-downtime) |
| [Dynamic Config Cheatsheet](DYNAMIC_CONFIG_CHEATSHEET.md) | Quick reference for Redis config keys and commands |
| [API Config Endpoints](API_CONFIG_ENDPOINTS.md) | Web UI API for configuration management |
| [API Config Audit Endpoints](API_CONFIG_AUDIT_ENDPOINTS.md) | Configuration audit trail API |

### Feature Guides

| Document | Description |
|----------|-------------|
| [Alerter Backpressure](ALERTER_BACKPRESSURE.md) | Backpressure handling and shedding modes |
| [SLOs](SLOs.md) | Service Level Objectives and `/api/v1/slo` endpoint |
| [API Versioning](API_VERSIONING.md) | API versioning strategy and implementation |
| [API Lifecycle Policy](API_LIFECYCLE_POLICY.md) | API deprecation and lifecycle management |
| [Feature Matrix](FEATURE_MATRIX.md) | Complete feature matrix across versions |

---

## 📚 API & Code Documentation

**Target Audience:** Developers, Integration Engineers

### API Documentation

| Document | Description |
|----------|-------------|
| **[API Reference](api/REFERENCE.md)** | Complete REST API reference with examples |
| [OpenAPI Spec](api/openapi.yaml) | OpenAPI 3.0 specification (machine-readable) |
| [ReDoc Viewer](api/redoc.html) | Interactive API documentation viewer |

### Code Documentation

| Document | Description |
|----------|-------------|
| [Code Modules](code/MODULES.md) | Python module documentation and dependencies |
| [Code Examples](code/EXAMPLES.md) | Code examples and usage patterns |
| [Used Python Modules](USED_PYTHON_MODULES.md) | Complete list of Python dependencies |
| [Database Schema](db/SCHEMA.md) | PostgreSQL schema documentation |

---

## 👨‍💻 Developer Documentation

**Target Audience:** Software Engineers

| Document | Description |
|----------|-------------|
| **[Developer Quickstart](DEV_QUICKSTART.md)** | Local setup, muttdev CLI, testing, CI/CD |
| [Development Standards](DEVELOPMENT_STANDARDS.md) | Coding standards, style guide, best practices |
| [Developer Onboarding](dev/ONBOARDING.md) | Complete onboarding guide for new developers |
| [Release Checklist](RELEASE_CHECKLIST.md) | Pre-release validation checklist |

---

## 🎯 Architecture Decision Records (ADRs)

**Target Audience:** Architects, Technical Leadership

| ADR | Title | Status |
|-----|-------|--------|
| **[ADR-001](adr/ADR-001-redis-vs-kafka.md)** | Redis Lists vs. Kafka for Queues | Accepted |
| **[ADR-002](adr/ADR-002-vault-vs-k8s-secrets.md)** | Vault vs. Kubernetes Secrets | Accepted |
| **[ADR-003](adr/ADR-003-single-threaded-workers.md)** | Single-Threaded Workers per Pod | Accepted |
| **[ADR-004](adr/ADR-004-postgres-for-audit-logs.md)** | PostgreSQL for Audit Logs | Accepted |
| **[ADR-005](adr/ADR-005-circuit-breaker-moog-forwarder.md)** | Circuit Breaker for Moog Forwarder | Accepted |
| **[ADR-006](adr/ADR-006-api-versioning.md)** | API Versioning Strategy | Accepted |

**ADR Index:** [adr/README.md](adr/README.md)
**ADR Template:** [adr/ADR_TEMPLATE.md](adr/ADR_TEMPLATE.md)

---

## 📊 Monitoring & Observability

**Target Audience:** SREs, Operations

| Document | Description |
|----------|-------------|
| **[Monitoring & Alerting Setup](operations/MONITORING_ALERTING.md)** | Complete Prometheus/Alertmanager/Grafana setup |
| [Prometheus Alerts](prometheus/README.md) | Alert rule definitions |
| [SLO Monitoring](SLOs.md) | SLO tracking and error budgets |

---

## 🔐 Security & Compliance

**Target Audience:** Security Engineers, Compliance Officers

| Document | Description |
|----------|-------------|
| [Secret Rotation Procedure](SECRET_ROTATION_PROCEDURE.md) | Zero-downtime password rotation |
| [Data Retention Guide](DATA_RETENTION_GUIDE.md) | SOX/GDPR compliance, data lifecycle |
| [Vault Integration](operations/CONFIG_MANAGEMENT.md#secrets-management) | HashiCorp Vault integration |

---

## 📝 Project Management & Planning

**Target Audience:** Project Managers, Architects

| Document | Description |
|----------|-------------|
| [Architect Status for Gemini](ARCHITECT_STATUS_FOR_GEMINI.md) | Project status and next work items |
| [Phase 2 Handoff](PHASE_2_HANDOFF_completed.md) | Phase 2 completion status |
| [Phase 3 Handoff](PHASE_3_HANDOFF_completed.md) | Phase 3 completion status |
| [Operations Documentation Plan](operations/DOCUMENTATION_PLAN.md) | Master plan for operational docs |
| [Presentation](presentation.md) | Project presentation materials |

---

## 📦 Deployment & Infrastructure

**Target Audience:** DevOps, Infrastructure Engineers

### Deployment Guides

| Document | Description |
|----------|-------------|
| **[Installation Guide](operations/INSTALLATION_GUIDE.md)** | Standalone RHEL deployment (PRIMARY) |
| **[Deployment Architecture](architecture/DEPLOYMENT_ARCHITECTURE.md)** | All deployment models (RHEL/K8s/Docker) |
| [Service Operations](operations/SERVICE_OPERATIONS.md) | Service management and scaling |

### Infrastructure

| Document | Description |
|----------|-------------|
| [Backup & Recovery](operations/BACKUP_RECOVERY.md) | Disaster recovery procedures |
| [Configuration Management](operations/CONFIG_MANAGEMENT.md) | Config, secrets, Vault integration |

---

## 🆘 Support & Troubleshooting

**Target Audience:** Support Engineers, On-Call

### Quick Access (Emergency)

1. **[Incident Response Runbook](operations/INCIDENT_RESPONSE.md)** - P1 incidents, on-call procedures
2. **[Troubleshooting Guide](operations/TROUBLESHOOTING_GUIDE.md)** - Systematic problem diagnosis
3. **[Service Operations](operations/SERVICE_OPERATIONS.md)** - Service start/stop/restart procedures

### Reference

| Document | Description |
|----------|-------------|
| [On-Call Runbook](ONCALL_RUNBOOK.md) | Quick reference for on-call engineers |
| [Common Error Messages](operations/TROUBLESHOOTING_GUIDE.md#common-error-messages) | Error message catalog |
| [Emergency Procedures](operations/SERVICE_OPERATIONS.md#emergency-procedures) | Emergency response workflows |

---

## 📂 Documentation by Role

### I'm a System Administrator / DevOps Engineer

**Start here:**
1. [Installation Guide](operations/INSTALLATION_GUIDE.md) - Deploy MUTT
2. [Service Operations](operations/SERVICE_OPERATIONS.md) - Manage services
3. [Configuration Management](operations/CONFIG_MANAGEMENT.md) - Configure MUTT
4. [Monitoring & Alerting](operations/MONITORING_ALERTING.md) - Set up monitoring
5. [Backup & Recovery](operations/BACKUP_RECOVERY.md) - Disaster recovery
6. [Troubleshooting Guide](operations/TROUBLESHOOTING_GUIDE.md) - Fix issues

### I'm an On-Call Engineer

**Start here:**
1. [Incident Response Runbook](operations/INCIDENT_RESPONSE.md) - Incident procedures
2. [Troubleshooting Guide](operations/TROUBLESHOOTING_GUIDE.md) - Problem diagnosis
3. [Service Operations](operations/SERVICE_OPERATIONS.md) - Service management
4. [On-Call Runbook](ONCALL_RUNBOOK.md) - Quick reference

### I'm a Software Developer

**Start here:**
1. [Developer Quickstart](DEV_QUICKSTART.md) - Local setup
2. [Developer Onboarding](dev/ONBOARDING.md) - Complete onboarding
3. [API Reference](api/REFERENCE.md) - REST API docs
4. [Code Modules](code/MODULES.md) - Python module docs
5. [Development Standards](DEVELOPMENT_STANDARDS.md) - Coding standards

### I'm an Architect / Tech Lead

**Start here:**
1. [System Architecture](architecture/SYSTEM_ARCHITECTURE.md) - High-level architecture
2. [Design Rationale](architecture/DESIGN_RATIONALE.md) - Design decisions
3. [ADR Index](adr/README.md) - Architecture Decision Records
4. [Scalability Guide](architecture/SCALABILITY_GUIDE.md) - Scaling strategies
5. [Evolution Roadmap](architecture/EVOLUTION_ROADMAP.md) - Future direction

### I'm Integrating with MUTT

**Start here:**
1. [API Reference](api/REFERENCE.md) - REST API documentation
2. [Integration Patterns](architecture/INTEGRATION_PATTERNS.md) - Integration guide
3. [OpenAPI Spec](api/openapi.yaml) - Machine-readable API spec
4. [Code Examples](code/EXAMPLES.md) - Example code

---

## 🗂️ Documentation Directory Structure

```
docs/
├── INDEX.md                          # This file
├── README.md                         # Overview (if exists)
│
├── operations/                       # Operations Documentation
│   ├── DOCUMENTATION_PLAN.md         # Master plan
│   ├── INSTALLATION_GUIDE.md         # P1: Installation
│   ├── SERVICE_OPERATIONS.md         # P1: Service management
│   ├── TROUBLESHOOTING_GUIDE.md      # P1: Troubleshooting
│   ├── CONFIG_MANAGEMENT.md          # P2: Configuration
│   ├── MONITORING_ALERTING.md        # P2: Monitoring setup
│   ├── BACKUP_RECOVERY.md            # P2: Disaster recovery
│   └── INCIDENT_RESPONSE.md          # P2: Incident procedures
│
├── architecture/                     # Architecture Documentation
│   ├── SYSTEM_ARCHITECTURE.md        # System overview
│   ├── DESIGN_RATIONALE.md           # Design decisions
│   ├── INTEGRATION_PATTERNS.md       # Integration guide
│   ├── SCALABILITY_GUIDE.md          # Scaling strategies
│   ├── DEPLOYMENT_ARCHITECTURE.md    # Deployment models
│   └── EVOLUTION_ROADMAP.md          # Future roadmap
│
├── api/                              # API Documentation
│   ├── REFERENCE.md                  # API reference
│   ├── openapi.yaml                  # OpenAPI spec
│   └── redoc.html                    # Interactive docs
│
├── code/                             # Code Documentation
│   ├── MODULES.md                    # Module docs
│   └── EXAMPLES.md                   # Code examples
│
├── db/                               # Database Documentation
│   └── SCHEMA.md                     # Database schema
│
├── dev/                              # Developer Documentation
│   └── ONBOARDING.md                 # Developer onboarding
│
├── adr/                              # Architecture Decision Records
│   ├── README.md                     # ADR index
│   ├── ADR_TEMPLATE.md               # ADR template
│   ├── ADR-001-redis-vs-kafka.md
│   ├── ADR-002-vault-vs-k8s-secrets.md
│   ├── ADR-003-single-threaded-workers.md
│   ├── ADR-004-postgres-for-audit-logs.md
│   ├── ADR-005-circuit-breaker-moog-forwarder.md
│   └── ADR-006-api-versioning.md
│
├── prometheus/                       # Prometheus Configuration
│   └── README.md                     # Prometheus docs
│
├── images/                           # Diagrams and Images
│   └── README.md                     # Image index
│
└── (root docs/)/                     # Individual Guides
    ├── DEV_QUICKSTART.md
    ├── ONCALL_RUNBOOK.md
    ├── DATA_RETENTION_GUIDE.md
    ├── DYNAMIC_CONFIG_USAGE.md
    ├── ALERTER_BACKPRESSURE.md
    ├── SLOs.md
    └── ... (and more)
```

---

## 📈 Documentation Statistics

**Total Documentation:**
- **Operations Guides:** 8 documents (~170 pages)
- **Architecture Guides:** 6 documents (~110 pages)
- **API Documentation:** 3 documents
- **Code Documentation:** 3 documents
- **ADRs:** 6 decision records
- **Developer Guides:** 5 documents
- **Feature Guides:** 10+ documents

**Total:** ~50+ documentation files, ~300+ pages

---

## 🔍 Finding What You Need

### Search by Topic

- **Installation:** [Installation Guide](operations/INSTALLATION_GUIDE.md)
- **Configuration:** [Configuration Management](operations/CONFIG_MANAGEMENT.md), [Dynamic Config Usage](DYNAMIC_CONFIG_USAGE.md)
- **Monitoring:** [Monitoring & Alerting Setup](operations/MONITORING_ALERTING.md)
- **Troubleshooting:** [Troubleshooting Guide](operations/TROUBLESHOOTING_GUIDE.md)
- **Backup:** [Backup & Recovery](operations/BACKUP_RECOVERY.md)
- **Incidents:** [Incident Response](operations/INCIDENT_RESPONSE.md)
- **Architecture:** [System Architecture](architecture/SYSTEM_ARCHITECTURE.md)
- **API:** [API Reference](api/REFERENCE.md)
- **Scaling:** [Scalability Guide](architecture/SCALABILITY_GUIDE.md), [Service Operations](operations/SERVICE_OPERATIONS.md)
- **Security:** [Secret Rotation](SECRET_ROTATION_PROCEDURE.md), [Vault Integration](operations/CONFIG_MANAGEMENT.md#secrets-management)

### Search by Deployment Model

- **Standalone RHEL (Primary):** [Installation Guide](operations/INSTALLATION_GUIDE.md), [Deployment Architecture](architecture/DEPLOYMENT_ARCHITECTURE.md)
- **Kubernetes/OpenShift:** [Deployment Architecture](architecture/DEPLOYMENT_ARCHITECTURE.md)
- **Docker Compose (Dev):** [DEV_QUICKSTART.md](DEV_QUICKSTART.md)

---

## 📞 Getting Help

**Documentation Issues:**
- Report missing or incorrect documentation via internal ticketing system
- Suggest improvements in team meetings or Slack

**Technical Support:**
- On-call: Use PagerDuty
- Non-urgent: #mutt-support Slack channel
- Email: mutt-ops@example.com

**Contributing to Docs:**
- Follow [Development Standards](DEVELOPMENT_STANDARDS.md)
- Use [ADR Template](adr/ADR_TEMPLATE.md) for architectural decisions
- Update this index when adding new documentation


