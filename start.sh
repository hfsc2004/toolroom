#!/bin/bash
set -e

# Get the directory where the script is located
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
PYTHON_BIN="./venv/bin/python"
GUNICORN_PID=""
PID_FILE="data/gunicorn.pid"

stop_backend() {
    # Prefer PID file first.
    if [ -f "$PID_FILE" ]; then
        PID_FROM_FILE="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [ -n "$PID_FROM_FILE" ] && kill -0 "$PID_FROM_FILE" 2>/dev/null; then
            kill "$PID_FROM_FILE" 2>/dev/null || true
            sleep 1
            kill -9 "$PID_FROM_FILE" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi

    # Command-line and port-based fallbacks.
    pkill -f "gunicorn.*app:app" || true
    pkill -f "cog http://localhost:5000" || true
    lsof -t -iTCP:5000 -sTCP:LISTEN 2>/dev/null | xargs -r kill 2>/dev/null || true
    sleep 1
    lsof -t -iTCP:5000 -sTCP:LISTEN 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    fuser -k 5000/tcp 2>/dev/null || true
}

cleanup() {
    echo "Shutting down Toolroom processes..."
    if [ -n "$GUNICORN_PID" ] && kill -0 "$GUNICORN_PID" 2>/dev/null; then
        kill "$GUNICORN_PID" 2>/dev/null || true
        wait "$GUNICORN_PID" 2>/dev/null || true
    fi
    stop_backend
}

trap cleanup EXIT INT TERM HUP QUIT

# 1. Kill any existing instances to prevent port conflicts
# Use -f because process name is often "python" when launched via "python -m gunicorn".
stop_backend
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
"$PYTHON_BIN" -m gunicorn --bind 127.0.0.1:5000 app:app --workers 2 --pid "$PID_FILE" --log-file data/app.log &
GUNICORN_PID=$!

# 6. Wait for Flask to initialize
sleep 3

# 7. Launch the Kiosk UI (Cage + Cog)
echo "Launching Kiosk UI..."
# Run cog inside a shell so that when cog exits, we explicitly pkill cage.
cage -- /bin/bash -lc 'cog http://localhost:5000; pkill -f "^cage( |$)" || true' || true
