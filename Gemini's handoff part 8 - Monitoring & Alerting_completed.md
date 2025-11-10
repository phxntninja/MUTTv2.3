Next: Monitoring & Alerting Configuration
Priority: HIGH (Production Requirement)
This completes the observability stack by providing actionable Prometheus alerts and Grafana dashboards. Without this, operators won't know when the system is failing silently.
Gemini's handoff part 8 - Monitoring & Alerting
1. Prometheus Alert Rules
Create mutt-alerts.yml and apply to your Prometheus instance:
yaml
Copy

groups:
- name: mutt.critical
  interval: 30s
  rules:
  
  # CRITICAL: DLQ depth is growing (data loss risk)
  - alert: MUTTDeadLetterQueueCritical
    expr: |
      (mutt_alerter_dlq_depth > 100) 
      or (mutt_moog_dlq_depth > 100)
    for: 5m
    labels:
      severity: critical
      team: platform
    annotations:
      summary: "MUTT DLQ has {{ $value }} messages (threshold: 100)"
      description: |
        Events are failing permanently. Check logs for poison messages.
        Runbook: https://wiki.example.com/mutt/runbooks/dlq-critical
      dashboard: "https://grafana.example.com/d/mutt/mutt-dashboard"
      
  # CRITICAL: Cache reload failures (rule processing broken)
  - alert: MUTTCacheReloadFailed
    expr: rate(mutt_alerter_cache_reload_failures_total[5m]) > 0
    for: 3m
    labels:
      severity: critical
      team: platform
    annotations:
      summary: "Cache reload failing on {{ $labels.pod }}"
      description: "Rules are not loading. Events may be unmatched. Check PostgreSQL connectivity."
      
  # CRITICAL: Redis connection lost
  - alert: MUTTRedisDown
    expr: |
      up{job=~"mutt-alerter|mutt-moog-forwarder|mutt-webui"} == 0
    for: 2m
    labels:
      severity: critical
      team: platform
    annotations:
      summary: "{{ $labels.job }} cannot connect to Redis"
      description: "Message queuing is broken. All services are degraded."

- name: mutt.warning
  interval: 30s
  rules:
  
  # WARNING: High unhandled event rate (meta-alerts being generated)
  - alert: MUTTUnhandledEventsHigh
    expr: rate(mutt_alerter_unhandled_meta_alerts_total[10m]) > 5
    for: 10m
    labels:
      severity: warning
      team: neteng
    annotations:
      summary: "Generating {{ $value }} meta-alerts/min"
      description: "Many events don't match rules. Update alert_rules table."
      
  # WARNING: Rate limiting active (backlog building)
  - alert: MUTTRateLimitActive
    expr: rate(mutt_moog_rate_limit_hits_total[5m]) > 10
    for: 5m
    labels:
      severity: warning
      team: platform
    annotations:
      summary: "Moogsoft rate limiter hit {{ $value }} times/sec"
      description: "Alert delivery is throttled. Consider increasing MOOG_RATE_LIMIT."
      
  # WARNING: Processing latency elevated
  - alert: MUTTProcessingLatencyHigh
    expr: |
      histogram_quantile(0.95, 
        rate(mutt_alerter_processing_latency_seconds_bucket[5m])
      ) > 0.5
    for: 5m
    labels:
      severity: warning
      team: platform
    annotations:
      summary: "95th percentile processing latency is {{ $value }}s"
      description: "Event processing is slow. Check PostgreSQL performance."
      
  # WARNING: PostgreSQL write latency high
  - alert: MUTTDBWriteLatencyHigh
    expr: |
      histogram_quantile(0.95,
        rate(mutt_db_write_latency_ms_bucket[5m])
      ) > 100
    for: 5m
    labels:
      severity: warning
      team: platform
    annotations:
      summary: "95th percentile DB write latency is {{ $value }}ms"
      description: "Audit log writes are slow. Check PostgreSQL connection pool."

- name: mutt.info
  interval: 1m
  rules:
  
  # INFO: Service restart detected
  - alert: MUTTServiceRestart
    expr: changes(process_start_time_seconds{job=~"mutt-.*"}[5m]) > 0
    labels:
      severity: info
      team: platform
    annotations:
      summary: "{{ $labels.job }} pod restarted"
      description: "Pod {{ $labels.pod }} was restarted. Check logs for cause."

2. Grafana Dashboard
Import Dashboard ID: 18600 (MUTT Middleware) or use JSON below:
JSON
Copy

