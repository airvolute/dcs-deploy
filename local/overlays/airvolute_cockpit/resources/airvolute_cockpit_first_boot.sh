#!/bin/bash
set -o pipefail
set -e

MARKER=/var/lib/airvolute/cockpit-setup.done
LOG_DIR=/home/dcs_user/Airvolute/logs/dcs-deploy
LOG_FILE=${LOG_DIR}/airvolute_cockpit_first_boot.log

mkdir -p "$(dirname "$MARKER")" "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

if [ -f "$MARKER" ]; then
    echo "Airvolute Cockpit setup already completed."
    exit 0
fi

echo "Starting Airvolute Cockpit setup."

install -d -m 0755 /usr/share/cockpit/branding/ubuntu
if [ -d /usr/local/share/airvolute/cockpit/branding ]; then
    cp -a /usr/local/share/airvolute/cockpit/branding/. /usr/share/cockpit/branding/ubuntu/
    chown -R root:root /usr/share/cockpit/branding/ubuntu
    find /usr/share/cockpit/branding/ubuntu -type d -exec chmod 755 {} +
    find /usr/share/cockpit/branding/ubuntu -type f -exec chmod 644 {} +
fi

if [ -f /usr/local/share/airvolute/cockpit/password-policy/airvolute-password-modal.js ]; then
    install -o root -g root -m 0644 \
        /usr/local/share/airvolute/cockpit/password-policy/airvolute-password-modal.js \
        /usr/share/cockpit/shell/airvolute-password-modal.js

    if [ -f /usr/share/cockpit/shell/index.html ] &&
       ! grep -q 'airvolute-password-modal.js' /usr/share/cockpit/shell/index.html; then
        cp -a /usr/share/cockpit/shell/index.html /usr/share/cockpit/shell/index.html.airvolute-backup
        sed -i 's#<script src="index.js"></script>#<script src="index.js"></script>\n    <script src="airvolute-password-modal.js"></script>#' \
            /usr/share/cockpit/shell/index.html
    fi
fi

chown -R root:root /usr/local/share/cockpit/airvolute-*
find /usr/local/share/cockpit/airvolute-* -type d -exec chmod 755 {} +
find /usr/local/share/cockpit/airvolute-* -type f -exec chmod 644 {} +

systemctl enable cockpit.socket
systemctl restart cockpit.socket

touch "$MARKER"
echo "Airvolute Cockpit setup completed."
