# ADR-002: Vault vs. Kubernetes Secrets

- Status: Accepted
- Date: 2025-11-10

Context
- MUTT runs on RHEL and OpenShift; needs secret rotation and AppRole flows.

Decision
- Use HashiCorp Vault (KV v2) with AppRole and token renewal; optionally read-only fallback to K8s secrets.

Consequences
- Pros: Rotation, policy control, audit trail; consistent across bare metal and K8s.
- Cons: Extra infra component; requires operators familiar with Vault.

Alternatives Considered
- K8s Secrets: Simpler in-cluster but lacks rotation/integration on RHEL hosts without K8s.

References
- scripts/vault-init.sh
- services/*: Vault usage patterns documented in README

