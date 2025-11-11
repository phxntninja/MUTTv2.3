# MUTT v2.3 Quick Start Guide

Get MUTT up and running in Docker in under 10 minutes.

---

## Prerequisites

- Docker 20.10+ installed
- Docker Compose 1.29+ installed
- 4GB RAM minimum
- Ports 8080-8090, 6379, 5432, 8200, 9090, 3000 available

---

## 3-Step Quick Start

### Step 1: Start All Services

```bash
# Clone repository
git clone https://github.com/yourusername/mutt.git
cd mutt

# Start all services
docker-compose up -d

# Watch logs
docker-compose logs -f
```

**Services started:**
- ✅ Redis (port 6379)
- ✅ PostgreSQL (port 5432)
- ✅ Vault (port 8200)
- ✅ MUTT Ingestor (port 8080)
- ✅ MUTT Alerter (port 8081)
- ✅ MUTT Moog Forwarder (ports 8083/8084)
- ✅ MUTT Web UI (port 8090)
- ✅ Mock Moog (port 8888)
- ✅ Prometheus (port 9090)
- ✅ Grafana (port 3000)

### Step 2: Verify Health

```bash
# Check all services are healthy
docker-compose ps

# Test Ingestor health endpoint
curl http://localhost:8080/health

# Expected output:
# {"status": "healthy", "timestamp": "..."}
```

### Step 3: Send Test Message

```bash
# Send a test syslog message
curl -X POST http://localhost:8080/api/v2/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: test-api-key-123" \
  -d '{
    "timestamp": "2025-11-08T12:00:00Z",
    "message": "CRITICAL: Test alert from quickstart",
    "hostname": "test-server-01",
    "program": "test",
    "syslog_severity": 2,
    "source_ip": "192.168.1.100",
    "mutt_type": "syslog"
  }'

# Expected output:
# {"status": "accepted", "correlation_id": "...", "queue_depth": 1}
```

---

## Access Services

| Service | URL | Credentials |
|---|---|---|
| **Web UI** | http://localhost:8090 | API Key: `test-api-key-123` |
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Vault** | http://localhost:8200 | Token: `root-token-for-dev` |

---

## View Your Test Message

### 1. Check Queue Depths (Web UI)

```bash
open http://localhost:8090
```

You should see:
- Ingest queue depth: 0 (message processed)
- Alert queue depth: 0 (forwarded to Moog)

### 2. Check Audit Log (Database)

```bash
docker exec -it mutt-postgres psql -U mutt_user -d mutt \
  -c "SELECT event_timestamp, hostname, message FROM event_audit_log ORDER BY event_timestamp DESC LIMIT 5;"
```

### 3. Check Mock Moog Logs

```bash
docker logs mutt-mock-moog

# You should see:
# Received alert: {...}
```

---

## View Metrics

### Prometheus

```bash
open http://localhost:9090

# Example queries:
# - mutt_ingest_requests_total
# - mutt_ingest_queue_depth
# - mutt_alerter_messages_processed_total
# - mutt_moog_forward_total
```

### Grafana

```bash
open http://localhost:3000
# Login: admin / admin

# Add dashboard:
# 1. Click "+" → Import
# 2. Use Prometheus datasource
# 3. Create visualizations for MUTT metrics
```

---

## Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ingestor
docker-compose logs -f alerter
docker-compose logs -f moog-forwarder
docker-compose logs -f webui
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart ingestor
docker-compose restart alerter
```

### Scale Services

```bash
# Scale alerter to 3 instances
docker-compose up -d --scale alerter=3

# Scale moog-forwarder to 2 instances
docker-compose up -d --scale moog-forwarder=2
```

### Stop Services

```bash
# Stop all (keeps data)
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Stop and remove ALL data (⚠️ destructive)
docker-compose down -v
```

---

## Test Suite

### Run Unit Tests

```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=services --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Test Results

You should see:
- ✅ 30+ Ingestor tests passing
- ✅ 40+ Alerter tests passing
- ✅ 35+ Moog Forwarder tests passing
- ✅ 30+ Web UI tests passing

