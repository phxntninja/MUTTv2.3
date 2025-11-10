# MUTT v2.5 - Operator Validation Guide

**Priority 3: Operational Tooling Validation**

This guide validates the new operational tooling (dynamic configuration and log streaming) in a staging environment.

---

## Prerequisites

- Docker and docker-compose installed
- Python 3.10+ with project dependencies
- Access to staging environment or local docker-compose setup

**Important:** Dynamic configuration must be enabled for services to pick up config changes. Services require the environment variable `DYNAMIC_CONFIG_ENABLED=true` to enable this feature.

For local testing, create a `docker-compose.override.yml` file:

```yaml
version: '3.8'
services:
  alerter:
    environment:
      DYNAMIC_CONFIG_ENABLED: "true"

  ingestor:
    environment:
      DYNAMIC_CONFIG_ENABLED: "true"

  webui:
    environment:
      DYNAMIC_CONFIG_ENABLED: "true"

  moog-forwarder:
    environment:
      DYNAMIC_CONFIG_ENABLED: "true"
```

This override file will be automatically applied when running `docker-compose up`.

---

## Validation Test 1: Dynamic Configuration Reload

**Objective:** Verify that services pick up configuration changes without restart.

### Setup

1. Start the services:
```bash
docker-compose up -d redis alerter webui
```

2. Wait for services to be healthy:
```bash
docker-compose ps
# All services should show "healthy" status
```

3. Verify Redis connectivity:
```bash
python scripts/muttdev.py config --list
```

### Test Steps

#### Step 1: Set Baseline Configuration

```bash
# Set initial value for alerter queue warn threshold
python scripts/muttdev.py config --set alerter_queue_warn_threshold 1000 --publish
```

Expected output:
```
Set alerter_queue_warn_threshold=1000 (published)
```

#### Step 2: Verify Current Configuration

```bash
# Get the current value
python scripts/muttdev.py config --get alerter_queue_warn_threshold
```

Expected output:
```
1000
```

#### Step 3: Live Configuration Update (No Restart)

```bash
# Update the value while services are running
python scripts/muttdev.py config --set alerter_queue_warn_threshold 2000 --publish
```

Expected output:
```
Set alerter_queue_warn_threshold=2000 (published)
```

#### Step 4: Verify Service Picked Up Change

Check the alerter logs to confirm it received the config update:

```bash
docker-compose logs --tail 50 alerter | grep -i "config\|threshold"
```

Expected indicators:
- Service should show "config update" or similar message
- No restart timestamp (service uptime unchanged)
- New threshold value logged

**Alternative verification:**
```bash
# Check service metrics endpoint
curl http://localhost:8081/health
# Service should still be healthy with no recent restart
```

#### Step 5: Verify Configuration Persistence

```bash
# Confirm the new value persists in Redis
python scripts/muttdev.py config --get alerter_queue_warn_threshold
```

Expected output:
```
2000
```

### Success Criteria

- ✅ Configuration value changes without service restart
- ✅ Service logs show config update received
- ✅ New configuration is active immediately
- ✅ No error messages or connection issues
- ✅ Service health check remains passing

---

## Validation Test 2: Log Streaming

**Objective:** Verify real-time log following functionality.

### Setup

Ensure services are running from Test 1, or start them:
```bash
docker-compose up -d redis alerter webui ingestor
```

### Test Steps

#### Step 1: Follow Alerter Logs

In a terminal window, start following logs:
```bash
python scripts/muttdev.py logs --service alerter --follow --tail 200
```

Expected behavior:
- Command should execute `docker-compose logs -f --tail=200 alerter`
- Log output should stream continuously
- Press Ctrl+C to stop

#### Step 2: Follow Ingestor Logs

In another terminal window:
```bash
python scripts/muttdev.py logs --service ingestor --follow
```

Expected behavior:
- Real-time log streaming from ingestor service
- New log entries appear as events occur

#### Step 3: Trigger Log Activity

Generate some activity to verify logs are streaming:

```bash
# Send a test event to the ingestor
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{"test": "validation", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'
```

Verify:
- Ingestor logs show the received event
- Alerter logs show processing activity
- Logs appear in real-time (within 1-2 seconds)

#### Step 4: Follow WebUI Logs

```bash
python scripts/muttdev.py logs --service webui --follow --tail 100
```

Then access the WebUI:
```bash
curl http://localhost:8090/health
```

Verify:
- Access logs appear immediately
- Health check requests are logged
- Log streaming continues until interrupted

### Success Criteria

