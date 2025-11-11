# MUTT v2.5 - Monitoring & Alerting Setup Guide

**Target Audience:** System Administrators, DevOps Engineers, Site Reliability Engineers
**Priority Level:** P2 (High)
**Last Updated:** 2025-11-10

---

## Table of Contents

1. [Overview](#overview)
2. [Monitoring Architecture](#monitoring-architecture)
3. [Prometheus Setup](#prometheus-setup)
4. [Metrics Collection](#metrics-collection)
5. [Alerting Rules](#alerting-rules)
6. [Alert Routing and Notifications](#alert-routing-and-notifications)
7. [Grafana Dashboards](#grafana-dashboards)
8. [SLO Monitoring](#slo-monitoring)
9. [Health Check Monitoring](#health-check-monitoring)
10. [Log Monitoring](#log-monitoring)
11. [Troubleshooting Monitoring Issues](#troubleshooting-monitoring-issues)

---

## Overview

MUTT v2.5 uses a comprehensive monitoring stack to ensure system reliability and observability:

- **Metrics Collection**: Prometheus (scrapes `/metrics` endpoints)
- **Alerting**: Prometheus Alertmanager (rule-based alerting)
- **Visualization**: Grafana (dashboards and graphs)
- **Health Checks**: HTTP endpoints (monitored by Prometheus and external systems)
- **SLO Tracking**: Custom API endpoint (`/api/v1/slo`)
- **Log Monitoring**: Centralized logging (Elasticsearch/Splunk/Datadog)

### Monitoring Philosophy

**Proactive Monitoring:**
- Alert before users notice issues
- Track SLOs and error budgets
- Monitor queue depths and backpressure
- Detect anomalies and trends

**Golden Signals:**
1. **Latency**: Request processing time
2. **Traffic**: Request rate and throughput
3. **Errors**: Error rate and types
4. **Saturation**: Queue depths, CPU/memory usage

---

## Monitoring Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  MUTT Services                          │
│                                                         │
│  Ingestor:9090   Alerter:9091   Moog:9092             │
│  WebUI:8090      Remediation:8086                      │
│                                                         │
│  Each service exposes /metrics endpoint                │
└──────────────────┬──────────────────────────────────────┘
                   │ (HTTP scrape every 15s)
                   v
         ┌──────────────────┐
         │   Prometheus     │
         │   :9090          │
         │                  │
         │  - Time-series   │
         │    database      │
         │  - Recording     │
         │    rules         │
         │  - Alerting      │
         │    rules         │
         └─────┬────────────┘
               │
       ┌───────┴────────┐
       │                │
       v                v
┌──────────────┐  ┌─────────────────┐
│ Alertmanager │  │    Grafana      │
│ :9093        │  │    :3000        │
│              │  │                 │
│ - Alert      │  │  - Dashboards   │
│   routing    │  │  - Graphs       │
│ - Dedup      │  │  - Panels       │
│ - Silence    │  │                 │
└──────┬───────┘  └─────────────────┘
       │
       v
┌──────────────────────────┐
│  Notification Channels   │
│                          │
│  - Email                 │
│  - Slack                 │
│  - PagerDuty             │
│  - Webhook               │
└──────────────────────────┘
```

### Component Ports

| Component | Port | Protocol | Purpose |
|-----------|------|----------|---------|
| Prometheus | 9090 | HTTP | Metrics scraping, query API |
| Alertmanager | 9093 | HTTP | Alert routing, management |
| Grafana | 3000 | HTTP | Dashboards, visualization |
| Ingestor | 9090 | HTTP | Metrics endpoint |
| Alerter | 9091 | HTTP | Metrics endpoint |
| Moog Forwarder | 9092 | HTTP | Metrics endpoint |
| Remediation | 8086 | HTTP | Metrics endpoint |
| Web UI | 8090 | HTTP | Metrics endpoint |

---

## Prometheus Setup

### Installation (Standalone RHEL Server)

**Step 1: Install Prometheus**

```bash
# Create Prometheus user
sudo useradd --no-create-home --shell /bin/false prometheus

# Download Prometheus (version 2.45.0 or later)
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz

# Extract
tar -xzf prometheus-2.45.0.linux-amd64.tar.gz
cd prometheus-2.45.0.linux-amd64

# Copy binaries
sudo cp prometheus /usr/local/bin/
sudo cp promtool /usr/local/bin/

# Create directories
sudo mkdir -p /etc/prometheus
sudo mkdir -p /var/lib/prometheus

# Copy console files
sudo cp -r consoles /etc/prometheus/
sudo cp -r console_libraries /etc/prometheus/

# Set ownership
sudo chown -R prometheus:prometheus /etc/prometheus
sudo chown -R prometheus:prometheus /var/lib/prometheus
sudo chown prometheus:prometheus /usr/local/bin/prometheus
sudo chown prometheus:prometheus /usr/local/bin/promtool
```

---

**Step 2: Configure Prometheus**

Create `/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s       # Scrape metrics every 15 seconds
  evaluation_interval: 15s   # Evaluate rules every 15 seconds
  external_labels:
    cluster: 'mutt-prod'
    environment: 'production'

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

# Load rules
rule_files:
  - "alerts-v25.yml"
  - "recording-rules-v25.yml"

# Scrape configurations
scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # MUTT Ingestor
  - job_name: 'mutt-ingestor'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'ingestor'
          component: 'mutt'

  # MUTT Alerter
  - job_name: 'mutt-alerter'
    static_configs:
      - targets: ['localhost:9091']
        labels:
          service: 'alerter'
          component: 'mutt'

  # MUTT Moog Forwarder
  - job_name: 'mutt-moog-forwarder'
    static_configs:
      - targets: ['localhost:9092']
        labels:
          service: 'moog-forwarder'
          component: 'mutt'

  # MUTT Remediation
  - job_name: 'mutt-remediation'
    static_configs:
      - targets: ['localhost:8086']
        labels:
          service: 'remediation'
          component: 'mutt'

  # MUTT Web UI
  - job_name: 'mutt-webui'
    static_configs:
      - targets: ['localhost:8090']
        labels:
          service: 'webui'
          component: 'mutt'

  # Infrastructure: Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']  # redis_exporter
        labels:
          component: 'infrastructure'

  # Infrastructure: PostgreSQL
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']  # postgres_exporter
        labels:
          component: 'infrastructure'
```

Set ownership:
```bash
sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
```

---

**Step 3: Create systemd Service**

Create `/etc/systemd/system/prometheus.service`:

```ini
[Unit]
Description=Prometheus Monitoring System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus/ \
  --web.console.templates=/etc/prometheus/consoles \
  --web.console.libraries=/etc/prometheus/console_libraries \
  --storage.tsdb.retention.time=30d \
  --web.enable-lifecycle

ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/prometheus

[Install]
WantedBy=multi-user.target
```

**Step 4: Start Prometheus**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start Prometheus
sudo systemctl enable prometheus
sudo systemctl start prometheus

# Verify status
sudo systemctl status prometheus

# Check logs
sudo journalctl -u prometheus -f

# Verify web UI
curl http://localhost:9090/-/healthy
# Expected: Prometheus is Healthy.

# Open in browser
http://<prometheus-server>:9090
```

---

### Recording Rules

Create `/etc/prometheus/recording-rules-v25.yml`:

```yaml
groups:
  - name: mutt-slo-recording-rules
    interval: 60s
    rules:
      # Ingestor Success Rate (5m window)
      - record: mutt:ingestor:success_rate:5m
        expr: |
          sum(rate(mutt_ingest_requests_total{status="success"}[5m]))
          /
          sum(rate(mutt_ingest_requests_total[5m]))

      # Ingestor Success Rate (1h window)
      - record: mutt:ingestor:success_rate:1h
        expr: |
          sum(rate(mutt_ingest_requests_total{status="success"}[1h]))
          /
          sum(rate(mutt_ingest_requests_total[1h]))

      # Ingestor Success Rate (24h window)
      - record: mutt:ingestor:success_rate:24h
        expr: |
          sum(rate(mutt_ingest_requests_total{status="success"}[24h]))
          /
          sum(rate(mutt_ingest_requests_total[24h]))

      # Forwarder Success Rate (5m window)
      - record: mutt:forwarder:success_rate:5m
        expr: |
          sum(rate(mutt_moog_requests_total{status="success"}[5m]))
          /
          sum(rate(mutt_moog_requests_total[5m]))

      # Forwarder Success Rate (1h window)
      - record: mutt:forwarder:success_rate:1h
        expr: |
          sum(rate(mutt_moog_requests_total{status="success"}[1h]))
          /
          sum(rate(mutt_moog_requests_total[1h]))

      # Forwarder Success Rate (24h window)
      - record: mutt:forwarder:success_rate:24h
        expr: |
          sum(rate(mutt_moog_requests_total{status="success"}[24h]))
          /
          sum(rate(mutt_moog_requests_total[24h]))

      # Queue Depth Gauges
      - record: mutt:ingest_queue:depth
        expr: mutt_ingest_queue_depth

      - record: mutt:alert_queue:depth
        expr: mutt_alerter_queue_depth

      # Error Rates
      - record: mutt:ingestor:error_rate:5m
        expr: |
          sum(rate(mutt_ingest_requests_total{status="fail"}[5m]))
          by (reason)

      - record: mutt:alerter:error_rate:5m
        expr: |
          sum(rate(mutt_alerter_events_processed_total{status="error"}[5m]))

      - record: mutt:forwarder:error_rate:5m
        expr: |
          sum(rate(mutt_moog_requests_total{status="fail"}[5m]))
          by (reason)
```

Set ownership:
```bash
sudo chown prometheus:prometheus /etc/prometheus/recording-rules-v25.yml
```

---

## Metrics Collection

### Ingestor Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mutt_ingest_requests_total` | Counter | status, reason | Total ingest requests (success/fail) |
| `mutt_ingest_queue_depth` | Gauge | | Current ingest queue depth |
| `mutt_ingest_latency_seconds` | Histogram | | Request processing latency |
| `mutt_ingest_rate_limit_hits_total` | Counter | | Rate limit rejections |

**Key Queries:**

```promql
# Success rate (last 5 minutes)
rate(mutt_ingest_requests_total{status="success"}[5m])
/ rate(mutt_ingest_requests_total[5m])

# Error rate by reason
rate(mutt_ingest_requests_total{status="fail"}[5m]) by (reason)

# P95 latency
histogram_quantile(0.95, rate(mutt_ingest_latency_seconds_bucket[5m]))

# Queue depth
mutt_ingest_queue_depth
```

---

### Alerter Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mutt_alerter_events_processed_total` | Counter | status | Events processed (handled/unhandled/error/poison) |
| `mutt_alerter_alerts_forwarded_total` | Counter | | Alerts forwarded to Moog queue |
| `mutt_alerter_unhandled_meta_alerts_total` | Counter | | Unhandled meta-alerts created |
| `mutt_alerter_processing_latency_seconds` | Histogram | | Event processing latency |
| `mutt_alerter_cache_reload_latency_seconds` | Histogram | | Rule cache reload time |
| `mutt_alerter_cache_rules_count` | Gauge | | Cached rules count |
| `mutt_alerter_cache_dev_hosts_count` | Gauge | | Cached dev hosts count |
| `mutt_alerter_cache_teams_count` | Gauge | | Cached teams count |
| `mutt_alerter_queue_depth` | Gauge | | Ingest queue depth (from alerter perspective) |
| `mutt_alerter_shed_events_total` | Counter | mode | Shed events (dlq/defer) |
| `mutt_alerter_dlq_depth` | Gauge | | Alerter DLQ depth |

**Key Queries:**

```promql
# Processing rate
rate(mutt_alerter_events_processed_total[5m])

# Unhandled rate
rate(mutt_alerter_events_processed_total{status="unhandled"}[5m])

# P95 processing latency
histogram_quantile(0.95, rate(mutt_alerter_processing_latency_seconds_bucket[5m]))

# Cache size
mutt_alerter_cache_rules_count

# Backpressure shedding rate
rate(mutt_alerter_shed_events_total[5m]) by (mode)
```

---

### Moog Forwarder Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mutt_moog_requests_total` | Counter | status, reason | Moogsoft requests (success/fail) |
| `mutt_moog_request_latency_seconds` | Histogram | | Moogsoft request latency |
| `mutt_moog_dlq_depth` | Gauge | | Dead letter queue depth |
| `mutt_moog_processing_list_depth` | Gauge | | In-flight messages |
| `mutt_moog_rate_limit_hits_total` | Counter | | Rate limit hits |
| `mutt_moog_circuit_breaker_state` | Gauge | name | Circuit breaker state (0=closed, 1=open, 2=half-open) |
| `mutt_moog_circuit_breaker_failures` | Gauge | name | Circuit breaker failure count |

**Key Queries:**

```promql
# Success rate
rate(mutt_moog_requests_total{status="success"}[5m])
/ rate(mutt_moog_requests_total[5m])

# DLQ growth rate
deriv(mutt_moog_dlq_depth[5m])

# Circuit breaker open
mutt_moog_circuit_breaker_state{name="moogsoft"} > 0

# P95 latency to Moogsoft
histogram_quantile(0.95, rate(mutt_moog_request_latency_seconds_bucket[5m]))
```

---

### Remediation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mutt_remediation_loops_total` | Counter | | Remediation loops executed |
| `mutt_remediation_dlq_depth` | Gauge | dlq_name | DLQ depth being monitored |
| `mutt_remediation_replay_success_total` | Counter | | Successful DLQ replays |
| `mutt_remediation_replay_fail_total` | Counter | reason | Failed DLQ replays |
| `mutt_remediation_poison_messages_total` | Counter | | Poison messages moved to dead letter |
| `mutt_remediation_moog_health` | Gauge | | Moogsoft health (1=healthy, 0=unhealthy) |

**Key Queries:**

```promql
# DLQ replay rate
rate(mutt_remediation_replay_success_total[5m])

# Poison message rate
rate(mutt_remediation_poison_messages_total[5m])

# Moogsoft health from remediation perspective
mutt_remediation_moog_health
```

---

### Web UI Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mutt_api_requests_total` | Counter | endpoint, status | API requests to Web UI |
| `mutt_api_latency_seconds` | Histogram | endpoint | API request latency |
| `mutt_redis_scan_latency_seconds` | Histogram | | Redis SCAN operation latency |
| `mutt_db_query_latency_seconds` | Histogram | operation | PostgreSQL query latency |

**Key Queries:**

```promql
# API request rate
rate(mutt_api_requests_total[5m]) by (endpoint)

# P95 API latency
histogram_quantile(0.95, rate(mutt_api_latency_seconds_bucket[5m])) by (endpoint)

# Database query latency
histogram_quantile(0.95, rate(mutt_db_query_latency_seconds_bucket[5m])) by (operation)
```

---

## Alerting Rules

Create `/etc/prometheus/alerts-v25.yml`:

```yaml
groups:
  # Critical Alerts (P1 - Immediate Response)
  - name: mutt-critical-alerts
    interval: 30s
    rules:
      # Ingestor Down
      - alert: MUTTIngestorDown
        expr: up{job="mutt-ingestor"} == 0
        for: 1m
        labels:
          severity: critical
          service: ingestor
          component: mutt
        annotations:
          summary: "MUTT Ingestor is down"
          description: "Ingestor service has been down for more than 1 minute. No new events can be ingested."
          runbook: "https://docs.internal/mutt/runbooks/ingestor-down"

      # Alerter Down
      - alert: MUTTAlerterDown
        expr: up{job="mutt-alerter"} == 0
        for: 1m
        labels:
          severity: critical
          service: alerter
          component: mutt
        annotations:
          summary: "MUTT Alerter is down"
          description: "Alerter service has been down for more than 1 minute. Events are queuing but not being processed."
          runbook: "https://docs.internal/mutt/runbooks/alerter-down"

      # Moog Forwarder Down
      - alert: MUTTMoogForwarderDown
        expr: up{job="mutt-moog-forwarder"} == 0
        for: 1m
        labels:
          severity: critical
          service: moog-forwarder
          component: mutt
        annotations:
          summary: "MUTT Moog Forwarder is down"
          description: "Moog Forwarder service has been down for more than 1 minute. Alerts are queuing but not being forwarded to Moogsoft."
          runbook: "https://docs.internal/mutt/runbooks/moog-forwarder-down"

      # Ingest Queue Full
      - alert: MUTTIngestQueueFull
        expr: mutt_ingest_queue_depth > 900000
        for: 2m
        labels:
          severity: critical
          service: ingestor
          component: mutt
        annotations:
          summary: "MUTT Ingest Queue nearly full"
          description: "Ingest queue depth is {{ $value }}, approaching cap of 1,000,000. Backpressure imminent."
          runbook: "https://docs.internal/mutt/runbooks/ingest-queue-full"

      # High Ingest Error Rate
      - alert: MUTTIngestHighErrorRate
        expr: |
          rate(mutt_ingest_requests_total{status="fail"}[5m])
          / rate(mutt_ingest_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
          service: ingestor
          component: mutt
        annotations:
          summary: "MUTT Ingestor high error rate"
          description: "Ingestor error rate is {{ $value | humanizePercentage }} (> 5%) for the last 5 minutes."
          runbook: "https://docs.internal/mutt/runbooks/ingest-high-errors"

      # SLO Breach - Critical
      - alert: MUTTSLOBreachCritical
        expr: |
          (
            sum(rate(mutt_ingest_requests_total{status="success"}[1h]))
            / sum(rate(mutt_ingest_requests_total[1h]))
          ) < 0.99
        for: 10m
        labels:
          severity: critical
          service: ingestor
          component: mutt
          slo: "ingestor-availability"
        annotations:
          summary: "MUTT Ingestor SLO breach (critical)"
          description: "Ingestor availability is {{ $value | humanizePercentage }}, below critical threshold of 99%."
          runbook: "https://docs.internal/mutt/runbooks/slo-breach"

  # High Priority Alerts (P2 - Urgent Response)
  - name: mutt-high-priority-alerts
    interval: 60s
    rules:
      # Ingest Queue Growing Fast
      - alert: MUTTIngestQueueGrowing
        expr: |
          deriv(mutt_ingest_queue_depth[5m]) > 1000
        for: 5m
        labels:
          severity: warning
          service: alerter
          component: mutt
        annotations:
          summary: "MUTT Ingest Queue growing rapidly"
          description: "Ingest queue is growing at {{ $value | humanize }}/sec. Alerter may not be keeping up."
          runbook: "https://docs.internal/mutt/runbooks/queue-growth"

      # DLQ Depth High
      - alert: MUTTMoogDLQDepthHigh
        expr: mutt_moog_dlq_depth > 100
        for: 10m
        labels:
          severity: warning
          service: moog-forwarder
          component: mutt
        annotations:
          summary: "MUTT Moog DLQ depth high"
          description: "Moog DLQ depth is {{ $value }}. Messages are failing to forward to Moogsoft."
          runbook: "https://docs.internal/mutt/runbooks/dlq-high"

      # Circuit Breaker Open
      - alert: MUTTMoogCircuitBreakerOpen
        expr: mutt_moog_circuit_breaker_state{name="moogsoft"} == 1
        for: 2m
        labels:
          severity: warning
          service: moog-forwarder
          component: mutt
        annotations:
          summary: "MUTT Moog circuit breaker open"
          description: "Circuit breaker for Moogsoft is open due to repeated failures. Messages going to DLQ."
          runbook: "https://docs.internal/mutt/runbooks/circuit-breaker"

      # High Processing Latency
      - alert: MUTTAlerterHighLatency
        expr: |
          histogram_quantile(0.95,
            rate(mutt_alerter_processing_latency_seconds_bucket[5m])
          ) > 1.0
        for: 5m
        labels:
          severity: warning
          service: alerter
          component: mutt
        annotations:
          summary: "MUTT Alerter high processing latency"
          description: "Alerter P95 processing latency is {{ $value | humanizeDuration }}, exceeding 1 second."
          runbook: "https://docs.internal/mutt/runbooks/alerter-slow"

      # High Unhandled Event Rate
      - alert: MUTTHighUnhandledRate
        expr: |
          rate(mutt_alerter_events_processed_total{status="unhandled"}[5m])
          / rate(mutt_alerter_events_processed_total[5m]) > 0.10
        for: 10m
        labels:
          severity: warning
          service: alerter
          component: mutt
        annotations:
          summary: "MUTT high unhandled event rate"
          description: "Unhandled event rate is {{ $value | humanizePercentage }} (> 10%). Rules may need updating."
          runbook: "https://docs.internal/mutt/runbooks/high-unhandled"

      # Backpressure Shedding Active
      - alert: MUTTBackpressureSheddingActive
        expr: rate(mutt_alerter_shed_events_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
          service: alerter
          component: mutt
        annotations:
          summary: "MUTT backpressure shedding active"
          description: "Alerter is shedding {{ $value | humanize }} events/sec due to backpressure."
          runbook: "https://docs.internal/mutt/runbooks/backpressure"

      # Redis Connection Issues
      - alert: MUTTRedisHighLatency
        expr: |
          redis_commands_duration_seconds_total{cmd="brpoplpush"}
          / redis_commands_total{cmd="brpoplpush"} > 0.05
        for: 5m
        labels:
          severity: warning
          service: redis
          component: infrastructure
        annotations:
          summary: "MUTT Redis high latency"
          description: "Redis BRPOPLPUSH command latency is {{ $value | humanizeDuration }}, exceeding 50ms."
          runbook: "https://docs.internal/mutt/runbooks/redis-slow"

  # Medium Priority Alerts (P3 - Standard Response)
  - name: mutt-medium-priority-alerts
    interval: 120s
    rules:
      # Cache Reload Failures
      - alert: MUTTAlerterCacheReloadFailures
        expr: rate(mutt_alerter_cache_reload_failures_total[5m]) > 0
        for: 10m
        labels:
          severity: info
          service: alerter
          component: mutt
        annotations:
          summary: "MUTT Alerter cache reload failures"
          description: "Alerter is failing to reload cache from PostgreSQL at {{ $value | humanize }}/sec."
          runbook: "https://docs.internal/mutt/runbooks/cache-reload-fail"

      # High Poison Message Rate
      - alert: MUTTHighPoisonMessageRate
        expr: rate(mutt_remediation_poison_messages_total[5m]) > 0.1
        for: 10m
        labels:
          severity: info
          service: remediation
          component: mutt
        annotations:
          summary: "MUTT high poison message rate"
          description: "Remediation service is detecting {{ $value | humanize }} poison messages/sec."
          runbook: "https://docs.internal/mutt/runbooks/poison-messages"

      # SLO Warning
      - alert: MUTTSLOBurnRateHigh
        expr: |
          (
            (1 - (sum(rate(mutt_ingest_requests_total{status="success"}[1h])) / sum(rate(mutt_ingest_requests_total[1h]))))
            / (1 - 0.995)
          ) > 2
        for: 15m
        labels:
          severity: info
          service: ingestor
          component: mutt
          slo: "ingestor-availability"
        annotations:
          summary: "MUTT Ingestor SLO burn rate high"
          description: "Ingestor error budget is burning at {{ $value | humanize }}× the acceptable rate."
          runbook: "https://docs.internal/mutt/runbooks/slo-burn-rate"
```

Set ownership:
```bash
sudo chown prometheus:prometheus /etc/prometheus/alerts-v25.yml
```

**Reload Prometheus configuration:**
```bash
# Send HUP signal to reload
sudo systemctl kill -s HUP prometheus

# OR use HTTP API (if --web.enable-lifecycle is set)
curl -X POST http://localhost:9090/-/reload

# Verify rules loaded
curl http://localhost:9090/api/v1/rules | jq .
```

---

## Alert Routing and Notifications

### Alertmanager Setup

**Step 1: Install Alertmanager**

```bash
# Download Alertmanager
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz

# Extract
tar -xzf alertmanager-0.26.0.linux-amd64.tar.gz
cd alertmanager-0.26.0.linux-amd64

# Copy binary
sudo cp alertmanager /usr/local/bin/
sudo cp amtool /usr/local/bin/

# Create directories
sudo mkdir -p /etc/alertmanager
sudo mkdir -p /var/lib/alertmanager

# Set ownership
sudo useradd --no-create-home --shell /bin/false alertmanager
sudo chown -R alertmanager:alertmanager /etc/alertmanager
sudo chown -R alertmanager:alertmanager /var/lib/alertmanager
sudo chown alertmanager:alertmanager /usr/local/bin/alertmanager
sudo chown alertmanager:alertmanager /usr/local/bin/amtool
```

---

**Step 2: Configure Alertmanager**

Create `/etc/alertmanager/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m
  smtp_from: 'mutt-alerts@example.com'
  smtp_smarthost: 'smtp.example.com:587'
  smtp_auth_username: 'mutt-alerts@example.com'
  smtp_auth_password: 'SMTP_PASSWORD_HERE'
  smtp_require_tls: true

# Templates (optional)
templates:
  - '/etc/alertmanager/templates/*.tmpl'

# Routing tree
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s        # Wait 10s before sending initial notification
  group_interval: 10s    # Wait 10s before sending updates for same group
  repeat_interval: 12h   # Repeat notifications every 12 hours

  # Child routes (specific handling)
  routes:
    # Critical alerts → PagerDuty + Email + Slack
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true  # Also send to default receiver

    # Warning alerts → Email + Slack
    - match:
        severity: warning
      receiver: 'warning-alerts'

    # Info alerts → Slack only
    - match:
        severity: info
      receiver: 'info-alerts'

# Receivers (notification destinations)
receivers:
  # Default receiver (Email)
  - name: 'default'
    email_configs:
      - to: 'mutt-ops@example.com'
        send_resolved: true
        headers:
          Subject: '[MUTT] {{ .GroupLabels.alertname }} - {{ .GroupLabels.severity }}'

  # Critical alerts
  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: 'PAGERDUTY_SERVICE_KEY_HERE'
        send_resolved: true
        description: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

    email_configs:
      - to: 'mutt-oncall@example.com'
        send_resolved: true
        headers:
          Subject: '[CRITICAL] {{ .GroupLabels.alertname }}'

    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#mutt-critical'
        send_resolved: true
        title: '[CRITICAL] {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        color: 'danger'

  # Warning alerts
  - name: 'warning-alerts'
    email_configs:
      - to: 'mutt-ops@example.com'
        send_resolved: true

    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#mutt-alerts'
        send_resolved: true
        title: '[WARNING] {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        color: 'warning'

  # Info alerts
  - name: 'info-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#mutt-info'
        send_resolved: true
        title: '[INFO] {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        color: 'good'

# Inhibition rules (suppress alerts)
inhibit_rules:
  # Inhibit warning/info if critical is firing for same service
  - source_match:
      severity: 'critical'
    target_match_re:
      severity: 'warning|info'
    equal: ['alertname', 'service']

  # Inhibit downstream alerts if ingestor is down
  - source_match:
      alertname: 'MUTTIngestorDown'
    target_match_re:
      alertname: 'MUTTIngestQueue.*'
    equal: ['cluster']
```

Set ownership:
```bash
sudo chown alertmanager:alertmanager /etc/alertmanager/alertmanager.yml
```

---

**Step 3: Create systemd Service**

Create `/etc/systemd/system/alertmanager.service`:

```ini
[Unit]
Description=Prometheus Alertmanager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=alertmanager
Group=alertmanager
ExecStart=/usr/local/bin/alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/var/lib/alertmanager/ \
  --web.listen-address=:9093 \
  --cluster.listen-address= \
  --web.external-url=http://localhost:9093

Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/alertmanager

[Install]
WantedBy=multi-user.target
```

**Step 4: Start Alertmanager**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable alertmanager
sudo systemctl start alertmanager

# Verify status
sudo systemctl status alertmanager

# Check web UI
curl http://localhost:9093/-/healthy
# Open in browser
http://<alertmanager-server>:9093
```

---

### Testing Alerts

**Manually trigger test alert:**

```bash
# Create test alert JSON
cat > test_alert.json <<EOF
[
  {
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning",
      "service": "test",
      "component": "mutt"
    },
    "annotations": {
      "summary": "This is a test alert",
      "description": "Testing Alertmanager notification routing"
    }
  }
]
EOF

# Send to Alertmanager
curl -X POST http://localhost:9093/api/v1/alerts -d @test_alert.json

# Check Alertmanager UI to verify alert appears
http://localhost:9093
```

---

## Grafana Dashboards

### Installation

```bash
# Add Grafana YUM repository
cat > /etc/yum.repos.d/grafana.repo <<EOF
[grafana]
name=grafana
baseurl=https://packages.grafana.com/oss/rpm
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://packages.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF

# Install Grafana
sudo yum install grafana -y

# Enable and start
sudo systemctl enable grafana-server
sudo systemctl start grafana-server

# Verify
sudo systemctl status grafana-server

# Open web UI (default credentials: admin/admin)
http://<grafana-server>:3000
```

---

### Add Prometheus Data Source

1. Log in to Grafana (http://localhost:3000)
2. Go to **Configuration** → **Data Sources**
3. Click **Add data source**
4. Select **Prometheus**
5. Configure:
   - **URL**: `http://localhost:9090`
   - **Access**: `Server`
6. Click **Save & Test**

---

### MUTT Dashboard JSON

Create dashboard for MUTT overview. Import the following JSON via **Dashboards** → **Import** → **Paste JSON**:

Due to length constraints, here's a condensed dashboard structure. In production, expand each panel:

```json
{
  "dashboard": {
    "title": "MUTT v2.5 - System Overview",
    "panels": [
      {
        "title": "Ingest Success Rate",
        "targets": [{
          "expr": "rate(mutt_ingest_requests_total{status=\"success\"}[5m]) / rate(mutt_ingest_requests_total[5m])"
        }]
      },
      {
        "title": "Ingest Queue Depth",
        "targets": [{
          "expr": "mutt_ingest_queue_depth"
        }]
      },
      {
        "title": "Alerter Processing Rate",
        "targets": [{
          "expr": "rate(mutt_alerter_events_processed_total[5m])"
        }]
      },
      {
        "title": "Moog DLQ Depth",
        "targets": [{
          "expr": "mutt_moog_dlq_depth"
        }]
      }
    ]
  }
}
```

**Recommended Dashboards:**
1. **System Overview**: High-level health metrics
2. **Ingestor Details**: Request rate, latency, errors
3. **Alerter Details**: Processing rate, queue depth, cache stats
4. **Moog Forwarder Details**: Success rate, DLQ, circuit breaker
5. **Infrastructure**: Redis/PostgreSQL metrics
6. **SLO Dashboard**: SLO compliance, error budgets

---

## SLO Monitoring

MUTT exposes an SLO API endpoint for tracking Service Level Objectives.

### SLO Endpoint

**URL**: `GET /api/v1/slo`

**Authentication**: Requires `X-API-Key` header or `api_key` query parameter

**Response Example:**

```json
{
  "window_hours": 24,
  "components": {
    "ingestor": {
      "target": 0.995,
      "availability": 0.9978,
      "error_budget_remaining": 0.56,
      "burn_rate": 0.44,
      "state": "ok",
      "window_hours": 24
    },
    "forwarder": {
      "target": 0.99,
      "availability": 0.9932,
      "error_budget_remaining": 0.68,
      "burn_rate": 0.68,
      "state": "ok",
      "window_hours": 24
    }
  }
}
```

---

### SLO Definitions

| Component | Target | Description |
|-----------|--------|-------------|
| Ingestor | 99.5% | Percentage of successful ingest requests |
| Forwarder | 99% | Percentage of successful forwards to Moogsoft |

**Error Budget:**

```
Error Budget = 1 - Target
Ingestor Error Budget = 1 - 0.995 = 0.5% (30 minutes/month)
Forwarder Error Budget = 1 - 0.99 = 1% (60 minutes/month)
```

**Burn Rate:**

```
Burn Rate = (1 - Actual Availability) / (1 - Target)

Example:
- Target: 99.5% (0.995)
- Actual: 99.3% (0.993)
- Burn Rate = (1 - 0.993) / (1 - 0.995) = 0.007 / 0.005 = 1.4×

Burn Rate > 1 means error budget is being consumed faster than expected
```

**States:**

- **ok**: Burn rate ≤ 1 (within error budget)
- **warn**: Burn rate > 1 and ≤ 2 (consuming error budget faster than planned)
- **critical**: Burn rate > 2 (rapidly exhausting error budget)

---

### Monitoring SLOs

**Prometheus Queries:**

```promql
# Ingestor Availability (24h)
sum(rate(mutt_ingest_requests_total{status="success"}[24h]))
/ sum(rate(mutt_ingest_requests_total[24h]))

# Forwarder Availability (24h)
sum(rate(mutt_moog_requests_total{status="success"}[24h]))
/ sum(rate(mutt_moog_requests_total[24h]))

# Ingestor Error Budget Remaining
1 - (
  (1 - (sum(rate(mutt_ingest_requests_total{status="success"}[24h])) / sum(rate(mutt_ingest_requests_total[24h]))))
  / (1 - 0.995)
)

# Ingestor Burn Rate
(1 - (sum(rate(mutt_ingest_requests_total{status="success"}[1h])) / sum(rate(mutt_ingest_requests_total[1h]))))
/ (1 - 0.995)
```

---

## Health Check Monitoring

All MUTT services expose `/health` endpoints for health checking.

### Health Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Ingestor | `http://localhost:8080/health` | `200 OK` + JSON |
| Alerter | `http://localhost:8081/health` | `200 OK` + JSON |
| Moog Forwarder | `http://localhost:8082/health` | `200 OK` + JSON |
| Remediation | `http://localhost:8087/health` | `200 OK` + JSON |
| Web UI | `http://localhost:8090/health` | `200 OK` + JSON |

---

### Prometheus Health Check Scraping

Prometheus automatically checks `up` status for each scrape target. Configure additional health check scraping:

Add to `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  # MUTT Health Checks (using blackbox_exporter)
  - job_name: 'mutt-health-checks'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - http://localhost:8080/health  # Ingestor
          - http://localhost:8081/health  # Alerter
          - http://localhost:8082/health  # Moog Forwarder
          - http://localhost:8087/health  # Remediation
          - http://localhost:8090/health  # Web UI
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9115  # blackbox_exporter address
```

**Install blackbox_exporter (optional but recommended):**

```bash
# Download
cd /tmp
wget https://github.com/prometheus/blackbox_exporter/releases/download/v0.24.0/blackbox_exporter-0.24.0.linux-amd64.tar.gz

# Extract and install
tar -xzf blackbox_exporter-0.24.0.linux-amd64.tar.gz
sudo cp blackbox_exporter-0.24.0.linux-amd64/blackbox_exporter /usr/local/bin/

# Create config
sudo mkdir /etc/blackbox_exporter
cat > /etc/blackbox_exporter/blackbox.yml <<EOF
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_status_codes: [200]
      method: GET
      preferred_ip_protocol: ip4
EOF

# Create systemd service (similar to prometheus.service)
# Start service
sudo systemctl start blackbox_exporter
```

---

## Log Monitoring

### Centralized Logging

For log-based alerting, integrate with centralized logging systems:

**Option 1: Elasticsearch + Logstash + Kibana (ELK)**

Configure Filebeat to ship MUTT logs:

```yaml
# /etc/filebeat/filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/mutt/*.log
    json.keys_under_root: true
    json.add_error_key: true
    fields:
      service: mutt
      environment: production

output.logstash:
  hosts: ["logstash.internal:5044"]
```

**Option 2: Splunk**

Configure rsyslog to forward logs:

```bash
# /etc/rsyslog.d/mutt.conf
$ModLoad imfile
$InputFileName /var/log/mutt/ingestor.log
$InputFileTag mutt-ingestor:
$InputFileStateFile stat-mutt-ingestor
$InputRunFileMonitor

*.* @@splunk.internal:514
```

---

### Log-Based Alerts

Create alerts based on log patterns (in ELK/Splunk):

**Examples:**
- **High error rate**: > 10 errors/minute in logs
- **Critical errors**: Any `CRITICAL` level logs
- **Vault auth failures**: Any "Vault authentication failed" messages
- **Database connection failures**: Any "PostgreSQL connection refused" messages

---

## Troubleshooting Monitoring Issues

### Issue: Prometheus Not Scraping Metrics

**Symptoms:**
- `up` metric shows 0 for MUTT services
- No metrics appearing in Prometheus

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq .

# Check service is listening on metrics port
sudo ss -tunlp | grep 9090

# Test metrics endpoint directly
curl http://localhost:9090/metrics
```

**Resolution:**
```bash
# Ensure service is running
sudo systemctl status mutt-ingestor

# Check firewall
sudo firewall-cmd --list-ports | grep 9090

# Add firewall rule if needed
sudo firewall-cmd --zone=public --add-port=9090/tcp --permanent
sudo firewall-cmd --reload

# Restart Prometheus
sudo systemctl restart prometheus
```

---

### Issue: Alerts Not Firing

**Symptoms:**
- Expected alerts not appearing in Alertmanager
- Prometheus shows alerts but Alertmanager doesn't

**Diagnosis:**
```bash
# Check Prometheus alerts
curl http://localhost:9090/api/v1/alerts | jq .

# Check Alertmanager connectivity
curl http://localhost:9093/api/v1/status

# Check Prometheus alertmanager config
curl http://localhost:9090/api/v1/alertmanagers | jq .
```

**Resolution:**
```bash
# Verify Alertmanager is running
sudo systemctl status alertmanager

# Check Prometheus can reach Alertmanager
telnet localhost 9093

# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload

# Check Prometheus logs
sudo journalctl -u prometheus -n 100 | grep -i alert
```

---

### Issue: Notifications Not Sending

**Symptoms:**
- Alerts appear in Alertmanager but no emails/Slack messages

**Diagnosis:**
```bash
# Check Alertmanager logs
sudo journalctl -u alertmanager -n 100

# Check Alertmanager config
amtool config show

# Test SMTP connectivity
telnet smtp.example.com 587
```

**Resolution:**
```bash
# Verify SMTP credentials
sudo vi /etc/alertmanager/alertmanager.yml
# Update smtp_auth_password

# Test Slack webhook
curl -X POST https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK \
  -d '{"text":"Test message from Alertmanager"}'

# Reload Alertmanager
sudo systemctl restart alertmanager
```

---

## Summary

### Monitoring Checklist

**Initial Setup:**
- [ ] Install Prometheus, Alertmanager, Grafana
- [ ] Configure Prometheus scrape configs for all MUTT services
- [ ] Load recording rules and alerting rules
- [ ] Configure Alertmanager notification channels
- [ ] Create Grafana dashboards
- [ ] Set up health check monitoring
- [ ] Configure centralized logging

**Ongoing Operations:**
- [ ] Monitor SLO compliance daily
- [ ] Review alerting rules monthly
- [ ] Update dashboards as needed
- [ ] Test alert routing quarterly
- [ ] Review and prune old metrics (retention policy)
- [ ] Validate monitoring during deployments

**Incident Response:**
- [ ] Check Alertmanager for active alerts
- [ ] Review Grafana dashboards for anomalies
- [ ] Query Prometheus for detailed metrics
- [ ] Check SLO API for error budget status
- [ ] Correlate alerts with log events

---

## Next Steps

For additional operational guidance:

1. **Service Operations**: [SERVICE_OPERATIONS.md](SERVICE_OPERATIONS.md) - Service management, scaling
2. **Troubleshooting**: [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Problem diagnosis
3. **Configuration Management**: [CONFIG_MANAGEMENT.md](CONFIG_MANAGEMENT.md) - Config, secrets management
4. **Backup & Recovery**: [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) (coming soon) - Disaster recovery
5. **Incident Response**: [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) (coming soon) - Incident procedures

---

**Document Metadata:**
- **Version**: 1.0
- **Last Updated**: 2025-11-10
- **Maintainer**: MUTT Operations Team
- **Feedback**: Report issues via internal ticketing system
