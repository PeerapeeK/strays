#!/usr/bin/env bash
# Pull, install, migrate, collect static files and restart StayMatch.
# Run as root on the LXC:  sudo /srv/strays/deploy/deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/strays}"
ENV_FILE="${ENV_FILE:-/etc/strays.env}"
APP_USER="${APP_USER:-strays}"
SERVICE="${SERVICE:-strays.service}"

if [ "$(id -u)" -ne 0 ]; then
    echo "deploy.sh must run as root (use sudo)." >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing $ENV_FILE. Create it from deploy/strays.env.example first." >&2
    exit 1
fi

if [ ! -f "$APP_DIR/manage.py" ]; then
    echo "No Django project at $APP_DIR." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

if [ -z "${SECRET_KEY:-}" ]; then
    echo "SECRET_KEY is empty in $ENV_FILE." >&2
    exit 1
fi

run_as_app() {
    runuser -u "$APP_USER" -- env \
        HOME="$APP_DIR" \
        DEBUG="${DEBUG:-False}" \
        SECRET_KEY="$SECRET_KEY" \
        ALLOWED_HOSTS="${ALLOWED_HOSTS:-}" \
        CSRF_TRUSTED_ORIGINS="${CSRF_TRUSTED_ORIGINS:-}" \
        SECURE_HSTS_SECONDS="${SECURE_HSTS_SECONDS:-3600}" \
        "$@"
}

run_as_app git -C "$APP_DIR" pull --ff-only

run_as_app "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
run_as_app "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

run_as_app "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate --noinput
run_as_app "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput

systemctl restart "$SERVICE"
systemctl --no-pager --lines=0 status "$SERVICE"

echo "Deploy finished: https://strays.peerapeek.cc/healthz/"
