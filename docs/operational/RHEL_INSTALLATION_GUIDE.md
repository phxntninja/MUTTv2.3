# MUTT Standalone Server Installation Guide (RHEL 8/9)

**Version:** 1.0
**Last Updated:** 2025-11-11
**Status:** Complete
**Audience:** Operators, SREs
**Prerequisites:** `docs/architecture/DEPLOYMENT_ARCHITECTURE.md`

---

> **Instructions for AI Agents:**
>
> *   **Gemini:** This skeleton has been created by Gemini to provide the architectural structure.
> *   **Codex:** Your task is to fill in all placeholders marked with `[CODEX: ...]`. Replace the placeholder and its description with the exact, complete command or configuration file content.
> *   **Claude:** Your task is to write the narrative text in each section, explaining the steps to the user. You will also add operational checks and verification steps after each major step. Finally, you will perform a full review to ensure the document is coherent and easy to follow.

---

## 1. Introduction

This document provides comprehensive, step-by-step instructions for deploying the MUTT v2.5 (Monitoring and Unified Threat Tracking) application on a standalone Red Hat Enterprise Linux (RHEL) 8 or 9 server. MUTT is a distributed event processing system that ingests syslog and SNMP trap data, applies intelligent routing rules, and forwards alerts to downstream monitoring platforms like Moogsoft.

This guide assumes you are starting with a fresh RHEL 8 or 9 server and have `sudo` privileges. It also assumes that the external dependencies (PostgreSQL, Redis, Vault) are already set up and network-accessible. By following this guide, you will have a fully operational MUTT installation with all four core services running under systemd supervision.

---

## 2. System Preparation

### 2.1. Update System Packages

Before installing any new software, ensure your RHEL system has the latest security patches and package updates. This command refreshes the package metadata and upgrades all installed packages to their latest versions. The DNF package manager (Dandified YUM) is the default package manager for RHEL 8 and 9.

```bash
sudo dnf -y update
```

**Verification:** The command should complete without errors. You may be prompted to reboot if kernel updates were applied.

### 2.2. Install Dependencies

MUTT requires Python 3, along with tools for building Python packages and PostgreSQL client libraries. This step installs all necessary system dependencies including:
- **python3**: Python runtime (RHEL 8/9 includes Python 3.6+ by default)
- **python3-pip** and **python3-virtualenv**: Package management and virtual environment support
- **gcc** and **gcc-c++**: C/C++ compilers needed for building Python packages with native extensions
- **libpq-devel**: PostgreSQL development headers for psycopg2
- **rsyslog**: System logging daemon (usually pre-installed)
- **curl**: For health checks and API testing
- **firewalld**: RHEL's default firewall management tool

```bash
sudo dnf -y install python3 python3-pip python3-virtualenv gcc gcc-c++ libpq-devel rsyslog curl firewalld
```

**Verification:** Run `python3 --version` to confirm Python 3 is installed and accessible.

### 2.3. Create Service User

For security best practices, MUTT services should run under a dedicated, non-privileged system account named `mutt`. This user will have no login shell (`/sbin/nologin`) and limited privileges, reducing the attack surface if a service is compromised. The `|| true` ensures the command succeeds even if the user already exists.

```bash
sudo groupadd --system mutt || true && sudo useradd --system --home-dir /opt/mutt --create-home --shell /sbin/nologin --gid mutt mutt || true
```

**Verification:** Confirm the user was created by running `id mutt`. You should see the user and group IDs.

---

## 3. Directory and Code Setup

### 3.1. Create Directory Structure

MUTT uses a structured directory layout following Linux Filesystem Hierarchy Standard (FHS) conventions:
- **/opt/mutt/services**: Application code and Python virtual environment
- **/etc/mutt/certs**: TLS certificates for Redis and PostgreSQL connections
- **/etc/mutt/secrets**: Sensitive credentials (Vault Secret ID)
- **/var/log/mutt**: Application logs (if file-based logging is configured)

```bash
sudo mkdir -p /opt/mutt/services /etc/mutt/certs /etc/mutt/secrets /var/log/mutt
```

### 3.2. Set Permissions

Assign ownership of all MUTT directories to the `mutt` service user. This ensures the services have the necessary read/write access while preventing unauthorized access by other system users.

```bash
sudo chown -R mutt:mutt /opt/mutt /etc/mutt /var/log/mutt
```

