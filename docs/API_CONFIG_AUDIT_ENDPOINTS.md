Config Audit API Endpoints

Overview
- Read change history recorded in `config_audit_log`.
- Supports filtering and pagination.
- Requires `X-API-KEY` for authentication.

Endpoints
- GET `/api/v2/config-audit` (also available as `/api/v1/config-audit`)

Query Parameters
- `page` (int, default 1): page number
- `limit` (int, default 50, max 200): items per page
- `changed_by` (string): filter by user or API key identifier suffix
- `table_name` (string): e.g., `alert_rules`
- `record_id` (int): specific record identifier
- `operation` (string): `CREATE` | `UPDATE` | `DELETE`
- `start_date` (ISO8601): inclusive lower bound on `changed_at`
- `end_date` (ISO8601): inclusive upper bound on `changed_at`

Response
```
{
  "changes": [
    {
      "id": 1,
      "changed_at": "2025-11-10T10:00:00Z",
      "changed_by": "admin_api_key",
      "operation": "CREATE",
      "table_name": "alert_rules",
      "record_id": 42,
      "reason": "initial rule",
      "correlation_id": "..."
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 123, "pages": 3 }
}
```

Headers
- `X-API-Version`: `v2.5`
- `X-API-Deprecated`: `true` for `/api/v1/*`, else `false`
- `X-API-Supported-Versions`: `v2.5, v2.0, v1.0`

