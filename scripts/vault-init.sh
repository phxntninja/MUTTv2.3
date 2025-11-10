#!/bin/bash
# =====================================================================
# MUTT v2.3 - Vault Initialization Script
# =====================================================================
# This script initializes HashiCorp Vault with MUTT secrets.
#
# Usage:
#   ./vault-init.sh
#
# Prerequisites:
#   - Vault server running and accessible
#   - VAULT_ADDR environment variable set
#   - VAULT_TOKEN environment variable set (root token or sufficient permissions)
#
# What this script does:
#   1. Enables KV v2 secrets engine at secret/
#   2. Creates secret/mutt/prod with all MUTT secrets
#   3. Creates secret/mutt/dev with dev environment secrets
#   4. Creates a policy for MUTT services
#   5. (Optional) Creates an AppRole for automated authentication
# =====================================================================

set -euo pipefail

# =====================================================================
# Configuration
# =====================================================================
VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"
MOUNT_PATH="secret"
SECRET_PATH_PROD="mutt/prod"
SECRET_PATH_DEV="mutt/dev"

# =====================================================================
# Colors for output
# =====================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# =====================================================================
# Logging Functions
# =====================================================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =====================================================================
# Validation
# =====================================================================
validate_config() {
    if [[ -z "$VAULT_TOKEN" ]]; then
        log_error "VAULT_TOKEN environment variable is required"
        echo "Usage: VAULT_TOKEN=your_token $0"
        exit 1
    fi

    # Test Vault connection
    if ! vault status > /dev/null 2>&1; then
        log_error "Cannot connect to Vault at $VAULT_ADDR"
        exit 1
    fi

    log_info "Vault connection successful"
}

# =====================================================================
# Enable Secrets Engine
# =====================================================================
enable_secrets_engine() {
    log_info "Checking if KV v2 secrets engine is enabled at $MOUNT_PATH/..."

    if vault secrets list | grep -q "^${MOUNT_PATH}/"; then
        log_info "Secrets engine already enabled at $MOUNT_PATH/"
    else
        log_info "Enabling KV v2 secrets engine at $MOUNT_PATH/..."
        vault secrets enable -path="$MOUNT_PATH" -version=2 kv
        log_info "Secrets engine enabled"
    fi
}

# =====================================================================
# Create Production Secrets
# =====================================================================
create_prod_secrets() {
    log_info "Creating production secrets at $MOUNT_PATH/$SECRET_PATH_PROD..."

    # Generate secure random passwords
    INGEST_API_KEY=$(openssl rand -hex 32)
    WEBUI_API_KEY=$(openssl rand -hex 32)
    MOOG_API_KEY=$(openssl rand -hex 32)
    DB_PASS_CURRENT=$(openssl rand -base64 32)
    DB_PASS_NEXT=$(openssl rand -base64 32)
    REDIS_PASS_CURRENT=$(openssl rand -base64 32)
    REDIS_PASS_NEXT=$(openssl rand -base64 32)

    vault kv put "${MOUNT_PATH}/${SECRET_PATH_PROD}" \
        INGEST_API_KEY="$INGEST_API_KEY" \
        WEBUI_API_KEY="$WEBUI_API_KEY" \
        MOOG_API_KEY="$MOOG_API_KEY" \
        DB_USER="mutt_app" \
        DB_PASS_CURRENT="$DB_PASS_CURRENT" \
        DB_PASS_NEXT="$DB_PASS_NEXT" \
        REDIS_PASS_CURRENT="$REDIS_PASS_CURRENT" \
        REDIS_PASS_NEXT="$REDIS_PASS_NEXT"

    log_info "Production secrets created (dual-password scheme)"
    log_warn "IMPORTANT: Save these credentials securely!"
    echo ""
    echo "  INGEST_API_KEY:      $INGEST_API_KEY"
    echo "  WEBUI_API_KEY:       $WEBUI_API_KEY"
    echo "  MOOG_API_KEY:        $MOOG_API_KEY"
    echo "  DB_PASS_CURRENT:     $DB_PASS_CURRENT"
    echo "  DB_PASS_NEXT:        $DB_PASS_NEXT"
    echo "  REDIS_PASS_CURRENT:  $REDIS_PASS_CURRENT"
    echo "  REDIS_PASS_NEXT:     $REDIS_PASS_NEXT"
    echo ""
}