**Verification:** Run `ls -ld /opt/mutt /etc/mutt /var/log/mutt` to confirm ownership is set to `mutt:mutt`.

### 3.3. Deploy Application Code

Copy the MUTT application source code to `/opt/mutt/services`. You can transfer the code using `scp`, `rsync`, or clone from a git repository. Ensure that all Python service files (`ingestor_service.py`, `alerter_service.py`, `moog_forwarder_service.py`, `web_ui_service.py`) and the `requirements.txt` file are present.

```bash
# Example using scp from your local machine:
# scp -r /path/to/mutt/source/* user@rhel-server:/tmp/mutt-code/
# Then on the server:
sudo cp -r /tmp/mutt-code/* /opt/mutt/services/
sudo chown -R mutt:mutt /opt/mutt/services
```

**Verification:** Confirm the service files exist by running `ls -la /opt/mutt/services/*.py`.

### 3.4. Create Python Virtual Environment

A Python virtual environment isolates MUTT's dependencies from system-wide Python packages, preventing version conflicts and ensuring reproducibility. This command creates the virtual environment and upgrades the package management tools (`pip`, `wheel`, `setuptools`) to their latest versions.

```bash
sudo -u mutt -H /usr/bin/python3 -m venv /opt/mutt/venv && sudo -u mutt -H /opt/mutt/venv/bin/pip install --upgrade pip wheel setuptools
```

**Verification:** Check that the virtual environment was created: `ls -la /opt/mutt/venv/bin/python`.

### 3.5. Install Python Dependencies

Install all required Python packages specified in the `requirements.txt` file into the virtual environment. This includes libraries for web frameworks (Flask), async operations (asyncio), database connectivity (psycopg2), Redis clients, and Vault integration. The `--no-cache-dir` flag reduces disk usage by not caching downloaded packages.

```bash
sudo -u mutt -H bash -lc 'cd /opt/mutt && /opt/mutt/venv/bin/pip install --no-cache-dir -r requirements.txt'
```

**Verification:** Run `/opt/mutt/venv/bin/pip list` to see all installed packages. Key packages should include `flask`, `redis`, `psycopg2-binary`, and `hvac`.

---

## 4. Configuration

### 4.1. Configure Environment File

All MUTT services are configured through a single centralized environment file located at `/etc/mutt/mutt.env`. This file contains connection parameters for external dependencies (Redis, PostgreSQL, Vault), service port assignments, and operational settings.

Create the file `/etc/mutt/mutt.env` using your preferred text editor (vi, nano, etc.) and paste the template below. **Important:** Replace all placeholder values (e.g., `your-redis-host`, `your-postgres-host`, `your-vault-url`) with the actual values for your environment before starting the services.

```
# ==========================
# MUTT Global Configuration
# ==========================

# Log level for all services: DEBUG, INFO, WARN, ERROR
LOG_LEVEL=INFO

# Redis (shared by services)
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_TLS_ENABLED=true
REDIS_CA_CERT_PATH=/etc/mutt/certs/redis_ca.crt
REDIS_MAX_CONNECTIONS=20

# PostgreSQL (used by Alerter and Web UI)
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=mutt_db
DB_USER=mutt_user
DB_TLS_ENABLED=true
DB_TLS_CA_CERT_PATH=/etc/mutt/certs/postgres_ca.crt
DB_POOL_MIN_CONN=2
DB_POOL_MAX_CONN=10

# Vault (used by all services)
VAULT_ADDR=https://your-vault-url:8200
VAULT_ROLE_ID=your-approle-role-id
VAULT_SECRET_ID_FILE=/etc/mutt/secrets/vault_secret_id
VAULT_SECRETS_PATH=secret/mutt
VAULT_TOKEN_RENEW_THRESHOLD=3600
VAULT_RENEW_CHECK_INTERVAL=300

# Metrics shared prefix (Redis keys consumed by Web UI)
METRICS_PREFIX=mutt:metrics

# ==========================
# Ingestor Service
# ==========================
SERVER_PORT_INGESTOR=8080
# Input validation
REQUIRED_FIELDS=hostname,message,timestamp
# Rate limiting
RATE_LIMIT_ENABLED=true
INGEST_MAX_RATE=1000
INGEST_RATE_WINDOW=60
# Redis queue
INGEST_QUEUE_NAME=mutt:ingest_queue
MAX_INGEST_QUEUE_SIZE=1000000

# ==========================
# Alerter Service
# ==========================
METRICS_PORT_ALERTER=8081
HEALTH_PORT_ALERTER=8082
# Redis queues and housekeeping
ALERTER_PROCESSING_LIST_PREFIX=mutt:processing:alerter
ALERTER_HEARTBEAT_PREFIX=mutt:heartbeat:alerter
ALERTER_HEARTBEAT_INTERVAL=10
ALERTER_JANITOR_TIMEOUT=30
ALERTER_DLQ_NAME=mutt:dlq:alerter
ALERTER_MAX_RETRIES=3
BRPOPLPUSH_TIMEOUT=5
ALERT_QUEUE_NAME=mutt:alert_queue
# Dynamic config toggle
DYNAMIC_CONFIG_ENABLED=false
# Unhandled event aggregation
UNHANDLED_PREFIX=mutt:unhandled
UNHANDLED_THRESHOLD=100
UNHANDLED_EXPIRY_SECONDS=86400
UNHANDLED_DEFAULT_TEAM=NETO

# ==========================
# Moog Forwarder Service
# ==========================
METRICS_PORT_MOOG=8083
HEALTH_PORT_MOOG=8084

# ==========================
# Web UI Service
# ==========================
SERVER_PORT_WEBUI=8090
# Metrics cache window and audit settings
METRICS_CACHE_TTL=5
AUDIT_LOG_PAGE_SIZE=50
# Prometheus (optional, used by Web UI when enabled)
PROMETHEUS_URL=http://localhost:9090
```

