Next Step: Vault Setup & Configuration Guide (Appendix B)
Priority: CRITICAL (Deploy Blocker)
All v2.3+ services depend on HashiCorp Vault for secrets management. Without proper Vault configuration, services will fail to start with authentication errors. This guide provides step-by-step instructions for DevOps teams.
Vault Setup Guide for MUTT v2.3+
Overview
This guide covers:

    Development setup (single-node Vault)
    Production setup (HA Vault cluster)
    AppRole configuration for each MUTT service
    Secret structure and injection
    Troubleshooting common errors

Prerequisites

    Vault binary (v1.15+) installed
    TLS certificates for Vault (production)
    vault CLI configured with VAULT_ADDR
    Access to create policies and enable auth methods

Section 1: Development Vault Setup (For Testing)
Step 1.1: Start Vault in Dev Mode
bash
Copy

# This is INSECURE - for local testing only
vault server -dev -dev-listen-address="0.0.0.0:8200"

Export the root token:
bash
Copy

export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root-token-from-vault-output'

Step 1.2: Enable KV v2 Secrets Engine
bash
Copy

# Enable KV v2 at the path used by MUTT
vault secrets enable -version=2 -path=secret kv-v2

# Verify
vault secrets list

Section 2: Production Vault Setup
Step 2.1: Initialize Vault Cluster
bash
Copy

# On first Vault node
vault operator init -key-shares=5 -key-threshold=3

# Save the output securely:
# - Unseal keys (5)
# - Root token

# Unseal the node (repeat for 3 keys)
vault operator unseal <unseal-key-1>
vault operator unseal <unseal-key-2>
vault operator unseal <unseal-key-3>

# Join other nodes (if HA)
vault operator raft join https://vault-node-1:8200

Step 2.2: Enable Audit Logging (Recommended)
bash
Copy

vault audit enable file file_path=/var/log/vault/audit.log

Section 3: AppRole Configuration
Step 3.1: Create Policy Files
Create three policy files for MUTT services:
mutt-alerter-policy.hcl
hcl
Copy

# Read-only access to secrets
path "secret/data/mutt" {
  capabilities = ["read"]
}

# Allow token self-renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

mutt-moog-forwarder-policy.hcl
hcl
Copy

# Same as alerter
path "secret/data/mutt" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

mutt-webui-policy.hcl
hcl
Copy

# Same as alerter
path "secret/data/mutt" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

mutt-ingest-webhook-policy.hcl
hcl
Copy

# Same as alerter (if using Component #1)
path "secret/data/mutt" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

Step 3.2: Write Policies to Vault
bash
Copy

vault policy write mutt-alerter mutt-alerter-policy.hcl
vault policy write mutt-moog-forwarder mutt-moog-forwarder-policy.hcl
vault policy write mutt-webui mutt-webui-policy.hcl
vault policy write mutt-ingest-webhook mutt-ingest-webhook-policy.hcl

# Verify
vault policy list

Step 3.3: Enable AppRole Auth Method
bash
Copy

vault auth enable approle

# Verify
vault auth list

Step 3.4: Create AppRole Roles
bash
Copy

# Event Processor (Alerter)
vault write auth/approle/role/mutt-alerter-role \
    secret_id_ttl=24h \
    token_num_uses=0 \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_num_uses=0 \
    policies="mutt-alerter"

# Moog Forwarder
vault write auth/approle/role/mutt-moog-forwarder-role \
    secret_id_ttl=24h \
    token_num_uses=0 \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_num_uses=0 \
    policies="mutt-moog-forwarder"

# Web UI
vault write auth/approle/role/mutt-webui-role \
    secret_id_ttl=24h \
    token_num_uses=0 \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_num_uses=0 \
    policies="mutt-webui"

# Ingest Webhook
vault write auth/approle/role/mutt-ingest-webhook-role \
    secret_id_ttl=24h \
    token_num_uses=0 \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_num_uses=0 \
    policies="mutt-ingest-webhook"

Section 4: Generate Role IDs and Secret IDs
Step 4.1: Get Role IDs (Public)
bash
Copy

# These are NOT secrets - can be stored in env vars/configmaps
vault read auth/approle/role/mutt-alerter-role/role-id
# Save output as ROLE_ID_ALERTER

vault read auth/approle/role/mutt-moog-forwarder-role/role-id
# Save as ROLE_ID_MOOG

vault read auth/approle/role/mutt-webui-role/role-id
# Save as ROLE_ID_WEBUI

vault read auth/approle/role/mutt-ingest-webhook-role/role-id
# Save as ROLE_ID_INGEST

Step 4.2: Generate Secret IDs (CONFIDENTIAL)
bash
Copy

# These are SECRETS - must be stored securely
vault write -f auth/approle/role/mutt-alerter-role/secret-id
# Save output "secret_id" to /etc/mutt/secrets/vault_secret_id (file used by alerter)

vault write -f auth/approle/role/mutt-moog-forwarder-role/secret-id
# Save for forwarder

vault write -f auth/approle/role/mutt-webui-role/secret-id
# Save for webui

vault write -f auth/approle/role/mutt-ingest-webhook-role/secret-id
# Save for ingest webhook

