# Documentation Task: Architecture & Design Documentation Suite

**To:** Gemini (Architect)
**From:** Claude (Software Engineer)
**Role:** You are the architect for MUTT v2.5, responsible for creating high-level architecture and design documentation
**Task Type:** Documentation Creation (Phase 1 of 3-phase documentation effort)

---

## Mission Statement

Create comprehensive architecture and design documentation that enables:
1. **Microsoft Copilot** (next AI tool) to understand system design and provide guidance
2. **Human engineers** (new team members) to understand system architecture quickly
3. **Operations teams** to understand how components interact and scale
4. **Future developers** to understand design decisions and constraints

Your documentation will be the **foundation** that all other documentation builds upon.

---

## Project Context

### What is MUTT?

MUTT (Multi-Use Telemetry Tool) is a production-grade, horizontally scalable event processing system for network operations:
- **Ingests** syslog and SNMP trap events
- **Processes** events using intelligent rule-based routing
- **Forwards** alerts to Moogsoft AIOps platform
- **Manages** configuration dynamically at runtime
- **Provides** Web UI for rules, metrics, and operations

### Current State (v2.5)

**Technology Stack:**
- **Languages:** Python 3.10+
- **Message Queue:** Redis (Lists, PubSub, with AOF persistence)
- **Database:** PostgreSQL 14+ (partitioned audit logs)
- **Secrets:** HashiCorp Vault
- **Monitoring:** Prometheus + Grafana
- **Deployment:** Docker Compose, RHEL systemd, Kubernetes/OpenShift

**Architecture Pattern:**
- Microservices with Redis-based reliable queuing (BRPOPLPUSH)
- Stateless workers with horizontal scalability
- In-memory caching with hot-reload (SIGHUP)
- Janitor pattern for crash recovery
- Backpressure handling with DLQs

**Key Services:**
1. **Ingestor** - HTTP endpoint for event ingestion (Port 8080)
2. **Alerter** - Rule matching and processing (Ports 8081/8082)
3. **Moog Forwarder** - External system integration with rate limiting (Ports 8083/8084)
4. **Web UI** - Management interface and dashboard (Port 8090)
5. **Remediation** - DLQ processing and recovery (Ports 8086/8087)

### Design Decisions Already Made

Review these ADRs (Architecture Decision Records) for context:
- `docs/adr/ADR-001-redis-vs-kafka.md` - Why Redis over Kafka
- `docs/adr/ADR-002-vault-vs-k8s-secrets.md` - Why Vault for secrets
- `docs/adr/ADR-003-single-threaded-workers.md` - Why single-threaded workers
- `docs/adr/ADR-004-postgres-for-audit-logs.md` - Why PostgreSQL for audit
- `docs/adr/ADR-005-circuit-breaker-moog-forwarder.md` - Circuit breaker pattern

### Recent Achievements (Phase 5-6)

- Dynamic configuration with Redis PubSub
- API versioning framework (v1 deprecated, v2 active)
- Multi-OS CI pipeline (Ubuntu, Windows / Python 3.10, 3.12)
- Code coverage enforcement via Codecov
- Developer CLI (`muttdev`) for operations
- Comprehensive test suite

---

## Your Documentation Deliverables

Create the following documents in `docs/architecture/` directory:

### 1. SYSTEM_ARCHITECTURE.md (Priority: CRITICAL)

**Purpose:** High-level system design overview

**Required Sections:**
- **System Overview** (2-3 paragraphs)
  - What MUTT does at a business level
  - Target users (Network operations teams, SREs)
  - Key capabilities and benefits

- **Architecture Diagram Description**
  - Data flow from ingestion to forwarding
  - Component interactions
  - External dependencies
  - Network boundaries

- **Component Architecture**
  - Each service's role and responsibility
  - Why each service exists (the "why" not just "what")
  - Scalability model for each component
  - Failure modes and recovery patterns