- ✅ `muttdev logs --follow` successfully streams logs
- ✅ Logs appear in real-time (< 2 second delay)
- ✅ Can follow multiple services simultaneously
- ✅ Log output is readable and properly formatted
- ✅ Ctrl+C cleanly exits log following

---

## Validation Test 3: Combined Operations Test

**Objective:** Validate dynamic config changes while monitoring logs.

### Test Steps

#### Step 1: Start Log Monitoring

In terminal 1:
```bash
python scripts/muttdev.py logs --service alerter --follow
```

#### Step 2: Make Configuration Changes

In terminal 2:
```bash
# Change alerter shed mode
python scripts/muttdev.py config --set alerter_shed_mode dlq --publish

# Wait 2 seconds
sleep 2

# Change queue threshold
python scripts/muttdev.py config --set alerter_queue_shed_threshold 3000 --publish
```

#### Step 3: Observe Real-Time Updates

In terminal 1 (logs), you should see:
- Config update messages for both changes
- No service restart
- Confirmation of new values being applied
- Service continues processing normally

#### Step 4: List All Configuration

```bash
python scripts/muttdev.py config --list
```

Expected output (sample):
```
alerter_queue_warn_threshold=2000
alerter_queue_shed_threshold=3000
alerter_shed_mode=dlq
...
```

### Success Criteria

- ✅ Configuration changes visible in real-time logs
- ✅ Multiple config updates handled correctly
- ✅ Service operates normally throughout changes
- ✅ All changes persisted and queryable

---

## Troubleshooting

### Issue: "redis package not installed"

**Solution:**
```bash
pip install redis
# or
pip install -r requirements.txt
```

### Issue: "Failed to initialize Redis client"

**Solution:**
1. Check Redis is running: `docker-compose ps redis`
2. Check Redis connectivity: `docker-compose exec redis redis-cli PING`
3. Verify `.env` has correct `REDIS_HOST` and `REDIS_PORT`

### Issue: Config changes not visible in service

**Solution:**
1. Check service has `DYNAMIC_CONFIG_ENABLED=true` in environment
2. Verify Redis PubSub is working:
   ```bash
   # Terminal 1
   docker-compose exec redis redis-cli SUBSCRIBE mutt:config:updates

   # Terminal 2
   python scripts/muttdev.py config --set test_key test_value --publish
   ```
3. Check service logs for errors
4. Restart service if needed: `docker-compose restart alerter`

### Issue: Logs not streaming

**Solution:**
1. Verify docker-compose is installed: `docker-compose --version`
2. Check service is running: `docker-compose ps`
3. Try manual command:
   ```bash
   docker-compose logs -f alerter
   ```

### Issue: "docker-compose.yml not found"

**Solution:**
Ensure you're running commands from the repository root directory.

---

## Validation Checklist

Use this checklist when performing operator validation:

### Dynamic Configuration
- [ ] Can list all config keys
- [ ] Can get individual config values
- [ ] Can set config values
- [ ] Config changes publish to services
- [ ] Services receive updates without restart
- [ ] Config persists in Redis
- [ ] Multiple services can be updated simultaneously

### Log Streaming
- [ ] Can follow logs for each service (ingestor, alerter, forwarder, webui, remediation)
- [ ] Logs stream in real-time
- [ ] Can specify tail count
- [ ] Can interrupt log following cleanly (Ctrl+C)
- [ ] Log format is readable and structured

### Integration
- [ ] Can monitor logs while making config changes
- [ ] Config updates visible in service logs
- [ ] No service disruption during config changes
- [ ] Health checks pass throughout validation
- [ ] All commands work from repo root directory

---

## Next Steps

After successful validation:

1. **Document Results:** Record validation timestamp, environment details, and any issues
2. **Update Runbooks:** Update operational runbooks with validated procedures
3. **Train Operators:** Conduct training session on new tooling
4. **Production Rollout:** Plan phased rollout to production environment

---

## Notes

- **Testing in Production:** Use conservative values and schedule during low-traffic windows
- **Rollback Plan:** Keep previous config values documented for quick rollback
- **Monitoring:** Watch service metrics and error rates during and after config changes
- **Audit Trail:** All config changes should be logged in audit systems

---

## Reference

- Dynamic Config Usage: [docs/DYNAMIC_CONFIG_USAGE.md](DYNAMIC_CONFIG_USAGE.md)
- Dynamic Config Cheatsheet: [docs/DYNAMIC_CONFIG_CHEATSHEET.md](DYNAMIC_CONFIG_CHEATSHEET.md)
- Developer Quickstart: [docs/DEV_QUICKSTART.md](DEV_QUICKSTART.md)