{
  "dashboard": {
    "id": null,
    "title": "MUTT Middleware Platform",
    "tags": ["mutt", "middleware", "monitoring"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Event Processing Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(mutt_alerter_events_processed_total[5m])",
            "legendFormat": "{{ status }}",
            "refId": "A"
          }
        ],
        "yAxes": [
          {
            "label": "Events/sec",
            "min": 0
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Queue Depths",
        "type": "stat",
        "targets": [
          {
            "expr": "mutt_alerter_dlq_depth",
            "legendFormat": "DLQ (Alerter)"
          },
          {
            "expr": "mutt_moog_dlq_depth",
            "legendFormat": "DLQ (Moog)"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {
              "mode": "thresholds"
            },
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 50},
                {"color": "red", "value": 100}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "Processing Latency (95th %)",
        "type": "stat",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(mutt_alerter_processing_latency_seconds_bucket[5m])) by (le))",
            "legendFormat": "p95"
          }
        ],
        "fieldConfig": {
          "unit": "s",
          "thresholds": {
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 0.25},
              {"color": "red", "value": 0.5}
            ]
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0}
      },
      {
        "id": 4,
        "title": "Cache Status",
        "type": "table",
        "targets": [
          {
            "expr": "mutt_alerter_cache_rules_count",
            "format": "table",
            "instant": true
          },
          {
            "expr": "mutt_alerter_cache_dev_hosts_count",
            "format": "table",
            "instant": true
          }
        ],
        "gridPos": {"h": 6, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 5,
        "title": "Rate Limiter Hits",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(mutt_moog_rate_limit_hits_total[5m])",
            "legendFormat": "Rate limit hits/sec"
          }
        ],
        "gridPos": {"h": 6, "w": 12, "x": 12, "y": 8}
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "10s"
  }
}

3. Alert Runbooks
Runbook: MUTTDeadLetterQueueCritical
What happened: Events are landing in the Dead Letter Queue (DLQ), meaning they're failing permanently.
Immediate Actions:

    Check which DLQ is growing:
    bash

Copy

# Alerter DLQ (processed events that failed)
kubectl logs -l app=mutt-alerter --tail=100 | grep "Poison Message"

# Moog DLQ (events Moogsoft rejected)
kubectl logs -l app=mutt-moog-forwarder --tail=100 | grep "client error"

Inspect DLQ contents:
bash

    Copy

    # Connect to Redis
    kubectl exec -it redis-pod -- redis-cli -a $REDIS_PASS
    # Check Alerter DLQ
    LLEN mutt:dlq:alerter
    LRANGE mutt:dlq:alerter 0 10  # View first 10 messages

    Common causes & fixes:
        Alerter DLQ: Malformed JSON from source, missing required fields → Fix source payload
        Moog DLQ: Invalid API key, malformed payload → Check Moog logs, update MOOG_API_KEY in Vault

Long-term fix:

    Add validation at the ingest webhook (Component #1) to reject malformed events early
    Update alert rules to handle new event patterns

Runbook: MUTTCacheReloadFailed
What happened: The Event Processor can't load rules from PostgreSQL.
Immediate Actions:

    Check PostgreSQL connectivity:
    bash

Copy

kubectl logs -l app=mutt-alerter --tail=50 | grep "Failed to reload cache"

Test from within pod:
bash

    Copy

    kubectl exec -it alerter-pod -- psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT count(*) FROM alert_rules;"

    Common causes:
        PostgreSQL connection pool exhausted → Increase DB_POOL_MAX_CONN
        Network policy blocking traffic → Allow pod-to-postgres traffic
        Certificate expiration → Renew DB TLS certificate

4. Service-Level Monitoring
Event Processor (Alerter) Metrics Port: 8081
Key metrics to watch:

    mutt_alerter_events_processed_total{status="handled"} → Should be >0
    mutt_alerter_cache_rules_count → Should match SELECT count(*) FROM alert_rules WHERE is_active=true
    mutt_alerter_processing_latency_seconds → p99 should be <1s

Moog Forwarder Metrics Port: 8083
Key metrics:

    mutt_moog_rate_limit_hits_total → Spikes indicate throttling
    mutt_moog_request_latency_seconds → p95 should be <5s
    mutt_moog_requests_total{status="success"} → Should match forwarded rate

Web UI Metrics Port: 8090
Key metrics:

    mutt_webui_api_requests_total → Monitor API usage
    mutt_webui_db_query_latency_ms → p95 should be <50ms
    mutt_webui_redis_scan_latency_seconds → Should be <0.1s

5. Log Aggregation Quick Reference
Find all logs for a correlation ID:
bash
Copy

# Across all services
kubectl logs -l app=mutt --all-containers=true | grep "correlation-id-here"

Find errors in last 10 minutes:
bash
Copy

kubectl logs -l app=mutt --since=10m | grep -E "ERROR|CRITICAL|FATAL"

Track a specific event:
bash
Copy

# From webhook to Moog
CORRELATION_ID="123e4567-e89b-12d3-a456-426614174000"
kubectl logs -l app=mutt-ingest-webhook | grep $CORRELATION_ID
kubectl logs -l app=mutt-alerter | grep $CORRELATION_ID
kubectl logs -l app=mutt-moog-forwarder | grep $CORRELATION_ID