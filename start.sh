#!/bin/bash

# Get the directory where the script is located
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# 1. Kill any existing instances to prevent port conflicts
pkill gunicorn || true
pkill cog || true

# 2. Start the Backend using the Venv's Gunicorn
echo "Starting Toolroom Backend..."
./venv/bin/gunicorn --bind 0.0.0.0:5000 app:app --daemon --workers 2 --log-file data/app.log

# 3. Wait for Flask to initialize
sleep 3

# 4. Launch the Kiosk UI (Cage + Cog)
echo "Launching Kiosk UI..."
# Cog is pointed to the local Flask server
cage -- cog http://localhost:5000