- **Data Flow Patterns**
  - Event ingestion path
  - Alert processing pipeline
  - Configuration update propagation
  - Metrics collection flow

- **Reliability Patterns**
  - BRPOPLPUSH for reliable queuing
  - Janitor pattern for crash recovery
  - Heartbeat mechanism
  - DLQ (Dead Letter Queue) strategy
  - Backpressure handling

- **Scalability Architecture**
  - Horizontal scaling approach
  - Stateless worker design
  - Shared-nothing architecture
  - Bottleneck identification and mitigation

**Style Guidelines:**
- Write for someone with strong networking/SRE background but new to MUTT
- Use analogies to well-known patterns (e.g., "similar to Kafka consumer groups")
- Include "Why this matters" sections
- Avoid code-level details (that's Codex's job)

**Length:** 15-20 pages

---

### 2. DESIGN_RATIONALE.md (Priority: HIGH)

**Purpose:** Explain WHY design decisions were made

**Required Sections:**

- **Technology Selection Rationale**
  - Redis vs Kafka (expand on ADR-001)
    - Performance characteristics
    - Operational complexity
    - Cost considerations
    - When to reconsider this choice

  - Vault vs K8s Secrets (expand on ADR-002)
    - Security model
    - Rotation capabilities
    - Audit requirements
    - Cross-platform needs

  - PostgreSQL for Audit Logs (expand on ADR-004)
    - Partitioning strategy
    - Query patterns
    - Compliance requirements
    - Retention automation

  - Python as Implementation Language
    - Rapid development
    - Library ecosystem
    - Team expertise
    - Performance trade-offs

- **Architectural Patterns Rationale**

  - Single-Threaded Workers (expand on ADR-003)
    - Simplicity vs throughput
    - Debugging advantages
    - Horizontal scaling approach
    - When to consider multi-threading

  - In-Memory Caching Strategy
    - Cache invalidation approach
    - TTL selection rationale
    - SIGHUP hot-reload pattern
    - Memory vs latency trade-offs

  - Janitor Pattern for Recovery
    - Crash recovery without external coordination
    - Heartbeat expiry tuning
    - Processing list cleanup
    - Orphan message handling

  - Backpressure Design
    - Queue cap strategy
    - HTTP 503 for flow control
    - DLQ vs defer modes
    - When to shed load

  - Rate Limiting Approach
    - Shared state in Redis
    - Lua script for atomicity
    - Sliding window algorithm
    - Why not client-side rate limiting

- **Non-Functional Requirements**
  - Reliability targets and why
  - Performance targets and rationale
  - Scalability goals
  - Operational complexity constraints
  - Security requirements

- **Trade-offs and Constraints**
  - What was sacrificed for what gain
  - Known limitations and why they exist
  - Future architectural evolution paths
  - When to reconsider decisions

**Style Guidelines:**
- Be honest about trade-offs (there are no perfect solutions)
- Explain constraints that drove decisions
- Identify when decisions should be revisited
- Use "We chose X over Y because..." format

**Length:** 20-25 pages

---

### 3. INTEGRATION_PATTERNS.md (Priority: HIGH)

**Purpose:** How components communicate and integrate

**Required Sections:**

- **Inter-Service Communication**
  - Redis as message bus
  - Queue naming conventions
  - Message format specifications
  - Correlation ID propagation

- **Reliable Messaging Patterns**
  - BRPOPLPUSH mechanics
  - Processing list pattern
  - Retry and backoff strategies
  - Idempotency considerations

- **Configuration Management**
  - Dynamic config architecture
  - Redis PubSub for invalidation
  - Local caching strategy
  - Configuration reload patterns

- **Secret Management Integration**
  - Vault AppRole authentication
  - Token renewal mechanism
  - Secret rotation handling
  - Fallback strategies

- **Database Integration Patterns**
  - Connection pooling strategy
  - Transaction management
  - Partition management
  - Query optimization patterns

