#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
PYTHON_BIN="./venv/bin/python"
PID_FILE="data/gunicorn.pid"

kill_all() {
    echo "Shutting down all Toolroom processes..."
    pkill -f "gunicorn.*app:app" 2>/dev/null || true
    pkill -x cog 2>/dev/null || true
    fuser -k 5000/tcp 2>/dev/null || true
    sleep 1
    pkill -9 -f "gunicorn.*app:app" 2>/dev/null || true
    pkill -9 -x cog 2>/dev/null || true
    fuser -k -9 5000/tcp 2>/dev/null || true
    rm -f "$PID_FILE"
}

trap kill_all EXIT

# Kill any existing instances
kill_all

# Ensure virtualenv exists
if [ ! -x "$PYTHON_BIN" ]; then
    python3 -m venv venv
fi

# Ensure pip works
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    "$PYTHON_BIN" -m ensurepip --upgrade
fi

# Ensure dependencies installed
if ! "$PYTHON_BIN" -c "import flask, gunicorn" >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
    "$PYTHON_BIN" -m pip install -r requirements.txt
fi

mkdir -p data

# Start gunicorn
echo "Starting Toolroom Backend..."
"$PYTHON_BIN" -m gunicorn --bind 127.0.0.1:5000 app:app --workers 2 --pid "$PID_FILE" --log-file data/app.log &
sleep 3

# Launch kiosk — cage is the sole compositor in direct boot mode.
# When cage exits, the EXIT trap fires and kills gunicorn.
echo "Launching Kiosk UI..."
cage -s -- cog http://localhost:5000
