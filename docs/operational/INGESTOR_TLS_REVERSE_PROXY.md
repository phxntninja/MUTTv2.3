MUTT Ingestor TLS Reverse Proxy
==============================

MUTT primarily receives data over HTTPS. The recommended pattern is to terminate TLS at a reverse proxy on the server and proxy to the local Ingestor (HTTP on 127.0.0.1:8080).

Option A: NGINX (recommended)
-----------------------------

1) Install NGINX
- Ubuntu: `sudo apt -y install nginx`
- RHEL: `sudo dnf -y install nginx && sudo systemctl enable --now nginx`

2) Place certificates
- Copy your certificate and private key to:
  - `/etc/ssl/mutt/ingestor.crt`
  - `/etc/ssl/mutt/ingestor.key`
- Restrict permissions: `sudo chmod 640 /etc/ssl/mutt/ingestor.key && sudo chown root:nginx /etc/ssl/mutt/ingestor.key` (group may be `www-data` on Ubuntu)
- Distribute the issuing CA certificate to senders (rsyslog `tls.cacert`): `/etc/mutt/certs/mutt_ingestor_ca.crt`

3) Configure virtual hosts

Ingestor on 8443 (HTTPS):
```
server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate     /etc/ssl/mutt/ingestor.crt;
    ssl_certificate_key /etc/ssl/mutt/ingestor.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    client_max_body_size 5m;

    location /ingest {
        proxy_pass         http://127.0.0.1:8080/ingest;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_read_timeout 30s;
    }

    # Optional: health
    location /health { proxy_pass http://127.0.0.1:8080/health; }
}
```

Optional: Web UI on 443 (HTTPS):
```
server {
    listen 443 ssl;
    server_name mutt-web.lab.local;

    ssl_certificate     /etc/ssl/mutt/ingestor.crt;
    ssl_certificate_key /etc/ssl/mutt/ingestor.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    location / {
        proxy_pass         http://127.0.0.1:8090/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_read_timeout 60s;
    }
}
```

4) Enable the config and reload NGINX
- Ubuntu: Place under `/etc/nginx/sites-available/` and symlink to `sites-enabled/`, then `sudo nginx -t && sudo systemctl reload nginx`
- RHEL: Place under `/etc/nginx/conf.d/` as `mutt.conf`, then `sudo nginx -t && sudo systemctl reload nginx`

5) Open firewall ports
- Ubuntu (ufw): `sudo ufw allow 8443/tcp` and optionally `sudo ufw allow 443/tcp`
- RHEL (firewalld): `sudo firewall-cmd --permanent --add-port=8443/tcp && sudo firewall-cmd --permanent --add-port=443/tcp && sudo firewall-cmd --reload`

Option B: HAProxy
-----------------
Minimal frontend on 8443 terminating TLS and proxying to 127.0.0.1:8080:
```
frontend mutt_ingestor_https
  bind *:8443 ssl crt /etc/ssl/mutt/ingestor.pem
  mode http
  default_backend mutt_ingestor_backend

backend mutt_ingestor_backend
  mode http
  server local_ingestor 127.0.0.1:8080
```

Restart HAProxy and allow 8443/tcp in the firewall as above.

Sender configuration (rsyslog and scripts)
-----------------------------------------
- rsyslog omhttp action must point to the HTTPS endpoint and include the CA cert:
  - See `docs/operational/RSYSLOG_FORWARD_TO_MUTT_TLS.conf` and set `server` and `tls.cacert`.
- snmptrapd traphandle script supports custom CA via `MUTT_CACERT` env var.
  - Set `MUTT_INGEST_URL=https://<ingestor-host>:8443/ingest`
  - Set `MUTT_CACERT=/etc/mutt/certs/mutt_ingestor_ca.crt`

