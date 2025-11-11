RHEL Standalone Install Checklist (v2.5)

Purpose
- Fast, high-confidence checklist to install MUTT on a single RHEL 8/9 server using systemd. Use with Deployment Architecture and Code Modules docs for details.

1) System Requirements
- RHEL 8/9 with sudo
- Python 3.10+ and gcc, openssl-devel: `sudo dnf install -y python3 python3-pip python3-devel gcc openssl openssl-devel`
- Redis, PostgreSQL, Vault reachable (or installed locally)
- firewalld running; SELinux enforcing or permissive (see step 5)

2) Users, Paths, Permissions
- Create service user: `sudo useradd -r -s /sbin/nologin -d /opt/mutt mutt`
- Create paths: `/opt/mutt/{services,venv}`, `/etc/mutt/{certs,secrets}`, `/var/log/mutt`
- Ownership: `sudo chown -R mutt:mutt /opt/mutt /etc/mutt /var/log/mutt`

3) Code + Python Env
- Copy service files to `/opt/mutt/services/` (ingestor_service.py, alerter_service.py, moog_forwarder_service.py, web_ui_service.py)
- Create venv: `sudo -u mutt python3 -m venv /opt/mutt/venv`
- Upgrade pip: `sudo -u mutt /opt/mutt/venv/bin/pip install --upgrade pip`
- Install deps: `sudo -u mutt /opt/mutt/venv/bin/pip install -r /path/to/requirements.txt` (or `requirements.txt` from repo)

4) Configuration
- Create `/etc/mutt/mutt.env` (600) with env vars from README.md:376 and related tables
- Place TLS certs under `/etc/mutt/certs` (644 for .crt/.pem, 600 for .key)
- Vault AppRole (if used): store RoleID/SecretID under `/etc/mutt/secrets` (600)

5) Network and SELinux
- Open firewall ports:
  - Ingestor 8080, Alerter 8081-8082, Forwarder 8083-8084, Web UI 8090
  - Example: `sudo firewall-cmd --permanent --add-port=8080/tcp` ... `--reload`
- SELinux (enforcing): allow custom ports for gunicorn/http servers, or set permissive for initial bring-up
  - Example: `sudo semanage port -a -t http_port_t -p tcp 8090` (repeat for 8080-8084)

6) systemd Units (one per service)
- Environment file: `EnvironmentFile=/etc/mutt/mutt.env`
- Web UI and Ingestor (gunicorn):
  - ExecStart (webui): `/opt/mutt/venv/bin/gunicorn -w 4 -b 0.0.0.0:8090 'services.web_ui_service:app'`
  - ExecStart (ingestor): `/opt/mutt/venv/bin/gunicorn -w 4 -b 0.0.0.0:8080 'services.ingestor_service:app'`
- Alerter and Forwarder (python entrypoints):
  - ExecStart (alerter): `/opt/mutt/venv/bin/python /opt/mutt/services/alerter_service.py`
  - ExecStart (forwarder): `/opt/mutt/venv/bin/python /opt/mutt/services/moog_forwarder_service.py`
- Harden with ProtectSystem/ProtectHome/PrivateTmp; set Restart=on-failure
- Enable + start: `sudo systemctl enable --now mutt-{ingestor,alerter,moog-forwarder,webui}.service`

7) Health Checks
- Ingestor: `curl -f http://<host>:8080/health`
- Alerter: `curl -f http://<host>:8082/health`
- Forwarder: `curl -f http://<host>:8084/health`
- Web UI: `curl -f http://<host>:8090/health`

8) Post-Install
- Configure rsyslog to POST to Ingestor (see configs/rsyslog/99-mutt.conf)
- Configure snmptrapd if using SNMP (configs/rsyslog/snmptrapd.conf)
- Optional: Prometheus alert rules at docs/prometheus/alerts-v25.yml

References
- Deployment Architecture: architecture/DEPLOYMENT_ARCHITECTURE.md
- Code Modules: code/MODULES.md
- API Reference: api/REFERENCE.md
