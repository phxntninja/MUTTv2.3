# MUTT Standalone Server Installation Guide (RHEL 9)

**Version:** 1.0
**Last Updated:** 2025-11-10
**Status:** Draft
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

**[Claude: Write a brief introduction explaining the purpose of this document. Mention that it provides step-by-step instructions to deploy the MUTT v2.5 application on a standalone RHEL 9 server.]**

This guide assumes you are starting with a fresh RHEL 9 server and have `sudo` privileges. It also assumes that the external dependencies (PostgreSQL, Redis, Vault) are already set up and network-accessible.

---

## 2. System Preparation

### 2.1. Update System Packages

**[Claude: Explain that the first step is to update the system's package lists.]**

**[CODEX: Provide the `dnf` command to update system packages.]**

### 2.2. Install Dependencies

**[Claude: Explain that MUTT requires Python, a virtual environment tool, and other build tools to be installed.]**

**[CODEX: Provide the single `dnf` command to install `python3`, `python3-devel`, `python3-pip`, `gcc`, and `libpq-devel`.]**

### 2.3. Create Service User

**[Claude: Explain that for security, MUTT will run under a dedicated, non-privileged user named `mutt`.]**

**[CODEX: Provide the `groupadd` and `useradd` commands to create the `mutt` user and group with a home directory of `/opt/mutt` and a disabled login shell.]**

---

## 3. Directory and Code Setup

### 3.1. Create Directory Structure

**[Claude: Explain the purpose of the directories for the application, configuration, and logs.]**

**[CODEX: Provide the `mkdir` commands to create `/opt/mutt/services`, `/etc/mutt/certs`, `/etc/mutt/secrets`, and `/var/log/mutt`.]**

### 3.2. Set Permissions

**[Claude: Explain that the `mutt` user needs to own the created directories.]**

**[CODEX: Provide the `chown` commands to give `mutt:mutt` ownership of `/opt/mutt`, `/etc/mutt`, and `/var/log/mutt`.]**

### 3.3. Deploy Application Code

**[Claude: Instruct the user to copy the MUTT source code into the `/opt/mutt/services` directory. Assume the user has the code available on the server.]**

### 3.4. Create Python Virtual Environment

**[Claude: Explain the importance of using a virtual environment to isolate Python dependencies.]**

**[CODEX: Provide the commands to create a Python virtual environment in `/opt/mutt/venv` as the `mutt` user.]**

### 3.5. Install Python Dependencies

**[Claude: Explain that the required Python packages will now be installed into the virtual environment.]**

**[CODEX: Provide the `pip` command to install the packages from the `requirements.txt` file into the `/opt/mutt/venv` virtual environment.]**

---

## 4. Configuration

### 4.1. Configure Environment File

**[Claude: Explain that all service configuration is managed via the `/etc/mutt/mutt.env` file. Instruct the user to create this file and paste the provided template. Emphasize that they must fill in the values for their environment.]**

**[CODEX: Provide the full content for a template `/etc/mutt/mutt.env` file. Include all relevant variables for all services (Ingestor, Alerter, Moog Forwarder, Web UI) with placeholder values (e.g., `REDIS_HOST=your-redis-host`).]**

### 4.2. Set `mutt.env` Permissions

**[Claude: Explain that this file contains sensitive information and its permissions must be restricted.]**

**[CODEX: Provide the `chmod` and `chown` commands to set the permissions of `/etc/mutt/mutt.env` to `600` and ownership to `mutt:mutt`.]**

### 4.3. Configure Vault Secret ID

**[Claude: Explain that the Vault Secret ID is stored in a separate, secure file.]**

**[CODEX: Provide the commands to create the `/etc/mutt/secrets/vault_secret_id` file, set its permissions to `600`, and set ownership to `mutt:mutt`. Instruct the user to paste their Secret ID into this file.]**

### 4.4. Configure rsyslog

**[Claude: Explain that `rsyslog` needs to be configured to forward syslog messages to the MUTT Ingestor service.]**

**[CODEX: Provide the full content for the `/etc/rsyslog.d/99-mutt.conf` file. Use placeholders like `REPLACE_WITH_INGESTOR_API_KEY`.]**

**[Claude: Add a step explaining how the user should replace the placeholder with the actual API key.]**

---

## 5. Service Installation (systemd)

**[Claude: Explain that each MUTT service will be managed by `systemd`.]**

### 5.1. Create `mutt-ingestor.service`

**[CODEX: Provide the complete content for the `/etc/systemd/system/mutt-ingestor.service` file. Ensure the `ExecStart` path points to the correct virtual environment and service file.]**

### 5.2. Create `mutt-alerter.service`

**[CODEX: Provide the complete content for the `/etc/systemd/system/mutt-alerter.service` file.]**

### 5.3. Create `mutt-moog-forwarder.service`

**[CODEX: Provide the complete content for the `/etc/systemd/system/mutt-moog-forwarder.service` file.]**

### 5.4. Create `mutt-webui.service`

**[CODEX: Provide the complete content for the `/etc/systemd/system/mutt-webui.service` file.]**

### 5.5. Reload systemd Daemon

**[Claude: Explain that `systemd` needs to be reloaded to recognize the new service files.]**

**[CODEX: Provide the `systemctl daemon-reload` command.]**

---

## 6. Firewall Configuration

**[Claude: Explain that the firewall needs to be configured to allow traffic to the MUTT services.]**

**[CODEX: Provide the `firewall-cmd` commands to allow traffic on TCP ports 8080, 8081, 8082, 8083, 8084, 8090, 514 and UDP ports 514, 162. Include the command to reload the firewall.]**

---

## 7. Starting and Verifying Services

**[Claude: Explain how to start the services and check their status.]**

### 7.1. Start MUTT Services

**[CODEX: Provide the `systemctl start` commands for all four `mutt-*.service` units.]**

### 7.2. Verify Service Status

**[Claude: Instruct the user on how to check if the services started successfully.]**

**[CODEX: Provide the `systemctl status` commands for all four services. Include an example of what a healthy output looks like.]**

### 7.3. Enable Services on Boot

**[Claude: Explain that the services should be enabled to start automatically when the server boots.]**

**[CODEX: Provide the `systemctl enable` commands for all four services.]**

### 7.4. Perform Health Checks

**[Claude: Instruct the user to use `curl` to hit the health check endpoint of each service to confirm they are running and healthy.]**

**[CODEX: Provide the `curl` commands to check the health of the Ingestor (`:8080/health`), Alerter (`:8082/health`), Moog Forwarder (`:8084/health`), and Web UI (`:8090/health`).]**

---

## 8. Post-Installation

**[Claude: Provide a concluding paragraph summarizing that the installation is complete and pointing the user to the Web UI to get started with managing rules.]**