Prometheus Alerts for MUTT

Overview
- Use `docs/prometheus/alerts-v25.yml` as the consolidated alert rules file for MUTT services.
- Targets assume scrape jobs named `mutt-alerter`, `mutt-moog-forwarder`, etc. Adjust to match your Prometheus config.

Included Alerts (high-value subset)
- MUTTIngestQueueNearCapacity: Warns when `mutt_ingest_queue_depth` exceeds 900k for 5m.
- MUTTAlerterDown: Fires if `up{job="mutt-alerter"} == 0` for 2m.
- MUTTMoogForwardFailures: Warns when `mutt_moog_requests_total{status=~"fail_.*"}` rate exceeds 0.1 req/s over 5m.
- MUTTMoogCircuitOpen: Critical when `mutt_moog_circuit_open == 1` for 2m.
- Plus v2.5 baseline alerts (queue high, rate-limit hits, service down for webui/ingestor).

Usage
1) Add rule file to Prometheus:

   rule_files:
     - /etc/prometheus/alerts/mutt/alerts-v25.yml

2) Ensure scrape jobs expose metrics:
   - Web UI: `http://<host>:8090/metrics`
   - Alerter: `http://<host>:8082/metrics`
   - Moog Forwarder: `http://<host>:8083/metrics`
   - Ingestor: `http://<host>:8080/metrics`

3) Label jobs appropriately, e.g. in static_configs or service discovery, set `job: mutt-alerter` for the Alerter target.

Notes
- Thresholds are conservative defaults; tune per environment.
- `MUTTMoogCircuitOpen` depends on forwarder exposing `mutt_moog_circuit_open` (included in this repo).
- Consider additional alerts for DB connectivity, Redis errors, and queue backlogs by team.