- **External System Integration**
  - Moogsoft webhook integration
  - Retry policies for external calls
  - Circuit breaker pattern (expand on ADR-005)
  - Error handling and DLQ

- **Observability Integration**
  - Prometheus metrics patterns
  - Structured logging approach
  - Correlation ID usage
  - Health check design

**Style Guidelines:**
- Focus on patterns, not implementation
- Show sequence diagrams (describe them in text)
- Explain failure scenarios
- Provide integration guidelines for new services

**Length:** 15-20 pages

---

### 4. SCALABILITY_GUIDE.md (Priority: MEDIUM)

**Purpose:** How to scale MUTT for different loads

**Required Sections:**

- **Scalability Model**
  - Horizontal scaling approach
  - When to scale each component
  - Resource requirements per component
  - Scaling limits and bottlenecks

- **Capacity Planning**
  - Events per second (EPS) targets
  - Resource utilization patterns
  - Redis sizing guidelines
  - PostgreSQL sizing guidelines
  - Infrastructure requirements at scale

- **Performance Characteristics**
  - Latency profiles
  - Throughput benchmarks
  - Queue depth monitoring
  - Saturation points

- **Scaling Strategies**
  - Ingestor scaling (stateless, easy)
  - Alerter scaling (cache coordination)
  - Forwarder scaling (rate limit coordination)
  - Web UI scaling (cache coherency)
  - Database scaling (read replicas, partitioning)

- **Bottleneck Identification**
  - Redis as potential bottleneck
  - PostgreSQL write throughput
  - Moogsoft rate limits
  - Network bandwidth considerations

- **Optimization Strategies**
  - Caching effectiveness
  - Batch processing opportunities
  - Connection pooling tuning
  - Redis pipeline usage

**Style Guidelines:**
- Provide actual numbers and metrics
- Include scaling decision trees
- Address both vertical and horizontal scaling
- Identify anti-patterns

**Length:** 12-15 pages

---

### 5. DEPLOYMENT_ARCHITECTURE.md (Priority: MEDIUM)

**Purpose:** How MUTT deploys in different environments

**Required Sections:**

- **Deployment Models**

  - **Standalone Server (CRITICAL - Primary Production Model)**
    - RHEL/CentOS with systemd services
    - Service installation and configuration
    - Directory structure and file locations
    - User/group setup and permissions
    - systemd unit file configuration
    - Service dependencies and startup order
    - Log file locations and rotation
    - Environment variable configuration
    - Python virtual environment setup
    - Firewall configuration (firewalld/iptables)
    - SELinux configuration considerations
    - Single-server vs multi-server topology
    - When to use standalone vs containerized

  - **Kubernetes/OpenShift**
    - Deployment manifests
    - ConfigMaps and Secrets
    - Service definitions
    - Ingress/Route configuration
    - Resource limits and requests

  - **Docker Compose (development/testing)**
    - Local development setup
    - Testing environment
    - Not recommended for production

  - **Hybrid deployments**
    - Services in containers, infrastructure standalone
    - Migration strategies

- **Infrastructure Requirements**
  - Compute resources
  - Network topology
  - Storage requirements
  - External dependencies

- **High Availability Design**
  - Redis Sentinel/Cluster
  - PostgreSQL replication (Patroni/Crunchy)
  - Vault HA configuration
  - Service redundancy

- **Network Architecture**
  - Port assignments and rationale
  - TLS termination points
  - Load balancer configuration
  - Firewall requirements

- **Data Persistence Strategy**
  - Redis AOF configuration
  - PostgreSQL backup strategy
  - Log retention
  - Metric retention

- **Security Architecture**
  - Secret distribution
  - TLS everywhere
  - API authentication
  - Network segmentation

**Style Guidelines:**
- **EMPHASIZE** standalone server deployment - this is the PRIMARY production model
- Compare deployment models (when to use each)
- Provide environment-specific guidance
- Address security at each layer
- Include network diagrams (described in text)
- Provide concrete examples (directory structures, file locations, commands)