**Total: 135+ tests**

---

## Simulate Production Traffic

### 1. Create Alert Rules

```bash
# Add a rule via Web UI API
curl -X POST http://localhost:8090/api/v1/rules \
  -H "X-API-KEY: test-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "match_string": "CRITICAL",
    "match_type": "contains",
    "priority": 10,
    "prod_handling": "Page_and_ticket",
    "dev_handling": "Ticket_only",
    "team_assignment": "NETO",
    "is_active": true
  }'
```

### 2. Send Multiple Messages

```bash
# Send 100 test messages
for i in {1..100}; do
  curl -s -X POST http://localhost:8080/ingest \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: test-api-key-123" \
    -d "{
      \"timestamp\": \"$(date -Iseconds)\",
      \"message\": \"Test message $i\",
      \"hostname\": \"test-server-01\",
      \"program\": \"test\",
      \"syslog_severity\": 4,
      \"source_ip\": \"192.168.1.100\",
      \"mutt_type\": \"syslog\"
    }"
done
```

### 3. Monitor Processing

```bash
# Watch queue depths
watch -n 1 'curl -s http://localhost:8090/api/v1/metrics | jq ".queue_depths"'

# Watch Prometheus metrics
open http://localhost:9090/graph
# Query: rate(mutt_ingest_requests_total[1m])
```

---

## Troubleshooting

### Issue: Services won't start

```bash
# Check logs
docker-compose logs

# Common issues:
# - Ports already in use (check with: netstat -an | grep LISTEN)
# - Insufficient memory (Docker needs 4GB+)
# - Missing .env file (not required for quick start)
```

### Issue: Database connection errors

```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# Check database initialized
docker exec -it mutt-postgres psql -U mutt_user -d mutt -c "\dt"

# You should see: alert_rules, development_hosts, device_teams, event_audit_log
```

### Issue: Redis connection errors

```bash
# Check Redis is healthy
docker-compose ps redis

# Test Redis connection
docker exec -it mutt-redis redis-cli ping
# Expected: PONG
```

### Issue: Messages not being processed

```bash
# Check Alerter is running
docker-compose logs alerter | tail -20

# Check processing list (should be empty when idle)
docker exec -it mutt-redis redis-cli LLEN mutt:processing:alerter:alerter-001

# Check for errors in Alerter logs
docker-compose logs alerter | grep ERROR
```

---

## Next Steps

### 1. Production Deployment

See [README.md](README.md) for RHEL deployment instructions using:
- `scripts/deploy_mutt_v2.3.sh` - Automated RHEL deployment
- `configs/rsyslog/` - rsyslog and snmptrapd configuration
- `configs/prometheus/` - Monitoring and alerting rules

### 2. Configure Real Moog Integration

```bash
# Update docker-compose.yml or .env
MOOG_WEBHOOK_URL=https://your-moog-instance.com/webhook
MOOG_API_KEY=your-moog-api-key

# Restart moog-forwarder
docker-compose restart moog-forwarder
```

### 3. Set Up Real Vault

```bash
# Run vault initialization script
./scripts/vault-init.sh

# Update services to use production Vault
# See README.md for details
```

### 4. Configure Partitioning

```bash
# Set up monthly partition creation cron job
# See scripts/partition_manager.sh
```

### 5. Production Secrets

Replace dev secrets in docker-compose.yml with production values:
- API keys
- Database passwords
- Moog credentials

**⚠️ Never commit production secrets to git!**

---

## Clean Up

```bash
# Stop all services and remove data
docker-compose down -v

# Remove Docker images
docker-compose down --rmi all
```

---

## Support

- 📖 Full documentation: [README.md](README.md)
- 🧪 Test documentation: [tests/README_TESTS.md](tests/README_TESTS.md)
- 📋 Handoff document: [HANDOFF.md](HANDOFF.md)
- 🐛 Report issues: GitHub Issues

---

**🎉 You're now running MUTT v2.3!**

For production deployment and advanced configuration, see [README.md](README.md).
