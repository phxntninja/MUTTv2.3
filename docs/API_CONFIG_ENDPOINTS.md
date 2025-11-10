# Web UI Config Management API

Authentication
- Header: `X-API-KEY: <your-key>` (or `?api_key=...` for browser use)

Endpoints
- GET `/api/v1/config`
  - Description: List all dynamic configuration key/values.
  - Response: `{ "config": { "key": "value", ... } }`
- PUT `/api/v1/config/<key>`
  - Description: Update a specific dynamic config value.
  - Body (JSON): `{ "value": "<string>", "reason": "<optional>" }`
  - Response: `{ "key": "<key>", "old_value": "...", "new_value": "..." }`
  - Side effect: Best‑effort audit record in `config_audit_log`.
- GET `/api/v1/config/history`
  - Description: Paginated history of config changes (audit log).
  - Query: `page` (default 1), `limit` (default 50, max 200)
  - Response: `{ "history": [ ... ], "pagination": { ... } }`

Notes
- DynamicConfig uses Redis for storage and PubSub; changes propagate without restarts.
- History is read from `config_audit_log` with `table_name='dynamic_config'`.

Examples
```bash
# List config
curl -H "X-API-KEY: $WEBUI_API_KEY" http://webui.local/api/v1/config | jq

# Update a key
curl -X PUT -H "Content-Type: application/json" -H "X-API-KEY: $WEBUI_API_KEY" \
  -d '{"value":"600","reason":"increase cache TTL"}' \
  http://webui.local/api/v1/config/cache_reload_interval | jq

# View history
curl -H "X-API-KEY: $WEBUI_API_KEY" \
  "http://webui.local/api/v1/config/history?page=1&limit=20" | jq
```