**Critical Success Factor:** Operations teams must be able to deploy MUTT on RHEL servers using only this document and the README.

**Length:** 18-22 pages (expanded to properly cover standalone server configuration)

---

### 6. EVOLUTION_ROADMAP.md (Priority: LOW)

**Purpose:** Future architectural direction

**Required Sections:**

- **Current Limitations**
  - Known technical debt
  - Scalability ceiling
  - Feature gaps
  - Operational pain points

- **Near-Term Evolution (6-12 months)**
  - Integration test expansion
  - Service mesh consideration
  - Multi-region support
  - Enhanced observability (OpenTelemetry)

- **Medium-Term Evolution (1-2 years)**
  - Kafka migration path (if needed)
  - GraphQL API consideration
  - ML/AI integration opportunities
  - ServiceNow integration

- **Long-Term Vision (2-5 years)**
  - Event-driven architecture evolution
  - Stream processing capabilities
  - Advanced analytics
  - Self-healing automation

- **Migration Strategies**
  - How to evolve without downtime
  - Backward compatibility approach
  - Data migration patterns
  - Rollback strategies

**Style Guidelines:**
- Be realistic about timelines
- Identify triggers for evolution
  - "When EPS exceeds X, consider Y"
  - "If team grows beyond N, consider Z"
- Address business drivers, not just technical
- Provide decision frameworks

**Length:** 10-12 pages

---

## Documentation Standards

### Writing Style

**Voice and Tone:**
- Professional but approachable
- Technical but not academic
- Clear and direct (avoid fluff)
- Assume reader is intelligent but unfamiliar with MUTT

**Structure:**
- Use hierarchical headings (H1, H2, H3)
- Include table of contents for docs >10 pages
- Use bullet points for lists
- Use numbered lists for sequences/procedures
- Include "TL;DR" summaries for long sections

**Technical Content:**
- Define acronyms on first use
- Use consistent terminology (maintain glossary)
- Provide context before details
- Use real examples from the codebase
- Link to code files where relevant

### Formatting

**Code References:**
- Reference files: `services/alerter_service.py`
- Reference functions: `process_alert()`
- Reference configs: `REDIS_HOST`

**Diagrams:**
- Describe diagrams in text (ASCII art is acceptable)
- Include "Figure N: [description]" captions
- Reference figures in text ("see Figure 1")

**Cross-References:**
- Link to other docs: `See INTEGRATION_PATTERNS.md for details`
- Link to ADRs: `Refer to ADR-001 for rationale`
- Link to code: `Implementation: services/alerter_service.py:450-475`

### Metadata

Include at the top of each document:

```markdown
# [Document Title]

**Version:** 1.0
**Last Updated:** [Date]
**Status:** Draft | Review | Approved
**Audience:** Architects | Engineers | Operators
**Prerequisites:** [List other docs to read first]

---
```

---

## Context Files to Review

Before writing, thoroughly review:

### Architecture Context
- `docs/adr/*.md` - All architecture decisions
- `README.md` - System overview
- `docs/architecture.md` - Existing architecture notes (may be outdated)

### Implementation Context
- `services/*.py` - Service implementations (understand what exists)
- `docker-compose.yml` - Deployment configuration
- `.github/workflows/ci.yml` - CI/CD pipeline

### Deployment Context (CRITICAL for Standalone Server Documentation)
- `systemd/*.service` - systemd unit files (may not exist yet - document what SHOULD exist)
- `config/mutt.env.example` - Environment variable configuration examples
- `requirements.txt` - Python dependencies
- `scripts/*.sh` - Installation and setup scripts (if any exist)
- `README.md` (deployment sections) - Existing deployment guidance
- **Note**: Standalone server deployment may be incompletely documented. Your job is to specify the CORRECT architecture, even if implementation files are missing.

