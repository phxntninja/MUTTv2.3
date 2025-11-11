MUTT v2.5 — Code Examples

Ingest Events (curl)
curl -s -X POST http://localhost:8080/api/v2/ingest \
  -H 'Content-Type: application/json' -H 'X-API-KEY: <INGEST_API_KEY>' \
  -d '{"timestamp":"2025-11-10T12:00:00Z","message":"hello","hostname":"dev1","syslog_severity":4}'

Create/Update/Delete Rules (curl)
# Create
curl -s -X POST -H 'Content-Type: application/json' -H 'X-API-KEY: <WEBUI_API_KEY>' \
  http://localhost:8090/api/v2/rules \
  -d '{"match_string":"ERROR","match_type":"contains","priority":100,"prod_handling":"Page_and_ticket","dev_handling":"Ticket_only","team_assignment":"NETO"}'
# Update (with audit reason)
curl -s -X PUT -H 'Content-Type: application/json' -H 'X-API-KEY: <WEBUI_API_KEY>' \
  http://localhost:8090/api/v2/rules/123 \
  -d '{"priority":200, "is_active":false, "reason":"downgrade in staging"}'
# Delete
curl -s -X DELETE -H 'X-API-KEY: <WEBUI_API_KEY>' http://localhost:8090/api/v2/rules/123

Fetch Audit Logs (curl)
curl -s -H 'X-API-KEY: <WEBUI_API_KEY>' \
  'http://localhost:8090/api/v2/audit-logs?page=1&limit=50&hostname=router1&start_date=2025-11-01'

Dynamic Config (muttdev CLI)
# List keys
python scripts/muttdev.py config --list
# Get a key
python scripts/muttdev.py config --get alerter_queue_warn_threshold
# Set a key and publish change notification
python scripts/muttdev.py config --set alerter_shed_mode dlq --publish

Retention Jobs (CLI)
# Dry-run cleanup
python scripts/muttdev.py retention --dry-run
# Create future partitions (cron monthly helper provided)
bash scripts/cron/mutt-partition-create