### 4.2. Set `mutt.env` Permissions

The `mutt.env` file contains sensitive connection strings and configuration parameters that should not be readable by other system users. Set strict permissions (600) to ensure only the `mutt` user can read this file.

```bash
sudo chown mutt:mutt /etc/mutt/mutt.env && sudo chmod 600 /etc/mutt/mutt.env
```

**Verification:** Run `ls -l /etc/mutt/mutt.env` and confirm permissions show `-rw-------` with owner `mutt:mutt`.

### 4.3. Configure Vault Secret ID

MUTT uses HashiCorp Vault's AppRole authentication method to securely retrieve secrets at runtime. The Vault Secret ID is stored in a separate file outside of the environment file for enhanced security. This credential should be obtained from your Vault administrator.

```bash
sudo touch /etc/mutt/secrets/vault_secret_id
sudo chown mutt:mutt /etc/mutt/secrets/vault_secret_id
sudo chmod 600 /etc/mutt/secrets/vault_secret_id
# Now paste your Secret ID into the file:
sudo sh -c 'echo "REPLACE_WITH_YOUR_VAULT_SECRET_ID" > /etc/mutt/secrets/vault_secret_id'
```

**Verification:** Confirm the file was created and has correct permissions: `ls -l /etc/mutt/secrets/vault_secret_id` (should show `-rw-------`).

### 4.4. Configure rsyslog

The rsyslog daemon must be configured to forward all system log messages to the MUTT Ingestor service via HTTP. This integration enables MUTT to process and route local system logs alongside logs from other sources. The `omhttp` module formats messages as JSON and sends them to the Ingestor's `/ingest` endpoint.

Create `/etc/rsyslog.d/99-mutt.conf` with the following content. **Important:** After creating the file, you must replace `REPLACE_WITH_INGESTOR_API_KEY` with the actual API key value retrieved from Vault (stored at the path `secret/mutt` under the key `ingestor_api_key`).

```
module(load="omhttp")

# Template to format syslog as JSON expected by MUTT Ingestor
template(name="MUTTJsonFormat" type="string"
         string="{\"hostname\":\"%HOSTNAME%\",\"message\":\"%msg%\",\"timestamp\":\"%timereported:::date-rfc3339%\"}")

# Forward all messages to MUTT Ingestor over HTTP
action(
  type="omhttp"
  server="127.0.0.1"
  port="8080"
  restpath="/ingest"
  usehttps="off"
  header="X-API-KEY: REPLACE_WITH_INGESTOR_API_KEY"
  template="MUTTJsonFormat"
)
```

After creating the configuration file and updating the API key, apply the changes by restarting rsyslog:

```bash
sudo systemctl restart rsyslog
```

**How to retrieve the Ingestor API key from Vault:**
```bash
# Using the Vault CLI (if installed):
vault kv get -field=ingestor_api_key secret/mutt

# Or via curl (replace VAULT_TOKEN with your token):
curl -H "X-Vault-Token: $VAULT_TOKEN" https://your-vault-url:8200/v1/secret/data/mutt | jq -r '.data.data.ingestor_api_key'
```

