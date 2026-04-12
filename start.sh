#!/bin/bash
set -e

# Get the directory where the script is located
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
PYTHON_BIN="./venv/bin/python"
GUNICORN_PID=""

cleanup() {
    echo "Shutting down Toolroom processes..."
    if [ -n "$GUNICORN_PID" ] && kill -0 "$GUNICORN_PID" 2>/dev/null; then
        kill "$GUNICORN_PID" 2>/dev/null || true
        wait "$GUNICORN_PID" 2>/dev/null || true
    fi
    pkill -f "gunicorn.*app:app" || true
    pkill -f "cog http://localhost:5000" || true
    fuser -k 5000/tcp 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# 1. Kill any existing instances to prevent port conflicts
# Use -f because process name is often "python" when launched via "python -m gunicorn".
pkill -f "gunicorn.*app:app" || true
pkill -f "cog http://localhost:5000" || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 1

# 2. Ensure virtualenv exists
if [ ! -x "$PYTHON_BIN" ]; then
    echo "Virtualenv missing. Creating venv..."
    python3 -m venv venv
fi

# 3. Ensure pip works inside venv
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    echo "Bootstrapping pip in venv..."
    "$PYTHON_BIN" -m ensurepip --upgrade
fi

# 4. Ensure required runtime packages are installed
if ! "$PYTHON_BIN" -c "import flask, gunicorn" >/dev/null 2>&1; then
    echo "Installing missing Python dependencies..."
    "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
    "$PYTHON_BIN" -m pip install -r requirements.txt
fi

# 5. Ensure data dir exists
mkdir -p data

# 2. Start the Backend using the Venv's Gunicorn
echo "Starting Toolroom Backend..."
"$PYTHON_BIN" -m gunicorn --bind 0.0.0.0:5000 app:app --workers 2 --log-file data/app.log &
GUNICORN_PID=$!

# 6. Wait for Flask to initialize
sleep 3

# 7. Launch the Kiosk UI (Cage + Cog)
echo "Launching Kiosk UI..."
# Cog is pointed to the local Flask server
cage -- cog http://localhost:5000