### Operations Context
- `docs/ONCALL_RUNBOOK.md` - Operational procedures
- `docs/DYNAMIC_CONFIG_USAGE.md` - Configuration management
- `docs/OPERATOR_VALIDATION_GUIDE.md` - Validation procedures

### Design Context
- `docs/ALERTER_BACKPRESSURE.md` - Backpressure design
- `docs/SLOs.md` - SLO definitions and monitoring
- `docs/API_VERSIONING.md` - API versioning strategy

### Status Context
- `PHASE_6_COMPLETION_STATUS.md` - Recent work completed
- `ARCHITECT_STATUS_FOR_GEMINI.md` - Your previous status update

---

## Quality Checklist

Before considering a document complete, verify:

### Technical Accuracy
- [ ] All technical claims are accurate
- [ ] Code references are correct
- [ ] Architecture diagrams match reality
- [ ] Performance numbers are realistic
- [ ] Limitations are honestly stated

### Completeness
- [ ] All required sections included
- [ ] Cross-references are complete
- [ ] Examples are provided
- [ ] Edge cases are addressed
- [ ] Future considerations mentioned

### Clarity
- [ ] Can a new engineer understand it?
- [ ] Are ambiguities resolved?
- [ ] Is terminology consistent?
- [ ] Are acronyms defined?
- [ ] Are diagrams clear?

### Usability
- [ ] Table of contents included (if >10 pages)
- [ ] Sections are logically ordered
- [ ] Headers are descriptive
- [ ] Can be read standalone (minimal cross-refs)
- [ ] Has actionable takeaways

### Integration
- [ ] Fits with existing documentation
- [ ] Links to/from related docs
- [ ] Complements (not duplicates) other docs
- [ ] Sets up Claude's operational docs
- [ ] Sets up Codex's API docs

---

## Success Criteria

Your documentation is successful if:

1. **Microsoft Copilot** can use it to answer architectural questions accurately
2. **New engineers** can understand system design in 2-3 hours of reading
3. **Operations teams** can use it to understand failure modes and scaling
4. **Future architects** can understand why decisions were made
5. **No major questions** remain unanswered about system architecture

---

## Deliverables Timeline

**Recommended Order:**
1. SYSTEM_ARCHITECTURE.md (foundation for everything else)
2. DESIGN_RATIONALE.md (explains the "why" behind the architecture)
3. INTEGRATION_PATTERNS.md (how components work together)
4. SCALABILITY_GUIDE.md (operational planning)
5. DEPLOYMENT_ARCHITECTURE.md (environmental specifics)
6. EVOLUTION_ROADMAP.md (future direction)

**Estimated Effort:**
- Total: ~90-110 pages of documentation
- Time: 2-3 days with proper context review
- Review: Allow time for technical review and iteration

---

## Next Steps After Your Work

Once you complete these documents:

1. **Claude** (Software Engineer) will create:
   - Operational runbooks
   - Troubleshooting guides
   - Developer onboarding guides
   - Procedures and checklists

2. **Codex** (OpenAI) will create:
   - API reference documentation
   - Code-level documentation
   - Database schema docs
   - Integration code examples

3. **Final Integration**: Claude will consolidate all documentation and create:
   - Master documentation index
   - Cross-reference navigation
   - Search/discovery aids
   - Documentation maintenance guide

---

## Questions or Clarifications

If anything is unclear:
- Reference the context files listed above
- Make reasonable assumptions and document them
- Mark areas needing review with `[REVIEW: ...]` comments
- Focus on architectural truth over perfection

---

## Final Notes

**Remember:**
- You're writing for the **next architect**, not just for today
- Explain the **"why"** more than the "what" (code shows the "what")
- Be **honest** about trade-offs and limitations
- Think about someone reading this in **2 years** when you're not available
- Your docs are the **foundation** that all other documentation builds on

**Your architectural documentation will determine how well future engineers understand and evolve MUTT. Make it count.**

---

**Ready to begin? Start with SYSTEM_ARCHITECTURE.md.**

Good luck! 🏗️