**Verification:** Check rsyslog status with `sudo systemctl status rsyslog` to ensure it restarted without errors. Test the integration by generating a test log message: `logger "MUTT test message"` and checking if it appears in the MUTT Ingestor logs.

---

### 4.5. Enable rsyslog UDP/TCP Input (optional)

To receive syslog locally and forward it to MUTT, enable rsyslog inputs.

```bash
sudo cp docs/operational/RSYSLOG_UDP_INPUT.conf /etc/rsyslog.d/10-udp-input.conf
# Optional TCP input
sudo cp docs/operational/RSYSLOG_TCP_INPUT.conf /etc/rsyslog.d/11-tcp-input.conf
sudo systemctl restart rsyslog
```

For HTTPS forwarding and custom CA, see `docs/operational/RSYSLOG_FORWARD_TO_MUTT_TLS.conf`.

### 4.6. SNMP Trap Forwarding (snmptrapd)

Install snmptrapd and Net-SNMP tools:

```bash
sudo dnf -y install net-snmp net-snmp-utils net-snmp-agent-libs
```

Option A: Log traps to syslog and forward via rsyslog (simple)

```bash
sudo bash -c 'cat > /etc/snmp/snmptrapd.conf <<EOF
disableAuthorization no
authCommunity log,execute,net public
EOF'
sudo systemctl enable --now snmptrapd
```

Option B: Direct HTTPS POST to MUTT (traphandle)

```bash
sudo install -d -o mutt -g mutt /opt/mutt/scripts
sudo install -m 0755 scripts/snmptrap_to_mutt.sh /opt/mutt/scripts/snmptrap_to_mutt.sh
sudo mkdir -p /etc/systemd/system/snmptrapd.service.d
sudo bash -c 'cat > /etc/systemd/system/snmptrapd.service.d/override.conf <<EOF
[Service]
Environment=MUTT_INGEST_URL=https://your-ingestor-host:8443/ingest
Environment=MUTT_INGEST_API_KEY=REPLACE_WITH_INGESTOR_API_KEY
Environment=MUTT_CACERT=/etc/mutt/certs/mutt_ingestor_ca.crt
EOF'
sudo systemctl daemon-reload
echo "traphandle default /opt/mutt/scripts/snmptrap_to_mutt.sh" | sudo tee -a /etc/snmp/snmptrapd.conf
sudo systemctl restart snmptrapd
```

See `docs/operational/SNMPTRAPD_OPTIONS.md` for advanced options (SNMPv3, custom communities).

---

### 4.7. Configure HTTPS Reverse Proxy (NGINX)

MUTT should receive data via HTTPS. Deploy an NGINX reverse proxy to terminate TLS on port 8443 and proxy to the local Ingestor on 127.0.0.1:8080.

```
sudo dnf -y install nginx
sudo systemctl enable --now nginx
sudo install -d /etc/ssl/mutt
# Place your cert and key at /etc/ssl/mutt/ingestor.crt and /etc/ssl/mutt/ingestor.key
sudo bash -c 'cat > /etc/nginx/conf.d/mutt_ingestor.conf <<EOF
server {
    listen 8443 ssl;
    server_name _;
    ssl_certificate     /etc/ssl/mutt/ingestor.crt;
    ssl_certificate_key /etc/ssl/mutt/ingestor.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    location /ingest { proxy_pass http://127.0.0.1:8080/ingest; proxy_set_header Host $host; }
    location /health { proxy_pass http://127.0.0.1:8080/health; }
}
EOF'
sudo nginx -t && sudo systemctl reload nginx
```

Open the firewall for 8443:

```
sudo firewall-cmd --permanent --add-port=8443/tcp
sudo firewall-cmd --reload
```

See `docs/operational/INGESTOR_TLS_REVERSE_PROXY.md` for more options (HAProxy, Web UI HTTPS on 443).

---

## 5. Service Installation (systemd)

RHEL uses systemd as its init system and service manager. Each MUTT service (Ingestor, Alerter, Moog Forwarder, and Web UI) will be configured as a systemd unit, enabling automatic startup on boot, automatic restart on failure, and centralized log management through journald. The following sections guide you through creating the service unit files.

### 5.1. Create `mutt-ingestor.service`

Create `/etc/systemd/system/mutt-ingestor.service` with:

