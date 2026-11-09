#!/usr/bin/env bash
# Idempotent server provisioning for StrayMatch (Debian/Ubuntu LXC).
# Installs packages, the strays user/venv, systemd + nginx units and enables
# the services. It never creates secrets and never touches cloudflared.
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/strays}"
APP_USER="${APP_USER:-strays}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "provision.sh must run as root (use sudo)." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    nginx \
    git \
    ca-certificates \
    curl \
    sudo

if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd \
        --system \
        --user-group \
        --create-home \
        --home-dir "$APP_DIR" \
        --shell /usr/sbin/nologin \
        "$APP_USER"
fi

if [ ! -f "$APP_DIR/manage.py" ] && [ "$REPO_DIR" != "$APP_DIR" ]; then
    install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
    cp -a "$REPO_DIR/." "$APP_DIR/"
fi

if [ ! -f "$APP_DIR/manage.py" ]; then
    echo "Django project not found at $APP_DIR (clone/copy it there first)." >&2
    exit 1
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 755 "$APP_DIR"
install -d -m 755 -o "$APP_USER" -g "$APP_USER" \
    "$APP_DIR/staticfiles" \
    "$APP_DIR/media" \
    "$APP_DIR/media/dogs"

if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    runuser -u "$APP_USER" -- python3 -m venv "$APP_DIR/.venv"
fi
runuser -u "$APP_USER" -- "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
runuser -u "$APP_USER" -- "$APP_DIR/.venv/bin/python" -m pip install \
    -r "$APP_DIR/requirements.txt"

install -m 644 "$REPO_DIR/deploy/strays.service" /etc/systemd/system/strays.service
install -m 644 "$REPO_DIR/deploy/nginx-strays.conf" \
    /etc/nginx/sites-available/strays.conf
ln -sfn /etc/nginx/sites-available/strays.conf \
    /etc/nginx/sites-enabled/strays.conf
# The default site listens on the LAN; StrayMatch must stay loopback-only.
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
nginx -t
systemctl enable nginx
systemctl reload-or-restart nginx
systemctl enable strays.service

if [ -f /etc/strays.env ]; then
    systemctl restart strays.service
    echo "strays.service restarted with existing /etc/strays.env."
else
    echo "Create /etc/strays.env from deploy/strays.env.example, then run:"
    echo "  sudo $APP_DIR/deploy/deploy.sh"
fi

echo "Provisioning finished. cloudflared is intentionally not installed or configured."
