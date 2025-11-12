#!/bin/bash
# File: deployments/scripts/deploy_rhel.sh
# MUTT v2.5 RHEL Deployment Script

set -e

MUTT_USER="mutt"
MUTT_GROUP="mutt"
MUTT_HOME="/opt/mutt"
PYTHON_VERSION="3.10"

echo "=== MUTT v2.5 RHEL Deployment ==="

# 1. Create user and group
if ! id "$MUTT_USER" &>/dev/null; then
    echo "Creating mutt user..."
    useradd --system --home-dir "$MUTT_HOME" --shell /bin/bash "$MUTT_USER"
fi

# 2. Create directories
echo "Creating directories..."
mkdir -p "$MUTT_HOME"/{services,scripts,database,logs,venv}
chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 3. Install Python dependencies
echo "Setting up Python virtual environment..."
sudo -u "$MUTT_USER" python${PYTHON_VERSION} -m venv "$MUTT_HOME/venv"
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install --upgrade pip
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install -r requirements.txt

# 4. Copy application files
echo "Copying application files..."
cp -r services/* "$MUTT_HOME/services/"
cp -r scripts/* "$MUTT_HOME/scripts/"
cp -r database/* "$MUTT_HOME/database/"
chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 5. Copy environment file
if [ ! -f "$MUTT_HOME/.env" ]; then
    echo "Creating .env file..."
    cp .env.template "$MUTT_HOME/.env"
    chown "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME/.env"
    chmod 600 "$MUTT_HOME/.env"
    echo "WARNING: Edit $MUTT_HOME/.env with production values!"
fi

# 6. Install systemd service files
echo "Installing systemd services..."
cp deployments/systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# 7. Enable and start services
echo "Enabling services..."
systemctl enable mutt-ingestor.service
systemctl enable mutt-alerter@{1..5}.service
systemctl enable mutt-moog-forwarder.service
systemctl enable mutt-webui.service
systemctl enable mutt-remediation.service

echo "Starting services..."
systemctl start mutt-ingestor.service
systemctl start mutt-alerter@{1..5}.service
systemctl start mutt-moog-forwarder.service
systemctl start mutt-webui.service
systemctl start mutt-remediation.service

# 8. Check status
echo ""
echo "=== Service Status ==="
systemctl status mutt-ingestor.service --no-pager
systemctl status mutt-alerter@1.service --no-pager
systemctl status mutt-webui.service --no-pager

echo ""
echo "=== Deployment Complete ==="
echo "Logs: journalctl -u mutt-* -f"
echo "Config: $MUTT_HOME/.env"
