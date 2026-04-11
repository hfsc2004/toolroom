#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "--- Installing Toolroom Environment ---"

# System dependencies
sudo apt update
sudo apt install -y python3-venv sqlite3 cage cog cifs-utils

# Venv Setup
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

./venv/bin/pip install --upgrade pip

# Install from the requirements file
if [ -f "requirements.txt" ]; then
    echo "Installing Python packages from requirements.txt..."
    ./venv/bin/pip install -r requirements.txt
else
    echo "Error: requirements.txt not found!"
    exit 1
fi

# Directory and DB Setup
mkdir -p data
if [ ! -f "data/inventory.db" ]; then
    echo "Initializing Database..."
    sqlite3 data/inventory.db "CREATE TABLE logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, badge_id TEXT, item_id TEXT, qty INTEGER DEFAULT 1, is_edited INTEGER DEFAULT 0, original_qty INTEGER);"
fi

echo "--- Installation complete ---"
