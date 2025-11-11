# MUTT Deployment Architecture

**Version:** 1.0
**Last Updated:** 2025-11-10
**Status:** Stable
**Audience:** Operators, SREs, Engineers
**Prerequisites:** `SYSTEM_ARCHITECTURE.md`

---

## Table of Contents
1. [Deployment Models](#deployment-models)
    - [Standalone Server (Primary Production Model)](#standalone-server-primary-production-model)
    - [Kubernetes/OpenShift](#kubernetesopenshift)
    - [Docker Compose (Development/Testing)](#docker-compose-developmenttesting)
2. [Infrastructure Requirements](#infrastructure-requirements)
3. [High Availability Design](#high-availability-design)
4. [Network Architecture](#network-architecture)
5. [Data Persistence Strategy](#data-persistence-strategy)
6. [Security Architecture](#security-architecture)

---

## Deployment Models

MUTT is designed to be deployed in several environments. The primary and most supported model for production is the Standalone Server deployment on a RHEL-based OS.

### Standalone Server (Primary Production Model)

This model involves deploying the MUTT services as `systemd` units on one or more RHEL (or CentOS/Rocky Linux) servers. It is designed for environments where Kubernetes is not available or desired.

#### Directory Structure and File Locations

A strict directory structure is enforced to ensure consistency and security.

*   `/opt/mutt/`: Main application directory.
    *   `/opt/mutt/services/`: Contains the Python service files (`ingestor_service.py`, etc.).
    *   `/opt/mutt/venv/`: The Python virtual environment for the application.
*   `/etc/mutt/`: Configuration directory.
    *   `/etc/mutt/mutt.env`: Main environment variable configuration file. **Permissions must be `600` (owner read/write only).**
    *   `/etc/mutt/certs/`: For all TLS certificates (`ca.pem`, `server.crt`, `server.key`).
    *   `/etc/mutt/secrets/`: For sensitive file-based secrets.
        *   `/etc/mutt/secrets/vault_secret_id`: The Vault Secret ID. **Permissions must be `600`.**
*   `/etc/systemd/system/`: Location for `systemd` unit files.
    *   `mutt-ingestor.service`
    *   `mutt-alerter.service`
    *   `mutt-moog-forwarder.service`
    *   `mutt-webui.service`
*   `/var/log/mutt/`: Log directory for services (if not using `journald`).
*   `/etc/rsyslog.d/`:
    *   `99-mutt.conf`: rsyslog configuration to forward messages to the Ingestor.
*   `/etc/snmp/`:
    *   `snmptrapd.conf`: SNMP trap daemon configuration.

#### User/Group Setup

A dedicated, non-privileged user should run the MUTT services.

*   **User:** `mutt`
*   **Group:** `mutt`
*   **Shell:** `/sbin/nologin` (or `/bin/false`) to prevent interactive logins.
*   **Ownership:** The `mutt` user should own `/opt/mutt/`, `/etc/mutt/`, and `/var/log/mutt/`.

**Command Example:**
```bash
sudo groupadd mutt
sudo useradd -r -g mutt -s /sbin/nologin -d /opt/mutt -c "MUTT Service User" mutt
sudo chown -R mutt:mutt /opt/mutt /etc/mutt
```

#### systemd Unit File Configuration

Each service runs as a separate `systemd` unit. This provides process supervision, automatic restarts, and dependency management.

**Example (`mutt-alerter.service`):**
```ini
[Unit]
Description=MUTT Alerter Service
After=network-online.target redis.service postgresql.service vault.service
Requires=redis.service postgresql.service

[Service]
# User and Group
User=mutt
Group=mutt

# Environment
EnvironmentFile=/etc/mutt/mutt.env
ExecStart=/opt/mutt/venv/bin/python /opt/mutt/services/alerter_service.py

# Security Hardening
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true

# Process Management
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s

[Install]
WantedBy=multi-user.target
```
*   **`After` & `Requires`:** Ensures that dependencies like Redis and PostgreSQL are started before MUTT.
*   **`EnvironmentFile`:** Loads the centralized configuration from `/etc/mutt/mutt.env`.
*   **Security:** Hardening options are applied to limit the service's privileges.
*   **`Restart`:** Automatically restarts the service if it fails.

#### Service Dependencies and Startup Order

1.  **External Dependencies:** `redis`, `postgresql`, `vault`
2.  **MUTT Services:**
    *   `mutt-ingestor.service`
    *   `mutt-alerter.service`
    *   `mutt-moog-forwarder.service`
    *   `mutt-webui.service`

The services can be started in any order relative to each other, as they are decoupled by Redis queues. However, they all depend on the external infrastructure being available.

#### Firewall Configuration (`firewalld`)

The necessary ports must be opened on the server's firewall.

**Command Example:**
```bash
sudo firewall-cmd --permanent --add-port=8080/tcp  # Ingestor
sudo firewall-cmd --permanent --add-port=8081-8082/tcp # Alerter
sudo firewall-cmd --permanent --add-port=8083-8084/tcp # Moog Forwarder
sudo firewall-cmd --permanent --add-port=8090/tcp  # Web UI
sudo firewall-cmd --permanent --add-port=514/tcp   # rsyslog
sudo firewall-cmd --permanent --add-port=514/udp   # rsyslog
sudo firewall-cmd --permanent --add-port=162/udp   # snmptrapd
sudo firewall-cmd --reload
```

#### SELinux Configuration

On an SELinux-enforcing system, you may need to set the correct context for the log directories and network ports, or generate a custom policy. For initial testing, SELinux can be set to permissive mode, but a proper policy is required for production.

**Example (Allowing Gunicorn to bind to ports):**
```bash
sudo setsebool -P httpd_can_network_connect 1
```

### Kubernetes/OpenShift

In a Kubernetes or OpenShift environment, each MUTT service is deployed as a separate **Deployment**, with a **Service** object to expose its ports.

*   **Deployments:** Each service (`ingestor`, `alerter`, etc.) gets its own Deployment manifest, specifying the container image, replica count, and resource requests/limits.
*   **ConfigMaps and Secrets:**
    *   Environment variables are managed via **ConfigMaps**.
    *   Sensitive information (API keys, passwords) is managed via **Secrets**. The Vault Secret ID file would be mounted into the pod from a Kubernetes Secret.
*   **Services:** A Kubernetes Service of type `ClusterIP` is created for each MUTT service to allow communication within the cluster.
*   **Ingress/Route:** An **Ingress** (in Kubernetes) or **Route** (in OpenShift) is used to expose the `Ingestor` and `Web UI` services to external traffic.

### Docker Compose (Development/Testing)

A `docker-compose.yml` file is provided for standing up the entire MUTT stack (including Redis, PostgreSQL, and Vault) in a local development environment. This is the fastest way for a developer to get started, but it is **not recommended for production** due to its lack of automatic restarts, high availability, and orchestration.

---

## Infrastructure Requirements

*   **Compute:**
    *   **Standalone:** A RHEL 8/9 server with at least 2 vCPUs and 8 GB RAM is a reasonable starting point for a small-to-medium load.
    *   **Kubernetes:** Resource requests should be set based on capacity planning (e.g., 0.5 vCPU, 512 MB RAM per Alerter pod).
*   **Network:** Low-latency network connectivity between the MUTT services and the Redis/PostgreSQL servers is critical for performance.
*   **External Dependencies:** A running instance of Redis, PostgreSQL, and HashiCorp Vault is required.

---

## High Availability Design

*   **Redis:** A **Redis Sentinel** configuration with 3 or 5 nodes is required for automatic failover of the Redis primary. The services need to be configured with the Sentinel hostnames to take advantage of this.
*   **PostgreSQL:** A streaming replication setup (e.g., using Patroni or a cloud provider's managed solution) with a floating IP or DNS name for the primary is required for database high availability.
*   **Vault:** A Vault cluster with at least 3 nodes is required for HA.
*   **Service Redundancy:** In both standalone and Kubernetes deployments, running at least **two instances** of each MUTT service on different physical hosts provides service-level redundancy.

---

## Network Architecture

### Port Assignments

| Port      | Service          | Purpose                  |
| --------- | ---------------- | ------------------------ |
| 8080/tcp  | Ingestor         | HTTP Event Ingestion     |
| 8081/tcp  | Alerter          | Prometheus Metrics       |
| 8082/tcp  | Alerter          | Health Check             |
| 8083/tcp  | Moog Forwarder   | Prometheus Metrics       |
| 8084/tcp  | Moog Forwarder   | Health Check             |
| 8090/tcp  | Web UI           | Web Dashboard & API      |
| 514/tcp+udp| rsyslog          | Syslog Ingestion         |
| 162/udp   | snmptrapd        | SNMP Trap Ingestion      |

### TLS Termination

**TLS is enforced everywhere.** All communication between services, and between services and their database/cache, should be over TLS. In a standalone deployment, TLS is terminated at each service. In a Kubernetes deployment, TLS can optionally be terminated at the Ingress, with unencrypted traffic inside the cluster (if the network is trusted) or with a service mesh like Istio providing mutual TLS.

---

## Data Persistence Strategy

*   **Redis:** Redis is used for transient data (queues). **AOF (Append-Only File) persistence** should be enabled with a `fsync` policy of `everysec`. This provides a good balance of performance and durability, ensuring that at most one second of queued data could be lost in the event of a catastrophic Redis failure.
*   **PostgreSQL:** This is used for long-term, durable storage of audit logs. A standard **Point-in-Time Recovery (PITR)** backup strategy should be implemented, with regular full backups and continuous archiving of WAL (Write-Ahead Log) files.
*   **Log Retention:** Log files generated by the services (`/var/log/mutt/`) should be rotated daily using `logrotate`. The retention period for the PostgreSQL `event_audit_log` is managed by a cron job that drops old monthly partitions.

---

## Security Architecture

*   **Secret Distribution:** All secrets are managed by HashiCorp Vault. Services authenticate using AppRole and retrieve secrets at startup. The only secret stored on the host is the Vault Secret ID, which is file-permission protected.
*   **TLS Everywhere:** As mentioned, all network communication is encrypted with TLS. This includes service-to-service, service-to-database, and service-to-Redis.
*   **API Authentication:** The Ingestor and Web UI APIs are protected by an API key, which must be provided in the `X-API-KEY` header.
*   **Network Segmentation:** In a high-security environment, the services should be placed in a separate network segment from the data sources and the external Moog AIOps platform, with strict firewall rules controlling traffic between the segments.

---

## See Also

- Code modules and entry points: code/MODULES.md
- API reference for endpoints and payloads: api/REFERENCE.md
- OpenAPI specification: api/openapi.yaml