# =====================================================================
# Create Development Secrets
# =====================================================================
create_dev_secrets() {
    log_info "Creating development secrets at $MOUNT_PATH/$SECRET_PATH_DEV..."

    vault kv put "${MOUNT_PATH}/${SECRET_PATH_DEV}" \
        INGEST_API_KEY="dev-api-key-123" \
        WEBUI_API_KEY="dev-webui-key-456" \
        MOOG_API_KEY="dev-moog-key-789" \
        DB_USER="mutt_app" \
        DB_PASS_CURRENT="dev_db_pass_current" \
        DB_PASS_NEXT="dev_db_pass_next" \
        REDIS_PASS_CURRENT="dev_redis_pass_current" \
        REDIS_PASS_NEXT="dev_redis_pass_next"

    log_info "Development secrets created (dual-password scheme)"
}

# =====================================================================
# Create Vault Policy
# =====================================================================
create_policy() {
    log_info "Creating Vault policy for MUTT services..."

    cat > /tmp/mutt-policy.hcl <<EOF
# MUTT Service Policy
# Allows read access to MUTT secrets

path "secret/data/mutt/*" {
  capabilities = ["read"]
}

path "secret/metadata/mutt/*" {
  capabilities = ["list"]
}

# Allow token renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow token lookup
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
EOF

    vault policy write mutt-service /tmp/mutt-policy.hcl
    rm /tmp/mutt-policy.hcl

    log_info "Policy created: mutt-service"
}

# =====================================================================
# Create AppRole (Optional)
# =====================================================================
create_approle() {
    log_info "Creating AppRole for MUTT services..."

    # Enable AppRole auth method
    if ! vault auth list | grep -q "^approle/"; then
        vault auth enable approle
        log_info "AppRole auth method enabled"
    fi

    # Create AppRole
    vault write auth/approle/role/mutt-service \
        token_policies="mutt-service" \
        token_ttl=24h \
        token_max_ttl=72h \
        secret_id_ttl=0

    # Get Role ID
    ROLE_ID=$(vault read -field=role_id auth/approle/role/mutt-service/role-id)

    # Generate Secret ID
    SECRET_ID=$(vault write -field=secret_id -f auth/approle/role/mutt-service/secret-id)

    log_info "AppRole created: mutt-service"
    log_warn "IMPORTANT: Save these credentials for AppRole authentication!"
    echo ""
    echo "  ROLE_ID:    $ROLE_ID"
    echo "  SECRET_ID:  $SECRET_ID"
    echo ""
    echo "Login with AppRole:"
    echo "  vault write auth/approle/login role_id=$ROLE_ID secret_id=$SECRET_ID"
    echo ""
}

# =====================================================================
# Verify Secrets
# =====================================================================
verify_secrets() {
    log_info "Verifying secrets..."

    # Read production secrets
    if vault kv get "${MOUNT_PATH}/${SECRET_PATH_PROD}" > /dev/null 2>&1; then
        log_info "✓ Production secrets readable"
    else
        log_error "✗ Cannot read production secrets"
        exit 1
    fi

    # Read development secrets
    if vault kv get "${MOUNT_PATH}/${SECRET_PATH_DEV}" > /dev/null 2>&1; then
        log_info "✓ Development secrets readable"
    else
        log_error "✗ Cannot read development secrets"
        exit 1
    fi

    log_info "Verification complete"
}

# =====================================================================
# Main
# =====================================================================
main() {
    echo "=========================================="
    echo "MUTT v2.3 - Vault Initialization"
    echo "=========================================="
    echo ""

    validate_config
    enable_secrets_engine
    create_prod_secrets
    create_dev_secrets
    create_policy

    # Uncomment to create AppRole
    # create_approle

    verify_secrets

    echo ""
    log_info "Vault initialization complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Save the credentials displayed above"
    echo "  2. Update rsyslog configuration with INGEST_API_KEY"
    echo "  3. Configure services to use Vault for secret retrieval"
    echo "  4. (Optional) Use AppRole for automated authentication"
    echo ""
}

main "$@"
