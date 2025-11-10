# MUTT API Version Lifecycle Policy v1.0

## 1. Version Stages

-   **Current:** Actively maintained, recommended for new integrations.
-   **Supported:** Maintained for backward compatibility.
-   **Deprecated:** Announced for removal, warning headers sent.
-   **Removed:** No longer available (410 Gone responses).

## 2. Lifecycle Timelines

-   **Support Duration:** Minimum 12 months after deprecation.
-   **Deprecation Notice:** Minimum 6 months before removal.
-   **Breaking Changes:** Only allowed in major versions (e.g., 1.0 -> 2.0).

## 3. Communication Requirements

-   **Deprecation Announcement:** Release notes + email to API key owners.
-   **Warning Headers:** `X-API-Deprecated` and `X-API-Sunset` headers included in responses.
-   **Documentation:** Migration guide published with deprecation.

## 4. Process

-   **New Version Release:** Update `VERSION_HISTORY` in `services/api_versioning.py`.
-   **Deprecation Trigger:** Add `deprecated_in`, `removed_in` to endpoint decorator.
-   **Removal:** Only after sunset date + confirmed no usage via metrics.
