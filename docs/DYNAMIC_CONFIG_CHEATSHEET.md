# MUTT v2.5 – Dynamic Config Cheat‑Sheet

Purpose
- Quick operator/dev reference for Redis‑backed dynamic config keys and commands.

Redis Namespace
- Key prefix: `mutt:config:*`
- Pub/Sub channel for cache invalidation: `mutt:config:updates`

Core Commands (redis-cli)
- Get a key: `redis-cli GET mutt:config:<key>`
- Set a key: `redis-cli SET mutt:config:<key> <value>`
- Publish change (notify services): `redis-cli PUBLISH mutt:config:updates <key>`

Common Keys
- Alerter backpressure
  - `alerter_queue_warn_threshold` (int)
  - `alerter_queue_shed_threshold` (int)
  - `alerter_shed_mode` (`dlq|defer`)
  - `alerter_defer_sleep_ms` (int)
- Remediation
  - `remediation_enabled` (bool)
  - `remediation_interval` (seconds)
  - `remediation_batch_size` (int)
  - `max_poison_retries` (int)
- SLOs
  - `slo_ingest_success_target` (float 0..1)
  - `slo_forward_success_target` (float 0..1)
  - `slo_window_hours` (int)
  - `slo_burn_rate_critical` (float)
  - `slo_burn_rate_warning` (float)

Examples
```bash
# Raise warn threshold to 2k and notify services
redis-cli SET mutt:config:alerter_queue_warn_threshold 2000
redis-cli PUBLISH mutt:config:updates alerter_queue_warn_threshold

# Switch shed mode to defer (throttle instead of DLQ)
redis-cli SET mutt:config:alerter_shed_mode defer
redis-cli PUBLISH mutt:config:updates alerter_shed_mode

# Enable remediation and increase batch size
redis-cli SET mutt:config:remediation_enabled true
redis-cli SET mutt:config:remediation_batch_size 25
redis-cli PUBLISH mutt:config:updates remediation_batch_size

# Update SLO window to 12h
redis-cli SET mutt:config:slo_window_hours 12
redis-cli PUBLISH mutt:config:updates slo_window_hours
```

Validation Tips
- After setting a key, check service logs for “config update” messages.
- Confirm behavior/metrics changes (e.g., queue depth warnings, remediation counts, /api/v1/slo response values).
- If a change doesn’t take effect, verify the Pub/Sub channel and that `DYNAMIC_CONFIG_ENABLED=true`.