Kubernetes Secret Example:
yaml
Copy

apiVersion: v1
kind: Secret
metadata:
  name: vault-secret-id-alerter
type: Opaque
stringData:
  vault_secret_id: "your-secret-id-here"

Section 5: Write Secrets to Vault KV v2
Step 5.1: Prepare Secrets JSON
JSON
Copy

{
  "REDIS_PASS": "super-strong-redis-password",
  "DB_PASS": "super-strong-db-password",
  "MOOG_API_KEY": "moogsoft-api-key-here",
  "WEBUI_API_KEY": "webui-management-key-here",
  "SESSION_SECRET_KEY": "a-very-long-random-string-min-32-chars-for-sessions",
  "WEBHOOK_API_KEY": "webhook-source-authentication-key"
}

Step 5.2: Write to Vault
bash
Copy

vault kv put secret/mutt \
    REDIS_PASS="super-strong-redis-password" \
    DB_PASS="super-strong-db-password" \
    MOOG_API_KEY="moogsoft-api-key-here" \
    WEBUI_API_KEY="webui-management-key-here" \
    SESSION_SECRET_KEY="a-very-long-random-string-min-32-chars-for-sessions" \
    WEBHOOK_API_KEY="webhook-source-authentication-key"

# Verify
vault kv get secret/mutt

Section 6: Service Environment Variables
Event Processor (Alerter)
bash
Copy

export VAULT_ADDR="https://vault.prod.svc:8200"
export VAULT_ROLE_ID="role-id-from-step-4.1"
export VAULT_SECRET_ID_FILE="/etc/mutt/secrets/vault_secret_id"
export VAULT_SECRETS_PATH="secret/mutt"

Moog Forwarder
bash
Copy

export VAULT_ADDR="https://vault.prod.svc:8200"
export VAULT_ROLE_ID="role-id-from-step-4.1"
export VAULT_SECRET_ID_FILE="/etc/mutt/secrets/vault_secret_id"
export VAULT_SECRETS_PATH="secret/mutt"

Web UI
bash
Copy

export VAULT_ADDR="https://vault.prod.svc:8200"
export VAULT_ROLE_ID="role-id-from-step-4.1"
export VAULT_SECRET_ID_FILE="/etc/mutt/secrets/vault_secret_id"
export VAULT_SECRETS_PATH="secret/mutt"

Ingest Webhook
bash
Copy

export VAULT_ADDR="https://vault.prod.svc:8200"
export VAULT_ROLE_ID="role-id-from-step-4.1"
export VAULT_SECRET_ID_FILE="/etc/mutt/secrets/vault_secret_id"
export VAULT_SECRETS_PATH="secret/mutt"

Section 7: Troubleshooting
Error 1: permission denied on secret read
Cause: Policy doesn't grant read access to secret/data/mutt
Fix:
bash
Copy

vault policy read mutt-alerter  # Check policy
# Update policy if needed
vault policy write mutt-alerter mutt-alerter-policy.hcl

Error 2: invalid secret ID or permission denied on AppRole login
Cause: Secret ID expired or wrong Role ID
Fix:

    Regenerate secret ID: vault write -f auth/approle/role/mutt-alerter-role/secret-id
    Verify Role ID: vault read auth/approle/role/mutt-alerter-role/role-id
    Check TTL: vault read auth/approle/role/mutt-alerter-role

Error 3: failed to renew token: ttl<0
Cause: Token is not renewable or max TTL exceeded
Fix:

    Check token status: vault write auth/token/lookup-self
    Ensure policy includes auth/token/renew-self capability
    Increase token_max_ttl in AppRole config

Error 4: connection refused to Vault
Cause: Vault not running, wrong address, or TLS issues
Fix:
bash
Copy

# Test connectivity
curl -k https://vault.prod.svc:8200/v1/sys/health

# Check service DNS
nslookup vault.prod.svc

# Check TLS
openssl s_client -connect vault.prod.svc:8200 -CAfile /etc/mutt/certs/vault-ca.pem

Section 8: Production Hardening
8.1: Use Vault Agent Injector (Kubernetes)
yaml
Copy

# In pod spec
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "mutt-alerter-role"
  vault.hashicorp.com/agent-inject-secret-vault_secret_id: "secret/mutt-alerter-secret-id"
spec:
  serviceAccountName: mutt-vault-auth

8.2: Rotate Secret IDs Regularly
bash
Copy

# Create new secret ID
vault write -f auth/approle/role/mutt-alerter-role/secret-id

# Revoke old one after deployment
vault write auth/approle/role/mutt-alerter-role/secret-id/destroy secret_id="<old-id>"

8.3: Monitor Vault Token Usage
bash
Copy

# Enable audit device
vault audit enable file file_path=/var/log/vault/audit.log

# Monitor metrics
vault metrics | grep vault.token

Summary
After completing this guide:

    ✅ Vault is running (dev or HA)
    ✅ KV v2 secrets engine enabled
    ✅ AppRole auth enabled
    ✅ Service policies created and assigned
    ✅ Role IDs and Secret IDs generated
    ✅ Secrets written to secret/mutt
    ✅ Services configured with correct env vars

Your MUTT services will now successfully authenticate to Vault and retrieve secrets on startup.
