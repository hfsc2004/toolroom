#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

KIOSK_USER="toolroom"
INSTALL_DIR="/home/$KIOSK_USER/toolroom_app"

echo "=== Toolroom Kiosk Installer ==="

# Must run as root (or with sudo)
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./install.sh"
    exit 1
fi

# 1. System dependencies
echo "[1/8] Installing system packages..."
apt update
apt install -y python3-venv sqlite3 cage cog cifs-utils

# 2. Create kiosk user if needed
if ! id "$KIOSK_USER" >/dev/null 2>&1; then
    echo "[2/8] Creating '$KIOSK_USER' user..."
    adduser --disabled-password --gecos "Toolroom Kiosk" "$KIOSK_USER"
else
    echo "[2/8] User '$KIOSK_USER' already exists."
fi

# 3. Copy app to kiosk user's home (skip if already running from there)
echo "[3/8] Installing app to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='venv*' --exclude='__pycache__' --exclude='.git' --exclude='data' "$APP_DIR/" "$INSTALL_DIR/"
chown -R "$KIOSK_USER:$KIOSK_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/start.sh"

# 4. Create venv and install Python deps
echo "[4/8] Setting up Python environment..."
sudo -u "$KIOSK_USER" bash -c "
    cd '$INSTALL_DIR'
    python3 -m venv venv
    ./venv/bin/python -m ensurepip --upgrade
    ./venv/bin/python -m pip install --upgrade pip setuptools wheel
    ./venv/bin/python -m pip install -r requirements.txt
"

# Verify
sudo -u "$KIOSK_USER" "$INSTALL_DIR/venv/bin/python" -m gunicorn --version >/dev/null
sudo -u "$KIOSK_USER" "$INSTALL_DIR/venv/bin/python" -c "import flask" >/dev/null
echo "    Python dependencies verified."

# 5. Initialize database
echo "[5/8] Initializing database..."
sudo -u "$KIOSK_USER" mkdir -p "$INSTALL_DIR/data"
if [ ! -f "$INSTALL_DIR/data/inventory.db" ]; then
    sudo -u "$KIOSK_USER" sqlite3 "$INSTALL_DIR/data/inventory.db" \
        "CREATE TABLE logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, badge_id TEXT, item_id TEXT, qty INTEGER DEFAULT 1, is_edited INTEGER DEFAULT 0, original_qty INTEGER);"
    echo "    Database created."
else
    echo "    Database already exists, skipping."
fi
# Users table is auto-created by app.py on first run (with default admin account)

# 6. Configure TTY1 autologin
echo "[6/8] Configuring auto-login on TTY1..."
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $KIOSK_USER --noclear %I \$TERM
EOF

# 7. Configure auto-start on login
echo "[7/8] Configuring kiosk auto-start..."
BASH_PROFILE="/home/$KIOSK_USER/.bash_profile"
MARKER="# Auto-start Toolroom kiosk on TTY1"
if ! grep -q "$MARKER" "$BASH_PROFILE" 2>/dev/null; then
    cat >> "$BASH_PROFILE" << EOF

$MARKER
if [ "\$(tty)" = "/dev/tty1" ]; then
    exec $INSTALL_DIR/start.sh
fi
EOF
    chown "$KIOSK_USER:$KIOSK_USER" "$BASH_PROFILE"
    echo "    .bash_profile configured."
else
    echo "    .bash_profile already configured, skipping."
fi

# 8. Set boot target to console (no desktop)
echo "[8/8] Setting boot target to multi-user (no desktop)..."
systemctl set-default multi-user.target
loginctl enable-linger "$KIOSK_USER"
systemctl daemon-reload

echo ""
echo "=== Installation complete ==="
echo ""
echo "Reboot to start the kiosk:  sudo reboot"
echo ""
echo "To restore desktop mode:    sudo systemctl set-default graphical.target && sudo reboot"
echo "To stop kiosk via SSH:      sudo systemctl stop getty@tty1"
echo "To restart kiosk via SSH:   sudo systemctl restart getty@tty1"
