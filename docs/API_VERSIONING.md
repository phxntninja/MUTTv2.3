# MUTT API Versioning Guide

## Overview

MUTT v2.5 implements comprehensive API versioning to ensure backward compatibility and graceful deprecation of endpoints. This allows us to evolve the API while maintaining support for existing clients.

## Version Negotiation

### Requesting a Specific Version

Clients can request a specific API version using one of three methods (in order of precedence):

1. **Accept-Version Header** (Recommended)
```bash
curl -H "Accept-Version: 2.0" \
     -H "X-API-KEY: your-key" \
     https://mutt.example.com/api/v1/rules
```

2. **X-API-Version Header**
```bash
curl -H "X-API-Version: 1.0" \
     -H "X-API-KEY: your-key" \
     https://mutt.example.com/api/v1/rules
```

3. **Query Parameter**
```bash
curl "https://mutt.example.com/api/v1/rules?api_version=2.0&api_key=your-key"
```

### Default Behavior

If no version is specified, the API defaults to version **2.0** (current version).

## Version Headers

All API responses include the following headers:

### X-API-Version
The current API version of the server.

```
X-API-Version: 2.0
```

### X-API-Supported-Versions
Comma-separated list of all supported versions.

```
X-API-Supported-Versions: 2.0, 1.0
```

### X-API-Deprecated (if applicable)
Warning that the endpoint is deprecated, including removal information.

```
X-API-Deprecated: Deprecated in version 2.0, will be removed in 3.0 (removal date: 2026-01-01)
```

### X-API-Sunset (if applicable)
ISO 8601 date when the endpoint will be removed.

```
X-API-Sunset: 2026-01-01
```

## Version Information Endpoint

### GET /api/v1/version

Returns comprehensive version information including current version, supported versions, and changelogs.

**No authentication required.**

#### Example Request
```bash
curl https://mutt.example.com/api/v1/version
```

#### Example Response
```json
{
  "current_version": "2.0",
  "default_version": "2.0",
  "supported_versions": ["2.0", "1.0"],
  "version_history": {
    "2.0": {
      "released": "2025-11-10",
      "status": "current",
      "changes": [
        "Added configuration audit logging",
        "Enhanced filtering for audit logs",
        "Added /api/v1/audit endpoint",
        "Added /audit web UI viewer",
        "Normalized metric labels to status={success|fail}",
        "Added SLO monitoring endpoint",
        "Added alerter backpressure controls"
      ]
    },
    "1.0": {
      "released": "2024-01-01",
      "status": "supported",
      "changes": [
        "Initial stable API release",
        "Basic CRUD operations for rules",
        "Event audit logs",
        "Metrics dashboard",
        "Dynamic configuration API"
      ],
      "deprecated_in": "3.0",
      "removal_date": "2026-01-01"
    }
  }
}
```

## Supported Versions

### Version 2.0 (Current)
- **Status:** Current
- **Released:** 2025-11-10
- **Support:** Full support

**New Features:**
- Configuration change audit logging (`/api/v1/audit`)
- Advanced audit log filtering
- Web UI audit viewer (`/audit`)
- SLO monitoring and reporting
- Alerter backpressure controls
- Normalized metric labels

### Version 1.0
- **Status:** Supported
- **Released:** 2024-01-01
- **Support:** Full support until 2026-01-01
- **Deprecation:** Will be deprecated in version 3.0
- **Removal Date:** 2026-01-01

**Features:**
- Basic CRUD operations for alert rules
- Event audit logs (not configuration audit)
- Metrics dashboard
- Dynamic configuration API
- Dev hosts and device team management

## Versioning Best Practices

### For API Consumers

1. **Always Specify Version**
   ```bash
   # Good
   curl -H "Accept-Version: 2.0" https://mutt.example.com/api/v1/rules

   # Avoid (relies on default)
   curl https://mutt.example.com/api/v1/rules
   ```

2. **Monitor Version Headers**
   Check response headers for deprecation warnings:
   ```python
   response = requests.get(url, headers={'Accept-Version': '2.0'})

   if 'X-API-Deprecated' in response.headers:
       print(f"Warning: {response.headers['X-API-Deprecated']}")
   ```

