# MUTT v2.5 - Incident Response Runbook

**Target Audience:** On-Call Engineers, Incident Commanders, Operations Team
**Priority Level:** P2 (High)
**Last Updated:** 2025-11-10

---

## Table of Contents

1. [Overview](#overview)
2. [Incident Classification](#incident-classification)
3. [Incident Response Process](#incident-response-process)
4. [On-Call Procedures](#on-call-procedures)
5. [Communication Protocols](#communication-protocols)
6. [Common Incident Scenarios](#common-incident-scenarios)
7. [Post-Incident Procedures](#post-incident-procedures)
8. [Escalation Procedures](#escalation-procedures)

---

## Overview

This runbook provides step-by-step procedures for responding to MUTT production incidents. Follow these procedures to minimize impact, restore service, and prevent recurrence.

### Incident Response Goals

1. **Minimize Impact**: Reduce scope and duration of incidents
2. **Restore Service**: Return to normal operations as quickly as possible
3. **Preserve Evidence**: Capture logs, metrics, and state for root cause analysis
4. **Communicate Clearly**: Keep stakeholders informed
5. **Learn and Improve**: Conduct post-incident reviews to prevent recurrence

### Key Contacts

| Role | Primary | Secondary | Contact Method |
|------|---------|-----------|----------------|
| **Incident Commander** | John Smith | Jane Doe | PagerDuty, Phone |
| **On-Call Engineer** | (Rotation) | (Rotation) | PagerDuty |
| **Database DBA** | Mike Johnson | Sarah Lee | Phone, Email |
| **Infrastructure Team** | ops-team@example.com | | Email, Slack |
| **Development Team** | dev-team@example.com | | Email, Slack |
| **Management** | Director of Ops | VP Engineering | Phone (P1 only) |

**Emergency Contact List:** https://wiki.internal/mutt/contacts

---

## Incident Classification

### Severity Levels

| Severity | Impact | Response Time | Examples |
|----------|--------|---------------|----------|
| **P1 (Critical)** | Total service outage, data loss, security breach | Immediate (< 5 min) | Ingestor down, database corruption, unauthorized access |
| **P2 (High)** | Major functionality degraded, significant performance impact | < 15 minutes | High error rate, slow processing, DLQ growing rapidly |
| **P3 (Medium)** | Minor functionality affected, workaround available | < 1 hour | Single component degraded, elevated latency |
| **P4 (Low)** | Minimal impact, planned maintenance, questions | < 4 hours | Informational alerts, minor config changes |

---

### Severity Assessment Criteria

**P1 - Critical:**
- ✅ Ingestor cannot accept new events
- ✅ Alerter completely stopped processing
- ✅ Database unavailable
- ✅ Data loss or corruption detected
- ✅ Security incident (unauthorized access, data breach)
- ✅ SLO breach > 5% below target for > 30 minutes

**P2 - High:**
- ✅ Ingest error rate > 5% for > 5 minutes
- ✅ Processing severely degraded (queue growing rapidly)
- ✅ Moog forwarder circuit breaker open > 10 minutes
- ✅ DLQ depth > 1,000 messages
- ✅ SLO breach > 2% below target for > 15 minutes

**P3 - Medium:**
- ✅ Single service instance down (others healthy)
- ✅ Elevated latency (P95 > 1 second)
- ✅ High unhandled event rate (> 10%)
- ✅ Non-critical component failure (Web UI, Remediation)

**P4 - Low:**
- ✅ Informational alerts
- ✅ Planned maintenance notifications
- ✅ Configuration questions

---

## Incident Response Process

### OODA Loop

Follow the **OODA Loop** (Observe, Orient, Decide, Act):

```
  OBSERVE          ORIENT           DECIDE           ACT
     │                │                │              │
     │   Gather       │   Analyze      │   Choose     │   Execute
     │   data,        │   symptoms,    │   response   │   actions,
     │   check        │   correlate    │   plan       │   monitor
     │   metrics      │   events       │              │   results
     │                │                │              │
     └────────────────┴────────────────┴──────────────┘
                         │
                         │ (Repeat until resolved)
                         v
```

---

### Step-by-Step Response

**Step 1: Acknowledge Incident**

```bash
# Via PagerDuty
- Click "Acknowledge" button

# Via Alertmanager
curl -X POST http://alertmanager:9093/api/v1/alerts \
  -d '[{"labels": {"alertname": "..."}, "status": "ack"}]'

# Document incident start time
INCIDENT_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "Incident started at: $INCIDENT_START"
```

---

**Step 2: Assess Severity**

```bash
# Check service status
for service in mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui; do
    systemctl is-active $service && echo "$service: UP" || echo "$service: DOWN"
done

# Check queue depths
echo "Ingest Queue: $(redis-cli LLEN mutt:ingest_queue)"
echo "Alert Queue: $(redis-cli LLEN mutt:alert_queue)"
echo "Moog DLQ: $(redis-cli LLEN mutt:dlq:moog)"

# Check error rates
curl -s http://localhost:9090/api/v1/query?query='rate(mutt_ingest_requests_total{status="fail"}[5m])' | jq .

# Determine severity (P1/P2/P3/P4)
```

---

**Step 3: Notify Stakeholders**

```bash
# P1: Immediate notification
- PagerDuty alert (automatic)
- Post in #mutt-incidents Slack channel
- Email ops-team@example.com with subject: "[P1] MUTT Incident - <brief description>"
- Call Incident Commander if unavailable

# P2: Urgent notification
- PagerDuty alert (automatic)
- Post in #mutt-incidents Slack channel
- Email ops-team@example.com

# P3/P4: Standard notification
- Post in #mutt-alerts Slack channel
- Update ticket in incident tracking system
```

**Incident Notification Template (Slack):**

```
🚨 **P1 INCIDENT**
Service: MUTT Ingestor
Impact: Cannot ingest new events
Start Time: 2025-11-10 14:35 UTC
On-Call: @john-smith
Incident Commander: @jane-doe
War Room: #incident-20251110-001

Initial Assessment:
- Ingestor service down on all hosts
- Root cause under investigation
- Estimated time to resolution: TBD

Updates will be posted every 15 minutes.
```

---

**Step 4: Initiate Response**

```bash
# Create incident war room (Slack)
/create-channel incident-$(date +%Y%m%d-%H%M)

# Start incident log
echo "$(date -u): Incident acknowledged, severity P1" >> /tmp/incident.log
echo "$(date -u): Services checked, ingestor down" >> /tmp/incident.log

# Begin troubleshooting (see Common Incident Scenarios below)
```

---

**Step 5: Implement Fix**

```bash
# Document all actions in incident log
echo "$(date -u): Action: Restarting ingestor service" >> /tmp/incident.log

# Execute fix (example: restart service)
sudo systemctl restart mutt-ingestor

# Verify fix
echo "$(date -u): Verification: Health check passed" >> /tmp/incident.log
curl http://localhost:8080/health
```

---

**Step 6: Monitor and Validate**

```bash
# Monitor for 15 minutes to ensure stability
watch -n 30 'curl -s http://localhost:8080/health && echo "Healthy" || echo "Unhealthy"'

# Check metrics for normal operation
curl -s http://localhost:9090/api/v1/query?query='rate(mutt_ingest_requests_total{status="success"}[5m])'

# Verify no new errors
sudo journalctl -u mutt-ingestor --since "5 minutes ago" | grep -i error
```

---

**Step 7: Resolve and Close**

```bash
# Post resolution update
# Slack #mutt-incidents:
✅ **RESOLVED**
Service: MUTT Ingestor
Duration: 23 minutes
Root Cause: Service crashed due to memory exhaustion
Fix: Restarted service, increased memory limit
Follow-up: Post-incident review scheduled for 2025-11-11 10:00 UTC

# Mark incident resolved in PagerDuty
# Create post-incident review ticket
# Update incident log with final timeline
```

---

## On-Call Procedures

### On-Call Rotation

**Schedule:** 7-day rotations, 24/7 coverage

**Handoff Checklist:**
- [ ] Review open incidents from previous week
- [ ] Review current system health (dashboards, alerts)
- [ ] Verify access to all systems (VPN, SSH, PagerDuty)
- [ ] Test alert notifications (SMS, phone, email)
- [ ] Review any upcoming changes or maintenance
- [ ] Confirm secondary on-call contact information

**Handoff Command:**
```bash
# Run weekly handoff report
/usr/local/bin/mutt-handoff-report.sh

# Output:
# - Open incidents
# - Recent alerts (last 7 days)
# - Upcoming maintenance windows
# - System health summary
```

---

### On-Call Responsibilities

**During On-Call Shift:**
- ✅ Respond to PagerDuty alerts within SLA (P1: 5 min, P2: 15 min)
- ✅ Acknowledge all alerts (even if resolved)
- ✅ Escalate to Incident Commander for P1 incidents
- ✅ Document all actions in incident log
- ✅ Post updates to stakeholders regularly
- ✅ Create follow-up tickets for non-urgent issues

**After On-Call Shift:**
- ✅ Complete post-incident reviews for all incidents
- ✅ Handoff open incidents to next on-call
- ✅ Submit expense reports for any on-call costs

---

### Escalation Criteria

Escalate to **Incident Commander** if:
- Severity is P1
- Incident duration > 30 minutes without resolution
- Multiple systems affected
- External dependencies involved (Moogsoft, infrastructure)
- Uncertain about next steps

Escalate to **Subject Matter Expert** if:
- Database issues (DBA team)
- Infrastructure issues (SRE team)
- Application bugs (Development team)
- Security incidents (Security team)

---

## Communication Protocols

### Update Frequency

| Severity | Update Frequency | Channels |
|----------|------------------|----------|
| **P1** | Every 15 minutes | Slack, Email, PagerDuty |
| **P2** | Every 30 minutes | Slack, PagerDuty |
| **P3** | Every hour | Slack |
| **P4** | As needed | Ticket updates |

---

### Communication Templates

**Initial Notification (P1):**

```
Subject: [P1 INCIDENT] MUTT - <Brief Description>

IMPACT:
- Services Affected: <Ingestor/Alerter/Moog Forwarder>
- User Impact: <Cannot ingest events / Delays in processing>
- Estimated Affected Users: <All / Partial>

STATUS:
- Incident Start Time: 2025-11-10 14:35 UTC
- Current Status: Investigating
- On-Call Engineer: John Smith
- Incident Commander: Jane Doe

ACTIONS TAKEN:
1. Services checked - ingestor down on all hosts
2. Reviewing logs and metrics
3. War room created: #incident-20251110-001

NEXT STEPS:
- Investigate root cause
- Restart services if appropriate
- Next update in 15 minutes

War Room: #incident-20251110-001
```

---

**Progress Update:**

```
UPDATE #2 - 14:50 UTC (15 minutes into incident)

STATUS: Still investigating

FINDINGS:
- Root cause identified: Memory exhaustion on ingestor hosts
- Memory usage spiked to 95% at 14:32 UTC
- Service OOM-killed by kernel at 14:35 UTC

ACTIONS:
- Restarting ingestor services on all hosts
- Increasing memory limits from 4GB to 8GB

NEXT STEPS:
- Monitor service stability for 15 minutes
- Review memory usage patterns to prevent recurrence
- Next update in 15 minutes
```

---

**Resolution Notification:**

```
✅ RESOLVED - 15:05 UTC

INCIDENT SUMMARY:
- Duration: 30 minutes
- Impact: Unable to ingest new events
- Root Cause: Memory exhaustion due to traffic spike
- Fix: Service restarted, memory limits increased

TIMELINE:
- 14:35 UTC: Incident detected (PagerDuty alert)
- 14:40 UTC: On-call acknowledged, investigation started
- 14:50 UTC: Root cause identified
- 14:55 UTC: Services restarted with increased memory
- 15:00 UTC: Services verified healthy
- 15:05 UTC: Incident resolved

FOLLOW-UP ACTIONS:
- Post-incident review scheduled for 2025-11-11 10:00 UTC
- Ticket created to implement memory monitoring alerts
- Runbook updated with memory exhaustion procedures

Thank you for your patience.
```

---

## Common Incident Scenarios

### Scenario 1: Ingestor Service Down

**Symptoms:**
- PagerDuty alert: "MUTTIngestorDown"
- Cannot reach `http://localhost:8080/health`
- Events not being ingested

**Immediate Actions:**

```bash
# 1. Check service status
sudo systemctl status mutt-ingestor

# 2. Check recent logs
sudo journalctl -u mutt-ingestor -n 100 --no-pager | tail -50

# 3. Check for OOM kills
sudo dmesg | grep -i "mutt.*killed"

# 4. Check resource usage
ps aux | grep ingestor
df -h /
free -h

# 5. Restart service
sudo systemctl restart mutt-ingestor

# 6. Verify health
curl http://localhost:8080/health

# 7. Monitor for stability
watch -n 10 'curl -s http://localhost:8080/health && echo "Healthy"'
```

**Root Cause Investigation:**

```bash
# Check for configuration errors
/usr/local/bin/validate_mutt_config.sh

# Check Vault connectivity
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
curl -s -k "$vault_addr/v1/sys/health"

# Check Redis connectivity
redis-cli PING

# Review error patterns in logs
sudo journalctl -u mutt-ingestor --since "1 hour ago" | grep -i error | sort | uniq -c
```

**Escalation:** If restart doesn't resolve, escalate to Incident Commander

**Estimated Resolution Time:** 5-15 minutes

---

### Scenario 2: High Ingest Error Rate

**Symptoms:**
- PagerDuty alert: "MUTTIngestHighErrorRate"
- Prometheus: `rate(mutt_ingest_requests_total{status="fail"}[5m]) > 0.05`
- Increased 4xx/5xx responses

**Immediate Actions:**

```bash
# 1. Check error reasons
curl -s http://localhost:9090/metrics | grep 'mutt_ingest_requests_total{status="fail"' | sort

# 2. Check queue depth (backpressure?)
redis-cli LLEN mutt:ingest_queue

# 3. Check for authentication issues
sudo journalctl -u mutt-ingestor -n 100 | grep -i "auth\|401\|403"

# 4. Check for Redis issues
redis-cli PING
redis-cli INFO memory

# 5. Sample recent errors
sudo journalctl -u mutt-ingestor --since "5 minutes ago" | grep ERROR | head -20
```

**Common Causes and Fixes:**

**Cause: API Key Issues**
```bash
# Verify Vault secrets
vault kv get secret/mutt/prod | grep INGEST_API_KEY

# Restart ingestor to reload secrets
sudo systemctl restart mutt-ingestor
```

**Cause: Backpressure (Queue Full)**
```bash
# Check queue vs cap
QUEUE_DEPTH=$(redis-cli LLEN mutt:ingest_queue)
QUEUE_CAP=$(grep INGEST_QUEUE_CAP /etc/mutt/mutt.env | cut -d= -f2)
echo "Queue: $QUEUE_DEPTH / $QUEUE_CAP"

# Scale alerter to process faster (see Service Operations Guide)
# OR increase queue cap temporarily
sudo vi /etc/mutt/mutt.env
# INGEST_QUEUE_CAP=2000000
sudo systemctl restart mutt-ingestor
```

**Cause: Redis Connectivity Issues**
```bash
# Check Redis status
sudo systemctl status redis

# Check Redis latency
redis-cli --latency-history

# Restart Redis if needed
sudo systemctl restart redis
sudo systemctl restart mutt-ingestor
```

**Escalation:** If error rate > 10% for > 15 minutes, escalate to P1

**Estimated Resolution Time:** 10-30 minutes

---

### Scenario 3: Queue Backlog Growing

**Symptoms:**
- PagerDuty alert: "MUTTIngestQueueGrowing"
- Prometheus: `deriv(mutt_ingest_queue_depth[5m]) > 1000`
- Ingest queue depth increasing rapidly

**Immediate Actions:**

```bash
# 1. Check current queue depth
redis-cli LLEN mutt:ingest_queue

# 2. Check alerter status
sudo systemctl status mutt-alerter

# 3. Check alerter processing rate
curl -s http://localhost:9091/metrics | grep mutt_alerter_events_processed_total

# 4. Check for alerter errors
sudo journalctl -u mutt-alerter -n 100 | grep -i error

# 5. Check PostgreSQL connectivity (alerter dependency)
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT 1;"
```

**Root Cause Investigation:**

```bash
# Check if alerter is stuck
POD_NAME=$(grep POD_NAME /etc/mutt/mutt.env | cut -d= -f2)
PROCESSING_LIST="mutt:processing:alerter:$POD_NAME"
redis-cli LLEN "$PROCESSING_LIST"
# If > 0 and not changing, alerter is stuck

# Check alerter CPU/memory
ps aux | grep alerter | awk '{print $3, $4}'

# Check rule cache reload
sudo journalctl -u mutt-alerter -n 200 | grep -i "cache.*reload"
```

**Remediation:**

```bash
# If alerter stuck, restart
sudo systemctl restart mutt-alerter

# If alerter slow, check database performance
sudo -u postgres psql -U mutt_user -d mutt <<EOF
SELECT query, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
EOF

# If high traffic is legitimate, scale alerter horizontally
# (See Service Operations Guide - Scaling section)
```

**Escalation:** If queue > 500,000 messages, escalate to P2

**Estimated Resolution Time:** 15-45 minutes

---

### Scenario 4: Moog Forwarder Circuit Breaker Open

**Symptoms:**
- PagerDuty alert: "MUTTMoogCircuitBreakerOpen"
- Prometheus: `mutt_moog_circuit_breaker_state{name="moogsoft"} == 1`
- DLQ depth growing

**Immediate Actions:**

```bash
# 1. Check circuit breaker state
curl -s http://localhost:9092/metrics | grep mutt_moog_circuit_breaker

# 2. Check DLQ depth
redis-cli LLEN mutt:dlq:moog

# 3. Check Moogsoft connectivity
MOOG_URL=$(grep MOOG_WEBHOOK_URL /etc/mutt/mutt.env | cut -d= -f2)
curl -I "$MOOG_URL"

# 4. Check moog forwarder logs
sudo journalctl -u mutt-moog-forwarder -n 100 | grep -i "moog\|circuit"
```

**Root Cause Investigation:**

```bash
# Check failure reasons
curl -s http://localhost:9092/metrics | grep 'mutt_moog_requests_total{status="fail"'

# Common reasons:
# - http: Moogsoft unavailable or returning errors
# - rate_limit: Hitting rate limit
# - retry_exhausted: Retries exceeded
# - circuit_open: Circuit breaker protection
```

**Remediation:**

**If Moogsoft is Down:**
```bash
# Contact Moogsoft team/vendor
# Circuit breaker will auto-retry after timeout (default: 5 minutes)
# Messages are safely in DLQ, will be replayed by remediation service

# Monitor DLQ depth
watch -n 30 'redis-cli LLEN mutt:dlq:moog'

# Verify remediation service is running
sudo systemctl status mutt-remediation
```

**If Moogsoft is Slow:**
```bash
# Increase timeout
sudo vi /etc/mutt/mutt.env
MOOG_TIMEOUT=30  # Increase from 10

sudo systemctl restart mutt-moog-forwarder
```

**If Rate Limiting:**
```bash
# Increase rate limit
sudo vi /etc/mutt/mutt.env
RATE_LIMIT_MAX_REQUESTS=200  # Increase from 100

sudo systemctl restart mutt-moog-forwarder
```

**Manual Circuit Breaker Reset (If Moogsoft is Healthy):**
```bash
# Verify Moogsoft is healthy
curl -I "$MOOG_URL"
# Expected: 2xx response

# Restart forwarder to reset circuit
sudo systemctl restart mutt-moog-forwarder

# Monitor circuit state
watch -n 10 'curl -s http://localhost:9092/metrics | grep mutt_moog_circuit_breaker_state'
```

**Escalation:** If DLQ > 5,000 messages, escalate to P2

**Estimated Resolution Time:** 10-30 minutes (or wait for Moogsoft recovery)

---

### Scenario 5: Database Connection Exhaustion

**Symptoms:**
- PagerDuty alert (alerter/webui errors)
- Logs: "FATAL: sorry, too many clients already"
- Services unable to query database

**Immediate Actions:**

```bash
# 1. Check current connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# 2. Check max connections
sudo -u postgres psql -c "SHOW max_connections;"

# 3. Kill idle connections
sudo -u postgres psql <<EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < NOW() - INTERVAL '10 minutes'
AND pid <> pg_backend_pid();
EOF

# 4. Restart affected services
sudo systemctl restart mutt-alerter mutt-webui
```

**Long-Term Fix:**

```bash
# Increase max_connections
sudo vi /var/lib/pgsql/data/postgresql.conf
max_connections = 200  # Increase from 100

# OR implement PgBouncer (recommended)
# (See Configuration Management Guide)

sudo systemctl restart postgresql
```

**Escalation:** If cannot restore within 15 minutes, escalate to DBA team

**Estimated Resolution Time:** 10-20 minutes

---

## Post-Incident Procedures

### Post-Incident Review (PIR)

**Schedule:** Within 48 hours of incident resolution

**Participants:**
- Incident Commander
- On-Call Engineer(s)
- Service Owners
- Stakeholders (if major impact)

**Agenda:**

1. **Timeline Review** (10 minutes)
   - What happened and when?
   - Duration of incident and impact

2. **Root Cause Analysis** (15 minutes)
   - What was the root cause?
   - Why did it happen?
   - Could it have been detected earlier?

3. **Response Evaluation** (10 minutes)
   - What went well?
   - What could have been better?
   - Was communication effective?

4. **Action Items** (15 minutes)
   - What can prevent this from happening again?
   - What monitoring/alerting is needed?
   - What documentation needs updating?

5. **Follow-Up** (5 minutes)
   - Assign action items with owners and due dates
   - Schedule follow-up review if needed

---

### Post-Incident Report Template

```markdown
# Post-Incident Report: [Incident Title]

**Incident ID:** INC-20251110-001
**Severity:** P1
**Date:** 2025-11-10
**Duration:** 30 minutes (14:35 - 15:05 UTC)
**Status:** Resolved

---

## Executive Summary

MUTT Ingestor service experienced a complete outage for 30 minutes due to memory exhaustion. All event ingestion was halted during this period. Service was restored by restarting with increased memory limits.

---

## Impact

- **Services Affected:** Ingestor
- **User Impact:** Unable to ingest new events for 30 minutes
- **Events Lost:** 0 (traffic queued upstream, no data loss)
- **SLO Impact:** 0.5% breach (within acceptable budget)

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:30 | Memory usage begins increasing rapidly |
| 14:35 | Service OOM-killed by kernel, PagerDuty alert fires |
| 14:36 | On-call acknowledges alert, begins investigation |
| 14:40 | Root cause identified (memory exhaustion) |
| 14:50 | Service restarted with increased memory limits |
| 14:55 | Service verified healthy |
| 15:00 | Monitoring period begins (15 min) |
| 15:05 | Incident declared resolved |

---

## Root Cause

Unexpected traffic spike (3× normal volume) from new data source caused memory consumption to exceed 4GB limit. Service did not have memory limit alerts configured, so issue was not detected until OOM kill occurred.

---

## Contributing Factors

1. No memory usage monitoring/alerting
2. Memory limits too low for traffic spikes
3. No auto-scaling configured
4. New data source not load-tested before production

---

## What Went Well

✅ PagerDuty alert fired immediately when service went down
✅ On-call responded within 1 minute
✅ Root cause identified quickly via dmesg logs
✅ No data loss (events queued upstream)
✅ Resolution faster than RTO (30 min vs 60 min target)

---

## What Could Be Improved

❌ No proactive memory alerts (only reactive after OOM)
❌ Memory limits too conservative
❌ No runbook for memory exhaustion scenario
❌ Lack of auto-scaling for traffic spikes

---

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| Add Prometheus alert for memory usage > 80% | @ops-team | 2025-11-12 | Open |
| Increase memory limits to 8GB on all hosts | @ops-team | 2025-11-11 | Done |
| Update runbook with memory exhaustion procedure | @docs-team | 2025-11-13 | Open |
| Implement horizontal auto-scaling (Kubernetes) | @infra-team | 2025-12-01 | Open |
| Load test new data sources before production | @dev-team | Ongoing | Open |

---

## Lessons Learned

1. **Proactive monitoring is critical**: Alerting on resource exhaustion before failure is essential
2. **Capacity planning matters**: Conservative limits are good, but must account for traffic variability
3. **Documentation helps**: Runbooks should cover common failure modes like OOM kills
4. **Testing prevents surprises**: Load testing new data sources would have caught this

---

**Report Author:** John Smith (On-Call Engineer)
**Reviewed By:** Jane Doe (Incident Commander)
**Date:** 2025-11-11
```

---

## Escalation Procedures

### When to Escalate

Escalate to **Incident Commander** when:
- ✅ Severity is P1
- ✅ Incident duration > 30 minutes with no resolution
- ✅ Multiple systems affected
- ✅ Unclear next steps or need expertise
- ✅ External dependencies involved

Escalate to **Subject Matter Expert** when:
- ✅ Database issues → DBA Team
- ✅ Infrastructure issues → SRE Team
- ✅ Application bugs → Development Team
- ✅ Security incidents → Security Team
- ✅ Vendor issues → Vendor Support

Escalate to **Management** when:
- ✅ P1 incident > 1 hour duration
- ✅ Customer-facing impact
- ✅ Data breach or security incident
- ✅ Potential regulatory implications

---

### Escalation Contact Methods

**Incident Commander:**
1. PagerDuty (primary)
2. Phone call (if no response in 5 minutes)
3. Slack DM + mention in #incidents

**Subject Matter Experts:**
1. Slack mention in war room channel
2. Email with [URGENT] prefix
3. Phone call if critical

**Management:**
1. Phone call (P1 only)
2. Email with status update
3. Slack notification (informational)

---

### Escalation Script

```
Hi [Name],

I'm escalating this incident to you as Incident Commander.

Incident: MUTT Ingestor Down
Severity: P1
Duration: 35 minutes (and counting)
Impact: Cannot ingest new events

What I've tried:
- Restarted ingestor service (no effect)
- Checked Vault, Redis, config (all healthy)
- Reviewed logs (no clear errors)

I need help with:
- Advanced troubleshooting
- Potential infrastructure issues
- Decision on next steps

War room: #incident-20251110-001
Incident log: /tmp/incident-20251110-001.log
```

---

## Summary

### Incident Response Checklist

**During Incident:**
- [ ] Acknowledge alert within SLA
- [ ] Assess severity (P1/P2/P3/P4)
- [ ] Notify stakeholders
- [ ] Create war room (P1/P2)
- [ ] Start incident log
- [ ] Investigate root cause
- [ ] Implement fix
- [ ] Monitor and validate (15+ minutes)
- [ ] Post resolution update
- [ ] Mark resolved in PagerDuty

**After Incident:**
- [ ] Complete incident log with timeline
- [ ] Schedule post-incident review (within 48 hours)
- [ ] Write post-incident report
- [ ] Create action item tickets
- [ ] Update runbooks/documentation
- [ ] Share learnings with team

---

## Next Steps

For additional operational guidance:

1. **Service Operations**: [SERVICE_OPERATIONS.md](SERVICE_OPERATIONS.md) - Service management, scaling
2. **Troubleshooting**: [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Detailed problem diagnosis
3. **Configuration Management**: [CONFIG_MANAGEMENT.md](CONFIG_MANAGEMENT.MD) - Config, secrets
4. **Monitoring & Alerting**: [MONITORING_ALERTING.md](MONITORING_ALERTING.md) - Prometheus, alerts
5. **Backup & Recovery**: [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) - Disaster recovery

---

**Document Metadata:**
- **Version**: 1.0
- **Last Updated**: 2025-11-10
- **Maintainer**: MUTT Operations Team
- **Feedback**: Report issues via internal ticketing system