```
[Unit]
Description=MUTT Ingestor Service
After=network.target rsyslog.service

[Service]
Type=simple
User=mutt
Group=mutt
EnvironmentFile=-/etc/mutt/mutt.env
WorkingDirectory=/opt/mutt/services
ExecStart=/opt/mutt/venv/bin/python /opt/mutt/services/ingestor_service.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 5.2. Create `mutt-alerter.service`

Create `/etc/systemd/system/mutt-alerter.service` with:

```
[Unit]
Description=MUTT Alerter Service
After=network.target

[Service]
Type=simple
User=mutt
Group=mutt
EnvironmentFile=-/etc/mutt/mutt.env
WorkingDirectory=/opt/mutt/services
ExecStart=/opt/mutt/venv/bin/python /opt/mutt/services/alerter_service.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 5.3. Create `mutt-moog-forwarder.service`

Create `/etc/systemd/system/mutt-moog-forwarder.service` with:

```
[Unit]
Description=MUTT Moog Forwarder Service
After=network.target

[Service]
Type=simple
User=mutt
Group=mutt
EnvironmentFile=-/etc/mutt/mutt.env
WorkingDirectory=/opt/mutt/services
ExecStart=/opt/mutt/venv/bin/python /opt/mutt/services/moog_forwarder_service.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 5.4. Create `mutt-webui.service`

Create `/etc/systemd/system/mutt-webui.service` with:

```
[Unit]
Description=MUTT Web UI Service
After=network.target

[Service]
Type=simple
User=mutt
Group=mutt
EnvironmentFile=-/etc/mutt/mutt.env
WorkingDirectory=/opt/mutt/services
ExecStart=/opt/mutt/venv/bin/python /opt/mutt/services/web_ui_service.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 5.5. Reload systemd Daemon

After creating or modifying systemd unit files, you must instruct systemd to reload its configuration to recognize the changes. This does not start the services—it only makes systemd aware of the new service definitions.

```bash
sudo systemctl daemon-reload
```

**Verification:** Run `systemctl list-unit-files | grep mutt` to confirm all four MUTT service units are now visible to systemd.

---

## 6. Firewall Configuration

Configure RHEL's firewalld to allow inbound traffic to the MUTT service ports. This step is critical for allowing external systems to send logs to the Ingestor and for accessing the Web UI. The firewalld service must be enabled and running, then rules are added to open the required ports. Adjust the firewall rules based on your network requirements:

- **8080/tcp**: Ingestor HTTP endpoint (receives syslog and SNMP traps)
- **8081/tcp**: Alerter Prometheus metrics endpoint
- **8082/tcp**: Alerter health check endpoint
- **8083/tcp**: Moog Forwarder Prometheus metrics endpoint
- **8084/tcp**: Moog Forwarder health check endpoint
- **8090/tcp**: Web UI interface
- **514/tcp & 514/udp**: Syslog (only if receiving syslog directly, not via rsyslog HTTP)
- **162/udp**: SNMP traps (if receiving SNMP traps directly)

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-port=8080/tcp   # Ingestor HTTP
sudo firewall-cmd --permanent --add-port=8081/tcp   # Alerter metrics
sudo firewall-cmd --permanent --add-port=8082/tcp   # Alerter health
sudo firewall-cmd --permanent --add-port=8083/tcp   # Moog metrics
sudo firewall-cmd --permanent --add-port=8084/tcp   # Moog health
sudo firewall-cmd --permanent --add-port=8090/tcp   # Web UI
sudo firewall-cmd --permanent --add-port=514/tcp    # Syslog (if needed)
sudo firewall-cmd --permanent --add-port=514/udp    # Syslog (if needed)
sudo firewall-cmd --permanent --add-port=162/udp    # SNMP traps (if needed)
sudo firewall-cmd --reload
```

**Verification:** Check firewall status with `sudo firewall-cmd --list-all` to confirm all rules are active. You can also verify with `sudo firewall-cmd --list-ports` to see the open ports.

---

## 7. Starting and Verifying Services

With all configuration in place, you're now ready to start the MUTT services and verify they are running correctly. This section covers starting the services, checking their status, enabling automatic startup on boot, and performing health checks.

### 7.1. Start MUTT Services

Start all four MUTT services simultaneously using systemctl:

```bash
sudo systemctl start mutt-ingestor.service mutt-alerter.service mutt-moog-forwarder.service mutt-webui.service
```

### 7.2. Verify Service Status

Check the status of each service to ensure they started successfully. Look for "active (running)" status and check for any error messages in the output. If a service failed to start, use `journalctl -xeu <service-name>` to view detailed logs.

```bash
sudo systemctl status mutt-ingestor.service
sudo systemctl status mutt-alerter.service
sudo systemctl status mutt-moog-forwarder.service
sudo systemctl status mutt-webui.service
```

**Expected output:** Each service should show `Active: active (running)` in green. If any service shows `failed` or `inactive`, review the logs using `journalctl -xeu mutt-<service-name>.service`.

### 7.3. Enable Services on Boot

To ensure MUTT services start automatically when the server boots or reboots, enable them using systemctl. This creates symbolic links in the systemd configuration that trigger service startup during the boot sequence.

```bash
sudo systemctl enable mutt-ingestor.service mutt-alerter.service mutt-moog-forwarder.service mutt-webui.service
```

**Verification:** Run `systemctl is-enabled mutt-ingestor.service` (repeat for other services) to confirm they return "enabled".

### 7.4. Perform Health Checks

Each MUTT service exposes a `/health` endpoint that returns HTTP 200 when the service is operational. Use `curl` to verify all services are responding correctly. The `-sSf` flags make curl silent except for errors and fail on HTTP error codes.

```bash
curl -sSf http://127.0.0.1:8080/health  # Ingestor
curl -sSf http://127.0.0.1:8082/health  # Alerter health port
curl -sSf http://127.0.0.1:8084/health  # Moog Forwarder health port
curl -sSf http://127.0.0.1:8090/health  # Web UI
```

**Expected output:** Each command should return `{"status":"healthy"}` or similar confirmation. If any health check fails, review the service logs using `journalctl -u mutt-<service-name>.service`.

---

## 8. Post-Installation

Congratulations! You have successfully deployed MUTT v2.5 on your RHEL 8/9 server. All four core services (Ingestor, Alerter, Moog Forwarder, and Web UI) are now running under systemd supervision with automatic restart and boot-time startup enabled.

### Next Steps

1. **Access the Web UI**: Open a web browser and navigate to `http://<your-server-ip>:8090` to access the MUTT Web UI. From here, you can:
   - View real-time metrics and system health
   - Create and manage routing rules
   - Configure team assignments and alerting logic
   - Review the audit log for all configuration changes

2. **Configure Routing Rules**: Use the Web UI to define how incoming events should be processed and routed. Rules are stored in PostgreSQL and can be dynamically updated without service restarts (if `DYNAMIC_CONFIG_ENABLED=true`).

3. **Monitor Service Health**: Regularly check service status using:
   ```bash
   sudo systemctl status mutt-*
   ```

4. **Review Logs**: Monitor service logs for errors or warnings:
   ```bash
   sudo journalctl -u mutt-ingestor.service -f   # Follow Ingestor logs
   sudo journalctl -u mutt-alerter.service -f    # Follow Alerter logs
   ```

5. **Integrate with Prometheus (Optional)**: If you have Prometheus deployed, configure it to scrape metrics from:
   - Alerter metrics: `http://<server>:8081/metrics`
   - Moog Forwarder metrics: `http://<server>:8083/metrics`

6. **TLS Certificates**: If you configured TLS for Redis and PostgreSQL connections, ensure the CA certificates are placed in `/etc/mutt/certs/` as specified in the `mutt.env` file.

7. **Backup Configuration**: Regularly back up the following critical files:
   - `/etc/mutt/mutt.env`
   - `/etc/mutt/secrets/vault_secret_id`
   - PostgreSQL database (routing rules, teams, audit logs)

### Troubleshooting

If you encounter issues:

- **Service fails to start**: Check `journalctl -xeu mutt-<service-name>.service` for detailed error messages
- **Cannot connect to Vault/Redis/PostgreSQL**: Verify network connectivity and credentials in `/etc/mutt/mutt.env`
- **Health checks fail**: Ensure firewall rules are correct and services are listening on expected ports
- **No logs being ingested**: Verify rsyslog configuration and check that the Ingestor API key is correct

For additional support, refer to the architecture documentation at [docs/architecture/DEPLOYMENT_ARCHITECTURE.md](docs/architecture/DEPLOYMENT_ARCHITECTURE.md) or consult your system administrator.

---

**Installation Complete!** Your MUTT system is ready to process events and forward alerts to Moogsoft.