3. **Plan for Upgrades**
   When you see `X-API-Deprecated` or `X-API-Sunset` headers, plan to upgrade before the removal date.

4. **Test with Multiple Versions**
   Test your integration with multiple API versions to ensure smooth transitions.

### For API Developers

1. **Use Versioned Endpoint Decorator**
   ```python
   from api_versioning import versioned_endpoint

   @app.route('/api/v1/new-feature', methods=['GET'])
   @require_api_key
   @versioned_endpoint(since='2.0')
   def new_feature():
       return jsonify({"data": "value"})
   ```

2. **Mark Deprecated Endpoints**
   ```python
   @versioned_endpoint(
       since='1.0',
       deprecated_in='2.0',
       removed_in='3.0',
       removal_date='2026-01-01'
   )
   def old_endpoint():
       return jsonify({"legacy": "data"})
   ```

3. **Maintain Changelogs**
   Update `VERSION_HISTORY` in `api_versioning.py` with each release.

## Breaking Changes Policy

### What Constitutes a Breaking Change?

- Removing an endpoint or parameter
- Changing response format or structure
- Changing authentication requirements
- Modifying error codes or messages
- Changing default behavior

### Breaking Change Process

1. **Announce in advance** (minimum 6 months notice)
2. **Mark as deprecated** with clear migration path
3. **Add to changelog** in new version
4. **Set sunset date** at least 6 months in future
5. **Maintain backward compatibility** until sunset date

### Non-Breaking Changes

These can be made without version changes:
- Adding new optional parameters
- Adding new endpoints
- Adding new fields to responses (additive only)
- Fixing bugs
- Improving error messages (without changing codes)
- Performance improvements

## Migration Guide

### Migrating from v1.0 to v2.0

#### New Endpoints
- `/api/v1/audit` - Configuration change audit logs (previously didn't exist)
- `/api/v1/version` - Version information endpoint

#### Changed Behavior
- **Metric Labels:** Now use `status={success|fail}` instead of custom status values
- **Audit Logs:** `GET /api/v1/audit-logs` now returns event audit logs only
- **Config Audit:** Use `/api/v1/audit` for configuration change audit logs

#### Example Migration

**Before (v1.0):**
```python
# Get all audit logs (mixed event and config)
response = requests.get(
    'https://mutt.example.com/api/v1/audit-logs',
    headers={'X-API-KEY': key}
)
```

**After (v2.0):**
```python
# Get event audit logs
event_logs = requests.get(
    'https://mutt.example.com/api/v1/audit-logs',
    headers={'X-API-KEY': key, 'Accept-Version': '2.0'}
)

# Get configuration change audit logs (new!)
config_logs = requests.get(
    'https://mutt.example.com/api/v1/audit',
    headers={'X-API-KEY': key, 'Accept-Version': '2.0'}
)
```

## Error Responses

### 410 Gone

Returned when accessing a removed endpoint:

```json
{
  "error": "Endpoint removed",
  "message": "This endpoint was removed in version 3.0",
  "removed_in": "3.0",
  "removal_date": "2026-01-01",
  "current_version": "2.0"
}
```

**Resolution:** Upgrade to a newer endpoint or API version.

## FAQ

### Q: What happens if I don't specify a version?

A: The API defaults to version 2.0 (current version). However, we recommend always specifying the version explicitly.

### Q: Can I use an unsupported version?

A: No. Requests for unsupported versions will fall back to the default version (2.0).

### Q: How long are older versions supported?

A: Major versions are supported for at least 12 months after deprecation is announced, with a minimum 6-month notice before removal.

### Q: Will the URL structure change?

A: No. The URL path (`/api/v1/*`) remains stable. Version negotiation is done through headers or query parameters.

### Q: How do I know when my version will be removed?

A: Check the `X-API-Sunset` header in responses, or call `/api/v1/version` to see deprecation dates.

### Q: Can I test future versions?

A: Not directly. Future versions are not exposed until they are officially released. However, you can review changelogs and documentation before migrating.

## Support

For questions about API versioning:
- Check version information: `GET /api/v1/version`
- Review this documentation
- Contact the MUTT development team

---

**Last Updated:** 2025-11-10
**API Version:** 2.0
