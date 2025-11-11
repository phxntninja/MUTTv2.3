# MUTT v2.5 - Installation & Deployment Guide

**Version:** 1.0
**Last Updated:** 2025-11-10
**Maintained By:** Operations Team
**Audience:** System Administrators, SREs, DevOps Engineers
**Prerequisites:** Linux system administration experience, basic Python knowledge
**Related Docs:**
- [Service Operations Guide](SERVICE_OPERATIONS.md)
- [Configuration Guide](CONFIGURATION_GUIDE.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Deployment Architecture](#deployment-architecture)
3. [Prerequisites](#prerequisites)
4. [Pre-Installation Planning](#pre-installation-planning)
5. [Installation Steps](#installation-steps)
6. [Post-Installation Verification](#post-installation-verification)
7. [Common Installation Issues](#common-installation-issues)
8. [Automated Deployment](#automated-deployment)
9. [Appendix](#appendix)

---

## Overview

This guide provides complete instructions for installing MUTT v2.5 on standalone RHEL/CentOS servers. This is the **primary production deployment model** for MUTT.

### What You'll Deploy

- **5 MUTT Services**:
  - Ingestor (HTTP API for event ingestion)
  - Alerter (Rule processing engine)
  - Moog Forwarder (External system integration)
  - Web UI (Management interface and dashboard)
  - Remediation (DLQ processing and recovery)

- **Supporting Infrastructure** (if not already present):
  - Redis (message queue and caching)
  - PostgreSQL (audit logs and configuration)
  - HashiCorp Vault (secrets management)

### Deployment Time

- **Automated**: 30-60 minutes (using deployment script)
- **Manual**: 2-4 hours (following this guide step-by-step)

---

## Deployment Architecture

### Single-Server Deployment (Development/Small Production)

```
┌─────────────────────────────────────────────────────┐
│ RHEL 8/9 Server                                     │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Ingestor │  │ Alerter  │  │  Moog    │         │
│  │  :8080   │  │  :8081   │  │Forwarder │         │
│  └────┬─────┘  └────┬─────┘  │  :8084   │         │
│       │             │         └────┬─────┘         │
│       └─────────┬───┴──────────────┘               │
│                 │                                   │
│           ┌─────▼─────┐  ┌──────────┐             │
│           │  Redis    │  │PostgreSQL│             │
│           │   :6379   │  │   :5432  │             │
│           └───────────┘  └──────────┘             │
│                                                     │
│  ┌──────────┐  ┌──────────┐                       │
│  │  Web UI  │  │Remediation│                      │
│  │  :8090   │  │ :8086/87  │                      │
│  └──────────┘  └──────────┘                       │
└─────────────────────────────────────────────────────┘
```

### Multi-Server Deployment (Production)

```
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ App Server 1   │  │ App Server 2   │  │ App Server 3   │
│ ┌──────────┐   │  │ ┌──────────┐   │  │ ┌──────────┐   │
│ │Ingestor  │   │  │ │Ingestor  │   │  │ │Ingestor  │   │
│ │Alerter   │   │  │ │Alerter   │   │  │ │Alerter   │   │
│ │Forwarder │   │  │ │Forwarder │   │  │ │Forwarder │   │
│ │WebUI     │   │  │ │WebUI     │   │  │ │WebUI     │   │
│ └────┬─────┘   │  │ └────┬─────┘   │  │ └────┬─────┘   │
└──────┼─────────┘  └──────┼─────────┘  └──────┼─────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                          │
              ┌───────────▼────────────┐
              │   Load Balancer       │
              └───────────┬────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼────┐    ┌──────▼──────┐  ┌─────▼──────┐
    │ Redis   │    │ PostgreSQL  │  │   Vault    │
    │Sentinel │    │   Patroni   │  │     HA     │
    │Cluster  │    │   Cluster   │  │            │
    └─────────┘    └─────────────┘  └────────────┘
```

---

## Prerequisites

### Operating System Requirements

**Supported:**
- Red Hat Enterprise Linux 8.x or 9.x
- CentOS Stream 8 or 9
- Rocky Linux 8.x or 9.x
- AlmaLinux 8.x or 9.x

**Not Supported:**
- RHEL/CentOS 7.x (Python 3.6 is too old)
- Debian/Ubuntu (different package manager, use containerized deployment)

### System Resources (Per Server)

**Minimum** (Development/Testing):
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB
- Network: 1 Gbps

**Recommended** (Production):
- CPU: 8 cores
- RAM: 16 GB
- Disk: 200 GB (SSD preferred for PostgreSQL)
- Network: 10 Gbps

**Scaling Guidelines:**
- **< 1,000 EPS**: Minimum resources
- **1,000-10,000 EPS**: Recommended resources
- **> 10,000 EPS**: Multiple servers + load balancer

### Software Dependencies

**Required:**
- Python 3.10+ (3.12 recommended)
- systemd
- firewalld or iptables
- Redis 6.0+ (with AOF persistence)
- PostgreSQL 12+ (14+ recommended)
- HashiCorp Vault 1.8+

**Optional:**
- Prometheus (for metrics collection)
- Grafana (for dashboards)
- SELinux (can be disabled but recommended for production)

### Network Requirements

**Outbound Access Required:**
- PyPI (pypi.org) - for Python package installation
- Moogsoft webhook endpoint (or your alert destination)
- Vault server
- Redis server
- PostgreSQL server

**Inbound Ports to Open:**
- 8080 - Ingestor HTTP API
- 8081 - Alerter health check
- 8082 - Alerter Prometheus metrics
- 8083 - Moog Forwarder Prometheus metrics
- 8084 - Moog Forwarder health check
- 8086 - Remediation metrics
- 8087 - Remediation health
- 8090 - Web UI

**Firewall Rules:**
```bash
# If using firewalld
sudo firewall-cmd --permanent --add-port=8080-8090/tcp
sudo firewall-cmd --reload

# If using iptables
sudo iptables -A INPUT -p tcp --match multiport --dports 8080:8090 -j ACCEPT
sudo service iptables save
```

### Access Requirements

You will need:
- Root or sudo access on the RHEL server
- Network access to Redis, PostgreSQL, and Vault
- Vault AppRole credentials (Role ID and Secret ID)
- API keys for MUTT services (or Vault paths to them)
- TLS certificates (if using TLS - recommended for production)

---

## Pre-Installation Planning

### 1. Infrastructure Planning

**Decision Matrix:**

| Component | Single Server | Multi-Server | Notes |
|-----------|--------------|--------------|-------|
| MUTT Services | Same server | Distributed | All 5 services |
| Redis | localhost | External cluster | Sentinel/Cluster for HA |
| PostgreSQL | localhost | External cluster | Patroni for HA |
| Vault | External | External cluster | Never localhost in production |
| Load Balancer | None | HAProxy/Nginx | For multi-server only |

**Recommended Configurations:**

- **Development**: Everything on one server (including Redis/Postgres)
- **Staging**: MUTT services on one server, separate Redis/Postgres/Vault
- **Production**: Multiple MUTT servers, clustered Redis/Postgres/Vault

### 2. Service Topology Planning

Decide which services to run on each server:

**Option A: All Services on All Servers** (Recommended)
- Pros: Simple, automatic failover, balanced load
- Cons: Higher resource usage per server
- Use when: Running 2-4 servers

**Option B: Service-Specific Servers**
- Pros: Easier to scale individual services
- Cons: More complex routing, single points of failure
- Use when: Running 5+ servers with very high load

**Option C: Tiered Deployment**
- Tier 1: Ingestor only (public-facing)
- Tier 2: Alerter + Forwarder (processing)
- Tier 3: Web UI + Remediation (management)
- Use when: DMZ/security zones required

### 3. Directory Structure Planning

Standard MUTT installation uses these directories:

```
/opt/mutt/               # Application root
├── venv/                # Python virtual environment
├── services/            # Service Python modules
│   ├── __init__.py
│   ├── ingestor_service.py
│   ├── alerter_service.py
│   ├── moog_forwarder_service.py
│   ├── web_ui_service.py
│   └── remediation_service.py
├── config/              # Optional: service-specific configs
└── requirements.txt     # Python dependencies

/etc/mutt/               # Configuration root
├── mutt.env             # Environment variables (SECRETS!)
├── mutt.env.template    # Template for env vars
├── secrets/             # Vault Secret IDs, API keys
│   └── vault_secret_id  # Vault AppRole Secret ID
└── certs/               # TLS certificates
    ├── ca.pem           # Root CA
    ├── redis-ca.pem     # Redis CA (optional)
    └── postgres-ca.pem  # PostgreSQL CA (optional)

/var/log/mutt/           # Log files
├── ingestor-access.log  # Gunicorn access logs
├── ingestor-error.log   # Gunicorn error logs
├── webui-access.log
├── webui-error.log
└── (service logs go to journald via systemd)

/var/run/mutt/           # Runtime files (PIDs, sockets)

/etc/systemd/system/     # systemd service files
├── mutt-ingestor.service
├── mutt-alerter.service
├── mutt-moog-forwarder.service
├── mutt-webui.service
└── mutt-remediation.service
```

**Important**: Do NOT change these paths without updating systemd service files!

### 4. User and Permissions Planning

MUTT runs as a dedicated system user:

- **User**: `mutt`
- **Group**: `mutt`
- **Shell**: `/bin/false` (no login allowed)
- **Home**: `/opt/mutt`
- **Purpose**: Security isolation, file ownership

**File Permissions:**
- `/opt/mutt/*` - Owner: mutt:mutt, Mode: 755 (directories), 644 (files)
- `/etc/mutt/*` - Owner: mutt:mutt, Mode: 700 (directory), 600 (secrets)
- `/var/log/mutt/*` - Owner: mutt:mutt, Mode: 755 (directory), 640 (logs)

### 5. Secret Management Planning

**Required Secrets:**
1. Redis password (if authentication enabled)
2. PostgreSQL password
3. Vault AppRole Secret ID
4. Ingestor API key
5. Web UI API key
6. Moog API key (optional, can be in Vault)

**Secret Storage Options:**

**Option A: All in Vault** (Recommended for Production)
- Secrets stored in Vault at `secret/mutt`
- Services fetch secrets at startup using AppRole
- Automatic secret rotation supported

**Option B: Mix of Vault and Environment** (Acceptable for Staging)
- Critical secrets (DB passwords) in Vault
- API keys in environment variables
- Easier initial setup, less secure

**Option C: All in Environment** (Development Only)
- All secrets in `/etc/mutt/mutt.env`
- Simple but NOT suitable for production

### 6. TLS/SSL Planning

**TLS Usage:**

| Connection | TLS Required? | Certificate Type |
|------------|---------------|------------------|
| Redis → MUTT | Recommended | CA certificate for verification |
| PostgreSQL → MUTT | Recommended | CA certificate for verification |
| Vault → MUTT | **REQUIRED** | Public CA or internal CA |
| Client → Ingestor | Optional | Server cert + key (if HTTPS) |
| Client → Web UI | Recommended | Server cert + key (if HTTPS) |

**Certificate Requirements:**
- **CA certificates**: PEM format, placed in `/etc/mutt/certs/`
- **Server certificates** (if needed): PEM format with full chain
- **Private keys**: 600 permissions, owned by mutt:mutt

---

## Installation Steps

### Step 1: Prepare the RHEL Server

#### 1.1 Update System Packages

```bash
sudo dnf update -y
```

**Why**: Ensure latest security patches and bug fixes

**Time**: 5-15 minutes depending on number of updates

#### 1.2 Install System Dependencies

```bash
sudo dnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    openssl \
    openssl-devel \
    libffi-devel \
    curl \
    wget \
    git
```

**Package Purposes:**
- `python3.11` - Python runtime (3.10+ required, 3.11 or 3.12 recommended)
- `python3.11-devel` - Headers for compiling Python packages (needed for psycopg2)
- `gcc` - C compiler (needed for some Python packages)
- `openssl-devel` - SSL/TLS support for Python packages
- `libffi-devel` - Foreign function interface (needed for some crypto packages)
- `curl`/`wget` - For downloading files and health checks
- `git` - For cloning MUTT repository (if using git deployment)

**Verification:**
```bash
python3.11 --version  # Should show 3.11.x
gcc --version         # Should show GCC version
```

#### 1.3 Configure Python Alternatives (Optional but Recommended)

```bash
sudo alternatives --set python3 /usr/bin/python3.11
python3 --version  # Verify it shows 3.11.x
```

**Why**: Ensures `python3` command uses the correct version

---

### Step 2: Create MUTT User and Directory Structure

#### 2.1 Create System User

```bash
sudo useradd --system \
    --shell /bin/false \
    --home-dir /opt/mutt \
    --create-home \
    mutt
```

**Parameters Explained:**
- `--system`: Creates a system account (UID < 1000)
- `--shell /bin/false`: Prevents interactive login (security)
- `--home-dir /opt/mutt`: Sets home directory
- `--create-home`: Creates the home directory automatically

**Verification:**
```bash
id mutt
# Output: uid=XXX(mutt) gid=XXX(mutt) groups=XXX(mutt)
```

#### 2.2 Create Directory Structure

```bash
sudo mkdir -p /opt/mutt/{venv,services,config,logs}
sudo mkdir -p /etc/mutt/{secrets,certs}
sudo mkdir -p /var/log/mutt
sudo mkdir -p /var/run/mutt
```

**Verification:**
```bash
ls -ld /opt/mutt /etc/mutt /var/log/mutt /var/run/mutt
```

#### 2.3 Set Ownership and Permissions

```bash
# Set ownership
sudo chown -R mutt:mutt /opt/mutt
sudo chown -R mutt:mutt /etc/mutt
sudo chown -R mutt:mutt /var/log/mutt
sudo chown -R mutt:mutt /var/run/mutt

# Set directory permissions
sudo chmod 755 /opt/mutt
sudo chmod 700 /etc/mutt          # Secrets directory - restrict access
sudo chmod 700 /etc/mutt/secrets  # Double-restrict secrets
sudo chmod 755 /etc/mutt/certs
sudo chmod 755 /var/log/mutt
sudo chmod 755 /var/run/mutt
```

**Security Note**: `/etc/mutt` contains secrets - only mutt user and root can access

---

### Step 3: Deploy Application Code

#### 3.1 Download MUTT Source Code

**Option A: From Git Repository**
```bash
cd /tmp
git clone https://github.com/yourorg/mutt.git
cd mutt
```

**Option B: From Release Tarball**
```bash
cd /tmp
wget https://github.com/yourorg/mutt/archive/v2.5.tar.gz
tar -xzf v2.5.tar.gz
cd mutt-2.5
```

**Option C: From Local Files**
```bash
# If you already have the files on the server
cd /path/to/mutt/source
```

#### 3.2 Copy Service Files

```bash
sudo cp -r services /opt/mutt/
sudo cp requirements.txt /opt/mutt/
sudo cp config/environment.py /opt/mutt/config/ # If exists
```

**Verification:**
```bash
ls /opt/mutt/services/
# Should show: __init__.py, *_service.py files
```

#### 3.3 Set File Permissions

```bash
sudo chown -R mutt:mutt /opt/mutt/services
sudo chmod 644 /opt/mutt/services/*.py
sudo chmod 644 /opt/mutt/requirements.txt
```

---

### Step 4: Create Python Virtual Environment

#### 4.1 Create Virtual Environment

```bash
sudo -u mutt python3.11 -m venv /opt/mutt/venv
```

**Why use venv?**
- Isolates MUTT dependencies from system Python
- Prevents conflicts with other Python applications
- Allows specific version pinning

**Verification:**
```bash
ls /opt/mutt/venv/bin/
# Should show: python, python3, pip, activate, etc.
```

#### 4.2 Upgrade pip

```bash
sudo -u mutt /opt/mutt/venv/bin/pip install --upgrade pip setuptools wheel
```

**Why**: Ensures latest pip with security fixes and better dependency resolution

#### 4.3 Install Python Dependencies

```bash
sudo -u mutt /opt/mutt/venv/bin/pip install -r /opt/mutt/requirements.txt
```

**Time**: 2-5 minutes depending on network speed

**Common Issues:**
- **psycopg2 build fails**: Install `python3-devel` and `postgresql-devel`
- **SSL errors**: Check network/proxy settings
- **Permission denied**: Ensure running as mutt user with `sudo -u mutt`

**Verification:**
```bash
/opt/mutt/venv/bin/pip list
# Should show: Flask, gunicorn, redis, psycopg2, hvac, etc.
```

---

### Step 5: Configure Environment Variables

#### 5.1 Create Configuration Template

```bash
sudo tee /etc/mutt/mutt.env.template > /dev/null <<'EOF'
# =====================================================================
# MUTT v2.5 Environment Configuration
# =====================================================================
# SECURITY: This file contains secrets - chmod 600 and restrict access
# =====================================================================

# --- Service Ports ---
SERVER_PORT_INGESTOR=8080
METRICS_PORT_INGESTOR=8080

HEALTH_PORT_ALERTER=8081
METRICS_PORT_ALERTER=8082

HEALTH_PORT_MOOG=8084
METRICS_PORT_MOOG=8083

SERVER_PORT_WEBUI=8090

HEALTH_PORT_REMEDIATION=8087
METRICS_PORT_REMEDIATION=8086

# --- Redis Configuration ---
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TLS_ENABLED=false
REDIS_CA_CERT_PATH=/etc/mutt/certs/ca.pem
REDIS_MAX_CONNECTIONS=20
REDIS_SOCKET_KEEPALIVE=true
REDIS_HEALTH_CHECK_INTERVAL=30

# Queue Names
INGEST_QUEUE_NAME=mutt:ingest_queue
ALERT_QUEUE_NAME=mutt:alert_queue
MAX_INGEST_QUEUE_SIZE=1000000

# --- PostgreSQL Configuration ---
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mutt
DB_USER=mutt_app
DB_TLS_ENABLED=false
DB_TLS_CA_CERT_PATH=/etc/mutt/certs/postgres-ca.pem
DB_POOL_MIN_CONN=2
DB_POOL_MAX_CONN=10

# --- HashiCorp Vault Configuration ---
VAULT_ADDR=https://vault.example.com:8200
VAULT_ROLE_ID=your-approle-role-id
VAULT_SECRET_ID_FILE=/etc/mutt/secrets/vault_secret_id
VAULT_MOUNT_PATH=secret
VAULT_SECRET_PATH=mutt/prod
VAULT_TOKEN_RENEW_THRESHOLD=3600

# --- Alerter Service Configuration ---
POD_NAME=mutt-alerter-01
BRPOPLPUSH_TIMEOUT=5
CACHE_RELOAD_INTERVAL=300
JANITOR_INTERVAL=60
HEARTBEAT_INTERVAL=10
HEARTBEAT_EXPIRY=30
POISON_MESSAGE_MAX_RETRIES=3

# Alerter Queue Names
ALERTER_PROCESSING_LIST_PREFIX=mutt:processing:alerter
ALERTER_DLQ_NAME=mutt:dlq:alerter
UNHANDLED_PREFIX=mutt:unhandled
UNHANDLED_THRESHOLD=100
UNHANDLED_EXPIRY_SECONDS=86400
UNHANDLED_DEFAULT_TEAM=NETO

# --- Moog Forwarder Configuration ---
MOOG_WEBHOOK_URL=https://moog.example.com/events/webhook
MOOG_TIMEOUT=10
MOOG_PROCESSING_LIST_PREFIX=mutt:processing:moog
MOOG_DLQ_NAME=mutt:dlq:moog

# Rate Limiting
MOOG_RATE_LIMIT=50
MOOG_RATE_PERIOD=1
MOOG_RATE_LIMIT_KEY=mutt:rate_limit:moog

# Retry Configuration
MOOG_MAX_RETRIES=5
MOOG_RETRY_BASE_DELAY=1
MOOG_RETRY_MAX_DELAY=60

# Circuit Breaker
MOOG_CB_FAILURE_THRESHOLD=5
MOOG_CB_OPEN_SECONDS=60
MOOG_CB_KEY_PREFIX=mutt:cb:moog

# --- Remediation Service Configuration ---
REMEDIATION_ENABLED=true
REMEDIATION_INTERVAL=300
REMEDIATION_BATCH_SIZE=10
MAX_POISON_RETRIES=3
MOOG_HEALTH_CHECK_ENABLED=true
MOOG_HEALTH_TIMEOUT=5

# --- Dynamic Configuration ---
DYNAMIC_CONFIG_ENABLED=true

# --- Observability ---
LOG_LEVEL=INFO
MUTT_TESTING=false

# --- Secrets (from Vault or override here for testing) ---
# These should normally come from Vault, but can be set here for testing
# REDIS_PASS=changeme
# DB_PASS=changeme
# INGEST_API_KEY=changeme
# WEBUI_API_KEY=changeme
# MOOG_API_KEY=changeme
EOF
```

#### 5.2 Create Production Configuration

```bash
sudo cp /etc/mutt/mutt.env.template /etc/mutt/mutt.env
```

#### 5.3 Edit Configuration

```bash
sudo vi /etc/mutt/mutt.env
```

**Required Changes:**
1. Update `REDIS_HOST` and `REDIS_PORT` with your Redis server
2. Update `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` with your PostgreSQL details
3. Update `VAULT_ADDR` with your Vault server
4. Update `VAULT_ROLE_ID` with your AppRole Role ID
5. Update `MOOG_WEBHOOK_URL` with your Moogsoft endpoint
6. Set unique `POD_NAME` for each server (e.g., mutt-server-01)

**Optional Changes:**
- Enable TLS by setting `REDIS_TLS_ENABLED=true` and providing certificates
- Adjust queue sizes, timeouts, retry settings based on your needs
- Set logging level (DEBUG for troubleshooting, INFO for production)

#### 5.4 Secure Configuration File

```bash
sudo chmod 600 /etc/mutt/mutt.env
sudo chown mutt:mutt /etc/mutt/mutt.env
```

**Verification:**
```bash
ls -l /etc/mutt/mutt.env
# Should show: -rw------- 1 mutt mutt
```

---

### Step 6: Configure Vault Secret ID

#### 6.1 Obtain Vault Secret ID

Contact your Vault administrator or use Vault CLI:

```bash
vault write -f auth/approle/role/mutt-app/secret-id
# Output will contain: secret_id
```

#### 6.2 Store Secret ID

```bash
echo "YOUR_SECRET_ID_HERE" | sudo tee /etc/mutt/secrets/vault_secret_id
sudo chmod 600 /etc/mutt/secrets/vault_secret_id
sudo chown mutt:mutt /etc/mutt/secrets/vault_secret_id
```

**Security Warning**: This file contains authentication credentials. Protect it!

**Verification:**
```bash
ls -l /etc/mutt/secrets/vault_secret_id
# Should show: -rw------- 1 mutt mutt

sudo cat /etc/mutt/secrets/vault_secret_id
# Should show your secret ID (verify it's not the placeholder)
```

---

### Step 7: Configure TLS Certificates (If Using TLS)

#### 7.1 Copy Certificates

```bash
# Copy CA certificate for Redis
sudo cp /path/to/your/redis-ca.pem /etc/mutt/certs/ca.pem

# Copy PostgreSQL CA (if different)
sudo cp /path/to/your/postgres-ca.pem /etc/mutt/certs/postgres-ca.pem

# Set permissions
sudo chmod 644 /etc/mutt/certs/*.pem
sudo chown mutt:mutt /etc/mutt/certs/*.pem
```

#### 7.2 Verify Certificate Format

```bash
openssl x509 -in /etc/mutt/certs/ca.pem -text -noout
# Should display certificate details without errors
```

#### 7.3 Update Environment Configuration

```bash
sudo vi /etc/mutt/mutt.env

# Set these values:
REDIS_TLS_ENABLED=true
DB_TLS_ENABLED=true
```

---

### Step 8: Create systemd Service Files

Create service files for all MUTT services. I'll show the complete files here:

#### 8.1 Ingestor Service

```bash
sudo tee /etc/systemd/system/mutt-ingestor.service > /dev/null <<'EOF'
[Unit]
Description=MUTT Ingestor Service (v2.5)
Documentation=https://github.com/yourorg/mutt
After=network-online.target redis.service
Wants=network-online.target
Requires=redis.service

[Service]
Type=notify
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/etc/mutt/mutt.env

# Use Gunicorn for production HTTP serving
ExecStart=/opt/mutt/venv/bin/gunicorn \
    --bind 0.0.0.0:${SERVER_PORT_INGESTOR} \
    --workers 4 \
    --timeout 30 \
    --graceful-timeout 10 \
    --max-requests 10000 \
    --max-requests-jitter 1000 \
    --access-logfile /var/log/mutt/ingestor-access.log \
    --error-logfile /var/log/mutt/ingestor-error.log \
    --log-level info \
    "services.ingestor_service:create_app()"

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/mutt /var/run/mutt

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF
```

**Service Configuration Explained:**
- `Type=notify`: Gunicorn will notify systemd when ready
- `--workers 4`: Run 4 worker processes (adjust based on CPU cores)
- `--timeout 30`: Request timeout (30 seconds)
- `--max-requests 10000`: Restart worker after 10k requests (prevents memory leaks)
- `NoNewPrivileges`: Security - prevents privilege escalation
- `ProtectSystem=strict`: Makes /usr, /boot, /etc read-only
- `Restart=always`: Auto-restart on failure

#### 8.2 Alerter Service

```bash
sudo tee /etc/systemd/system/mutt-alerter.service > /dev/null <<'EOF'
[Unit]
Description=MUTT Alerter Service (v2.5)
Documentation=https://github.com/yourorg/mutt
After=network-online.target redis.service postgresql.service
Wants=network-online.target
Requires=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/etc/mutt/mutt.env

ExecStart=/opt/mutt/venv/bin/python3 -m services.alerter_service

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/mutt /var/run/mutt

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Signal handling
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
```

#### 8.3 Moog Forwarder Service

```bash
sudo tee /etc/systemd/system/mutt-moog-forwarder.service > /dev/null <<'EOF'
[Unit]
Description=MUTT Moog Forwarder Service (v2.5)
Documentation=https://github.com/yourorg/mutt
After=network-online.target redis.service
Wants=network-online.target
Requires=redis.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/etc/mutt/mutt.env

ExecStart=/opt/mutt/venv/bin/python3 -m services.moog_forwarder_service

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/mutt /var/run/mutt

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Signal handling
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
```

#### 8.4 Web UI Service

```bash
sudo tee /etc/systemd/system/mutt-webui.service > /dev/null <<'EOF'
[Unit]
Description=MUTT Web UI Service (v2.5)
Documentation=https://github.com/yourorg/mutt
After=network-online.target redis.service postgresql.service
Wants=network-online.target
Requires=redis.service postgresql.service

[Service]
Type=notify
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/etc/mutt/mutt.env

# Use Gunicorn for production HTTP serving
ExecStart=/opt/mutt/venv/bin/gunicorn \
    --bind 0.0.0.0:${SERVER_PORT_WEBUI} \
    --workers 2 \
    --timeout 60 \
    --graceful-timeout 10 \
    --max-requests 5000 \
    --access-logfile /var/log/mutt/webui-access.log \
    --error-logfile /var/log/mutt/webui-error.log \
    --log-level info \
    "services.web_ui_service:create_app()"

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/mutt /var/run/mutt

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF
```

#### 8.5 Remediation Service

```bash
sudo tee /etc/systemd/system/mutt-remediation.service > /dev/null <<'EOF'
[Unit]
Description=MUTT Remediation Service (v2.5)
Documentation=https://github.com/yourorg/mutt
After=network-online.target redis.service
Wants=network-online.target
Requires=redis.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/etc/mutt/mutt.env

ExecStart=/opt/mutt/venv/bin/python3 -m services.remediation_service

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/mutt /var/run/mutt

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Signal handling
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
```

---

### Step 9: Configure Firewall

#### 9.1 Configure firewalld (RHEL 8/9 Default)

```bash
# Open MUTT service ports
sudo firewall-cmd --permanent --add-port=8080-8090/tcp

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
# Should show: 8080-8090/tcp
```

#### 9.2 Alternative: iptables (If not using firewalld)

```bash
# Add rule
sudo iptables -A INPUT -p tcp --match multiport --dports 8080:8090 -j ACCEPT

# Save rules
sudo service iptables save

# Verify
sudo iptables -L INPUT -n --line-numbers | grep 808
```

---

### Step 10: Configure Log Rotation

```bash
sudo tee /etc/logrotate.d/mutt > /dev/null <<'EOF'
/var/log/mutt/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 mutt mutt
    sharedscripts
    postrotate
        /bin/systemctl reload mutt-ingestor.service > /dev/null 2>&1 || true
        /bin/systemctl reload mutt-webui.service > /dev/null 2>&1 || true
    endscript
}
EOF
```

**Configuration Explained:**
- `daily`: Rotate logs daily
- `rotate 30`: Keep 30 days of logs
- `compress`: Compress rotated logs with gzip
- `delaycompress`: Don't compress yesterday's log (in case still being read)
- `create 0640 mutt mutt`: Create new log file with correct ownership/permissions
- `postrotate`: Reload Gunicorn services to reopen log files

---

### Step 11: Enable and Start Services

#### 11.1 Reload systemd

```bash
sudo systemctl daemon-reload
```

**Why**: Tell systemd to read the new service files

#### 11.2 Enable Services (Auto-start on Boot)

```bash
sudo systemctl enable mutt-ingestor.service
sudo systemctl enable mutt-alerter.service
sudo systemctl enable mutt-moog-forwarder.service
sudo systemctl enable mutt-webui.service
sudo systemctl enable mutt-remediation.service
```

**Verification:**
```bash
systemctl is-enabled mutt-*.service
# All should show: enabled
```

#### 11.3 Start Services

```bash
sudo systemctl start mutt-ingestor.service
sudo systemctl start mutt-alerter.service
sudo systemctl start mutt-moog-forwarder.service
sudo systemctl start mutt-webui.service
sudo systemctl start mutt-remediation.service
```

**Wait 5-10 seconds for services to start**

#### 11.4 Check Service Status

```bash
sudo systemctl status mutt-*.service
```

**Expected Output:**
```
● mutt-ingestor.service - MUTT Ingestor Service (v2.5)
   Loaded: loaded (/etc/systemd/system/mutt-ingestor.service; enabled)
   Active: active (running) since ...
   ...
```

**All services should show `Active: active (running)`**

---

## Post-Installation Verification

### Health Checks

Test each service's health endpoint:

```bash
# Ingestor
curl -f http://localhost:8080/health
# Expected: {"status":"healthy","redis":"connected","vault":"connected"}

# Alerter
curl -f http://localhost:8081/health
# Expected: {"status":"healthy","redis":"connected","database":"connected"}

# Moog Forwarder
curl -f http://localhost:8084/health
# Expected: {"status":"healthy","redis":"connected"}

# Web UI
curl -f http://localhost:8090/health
# Expected: {"status":"healthy","redis":"connected","database":"connected"}

# Remediation
curl -f http://localhost:8087/health
# Expected: {"status":"healthy","redis":"connected"}
```

**If any health check fails, see [Troubleshooting](#common-installation-issues)**

### Metrics Check

Verify Prometheus metrics are being exposed:

```bash
curl -s http://localhost:8080/metrics | head -20
# Should show Prometheus metrics format
```

### Log Verification

Check that services are logging:

```bash
# View ingestor logs
sudo journalctl -u mutt-ingestor.service -n 50

# View alerter logs
sudo journalctl -u mutt-alerter.service -n 50

# Check for errors
sudo journalctl -u mutt-*.service --since "5 minutes ago" | grep -i error
```

### Functional Test

Test event ingestion:

```bash
curl -X POST http://localhost:8080/api/v2/ingest \
  -H "X-API-KEY: YOUR_INGEST_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "hostname": "test-server",
    "message": "Installation test event",
    "syslog_severity": 6
  }'
```

**Expected Response:**
```json
{"status":"accepted","queued":true}
```

### Queue Verification

Check Redis queues:

```bash
# Check ingest queue depth
redis-cli LLEN mutt:ingest_queue

# Check alert queue depth
redis-cli LLEN mutt:alert_queue
```

---

## Common Installation Issues

### Issue: Python Package Installation Fails

**Symptoms:**
```
error: command 'gcc' failed with exit status 1
```

**Solution:**
```bash
sudo dnf install -y python3-devel gcc
sudo -u mutt /opt/mutt/venv/bin/pip install -r /opt/mutt/requirements.txt
```

---

### Issue: Service Fails to Start - Vault Connection

**Symptoms:**
```
vault.exceptions.InvalidRequest: invalid role ID or secret ID
```

**Solutions:**
1. Verify Vault Role ID in `/etc/mutt/mutt.env`
2. Verify Secret ID in `/etc/mutt/secrets/vault_secret_id`
3. Test Vault authentication:
```bash
vault write auth/approle/login \
  role_id="YOUR_ROLE_ID" \
  secret_id="YOUR_SECRET_ID"
```

---

### Issue: Redis Connection Refused

**Symptoms:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**Solutions:**
1. Verify Redis is running: `sudo systemctl status redis`
2. Check Redis listens on correct port: `sudo ss -tlnp | grep 6379`
3. Verify `REDIS_HOST` and `REDIS_PORT` in `/etc/mutt/mutt.env`
4. Test connection: `redis-cli -h $REDIS_HOST -p $REDIS_PORT PING`

---

### Issue: PostgreSQL Connection Fails

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**
1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check PostgreSQL accepts connections: `sudo ss -tlnp | grep 5432`
3. Verify database exists:
```bash
psql -h $DB_HOST -U postgres -l | grep mutt
```
4. Test connection:
```bash
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;"
```

---

### Issue: Permission Denied Errors

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/var/log/mutt/...'
```

**Solution:**
```bash
sudo chown -R mutt:mutt /opt/mutt /etc/mutt /var/log/mutt /var/run/mutt
sudo chmod 755 /var/log/mutt
```

---

### Issue: Port Already in Use

**Symptoms:**
```
OSError: [Errno 98] Address already in use
```

**Solutions:**
1. Find what's using the port:
```bash
sudo ss -tlnp | grep :8080
```
2. Stop conflicting service or change MUTT port in `/etc/mutt/mutt.env`

---

### Issue: SELinux Blocks Service

**Symptoms:**
Service fails to bind to port, SELinux audit logs show denials

**Solutions:**

**Option 1: Allow specific ports (Recommended)**
```bash
sudo semanage port -a -t http_port_t -p tcp 8080
sudo semanage port -a -t http_port_t -p tcp 8081
sudo semanage port -a -t http_port_t -p tcp 8082
# ... repeat for all ports
```

**Option 2: Create custom SELinux policy**
```bash
sudo grep mutt /var/log/audit/audit.log | audit2allow -M mutt_policy
sudo semodule -i mutt_policy.pp
```

**Option 3: Disable SELinux (NOT recommended for production)**
```bash
sudo setenforce 0  # Temporary
sudo vi /etc/selinux/config  # Set SELINUX=permissive for permanent
```

---

## Automated Deployment

For automated deployment, use the provided script:

```bash
# Download deployment script
curl -O https://raw.githubusercontent.com/yourorg/mutt/main/scripts/deploy_mutt_v2.3.sh

# Make executable
chmod +x deploy_mutt_v2.3.sh

# Run as root
sudo ./deploy_mutt_v2.3.sh
```

**Script Features:**
- Prerequisites validation
- Interactive configuration
- Automatic service setup
- Health verification
- Rollback on failure

**Script Location:** `scripts/deploy_mutt_v2.3.sh` in the MUTT repository

---

## Appendix

### A. Environment Variable Reference

See [Configuration Guide](CONFIGURATION_GUIDE.md) for complete reference.

### B. systemd Service Commands

```bash
# Start a service
sudo systemctl start mutt-ingestor.service

# Stop a service
sudo systemctl stop mutt-ingestor.service

# Restart a service
sudo systemctl restart mutt-ingestor.service

# Reload configuration (SIGHUP)
sudo systemctl reload mutt-ingestor.service

# Check status
sudo systemctl status mutt-ingestor.service

# View logs
sudo journalctl -u mutt-ingestor.service -f

# Enable auto-start
sudo systemctl enable mutt-ingestor.service

# Disable auto-start
sudo systemctl disable mutt-ingestor.service
```

### C. Directory Quick Reference

| Path | Purpose | Owner | Permissions |
|------|---------|-------|-------------|
| `/opt/mutt/` | Application root | mutt:mutt | 755 |
| `/opt/mutt/venv/` | Python virtual environment | mutt:mutt | 755 |
| `/opt/mutt/services/` | Service modules | mutt:mutt | 755 (dir), 644 (files) |
| `/etc/mutt/` | Configuration root | mutt:mutt | 700 |
| `/etc/mutt/mutt.env` | Environment variables | mutt:mutt | 600 |
| `/etc/mutt/secrets/` | Vault Secret IDs | mutt:mutt | 700 |
| `/etc/mutt/certs/` | TLS certificates | mutt:mutt | 755 |
| `/var/log/mutt/` | Log files | mutt:mutt | 755 (dir), 640 (files) |
| `/var/run/mutt/` | Runtime files | mutt:mutt | 755 |

### D. Port Reference

| Service | Port | Type | Purpose |
|---------|------|------|---------|
| Ingestor | 8080 | HTTP | Event ingestion API, health, metrics |
| Alerter | 8081 | HTTP | Health check |
| Alerter | 8082 | HTTP | Prometheus metrics |
| Moog Forwarder | 8083 | HTTP | Prometheus metrics |
| Moog Forwarder | 8084 | HTTP | Health check |
| Remediation | 8086 | HTTP | Prometheus metrics |
| Remediation | 8087 | HTTP | Health check |
| Web UI | 8090 | HTTP | Dashboard and API |

### E. Log File Locations

| Log File | Purpose | Rotation |
|----------|---------|----------|
| `/var/log/mutt/ingestor-access.log` | HTTP access logs | Daily, 30 days |
| `/var/log/mutt/ingestor-error.log` | Gunicorn errors | Daily, 30 days |
| `/var/log/mutt/webui-access.log` | Web UI access logs | Daily, 30 days |
| `/var/log/mutt/webui-error.log` | Web UI errors | Daily, 30 days |
| `journalctl -u mutt-*.service` | Service application logs | systemd journal |

### F. Next Steps

After successful installation:
1. Read [Service Operations Guide](SERVICE_OPERATIONS.md)
2. Set up monitoring with [Monitoring Setup Guide](MONITORING_SETUP.md)
3. Configure backups with [Backup & Recovery Guide](BACKUP_RECOVERY.md)
4. Review [Security Operations Guide](SECURITY_OPERATIONS.md)
5. Add to on-call runbook: [Incident Response](INCIDENT_RESPONSE.md)

---

**Installation Complete!**

For operational procedures, troubleshooting, and day-to-day management, see the [Service Operations Guide](SERVICE_OPERATIONS.md).
