Release Checklist (v2.5)

Use this checklist to cut a release confidently.

Preflight
- [ ] CI green on main (lint, type, tests, coverage ≥ 80%)
- [ ] E2E smoke test (scripts/run_e2e.sh) passes locally
- [ ] Prometheus alert rules parse in target environment (alerts-v25.yml)

Versioning
- [ ] Update README version badge
- [ ] Update CHANGELOG.md with highlights and dates
- [ ] Tag the release (e.g., git tag v2.5.0)

Artifacts
- [ ] Build/push container images (optional)
- [ ] Verify Dockerfile(s) and image scan (if applicable)

Docs
- [ ] docs/INDEX.md updated with new/changed docs
- [ ] API docs reflect current endpoints and headers
- [ ] Screenshots captured/updated

Ops
- [ ] Confirm CronJobs (retention, partition-create) manifests and schedules
- [ ] Runbook entries for API key rotation and CB tuning verified
- [ ] Vault secrets present and policies validated

Post-Release
- [ ] Create GitHub release notes from CHANGELOG.md
- [ ] Announce internally and link master docs index
