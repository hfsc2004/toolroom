# Toolroom Kiosk System

<p align="center">
  <img src="static/logo.png" alt="Toolroom Logo" width="200">
</p>

A barcode/QR-code scanning kiosk for tool crib inventory tracking, built for Raspberry Pi 4.

Workers scan their badge, scan a tool, and the transaction is logged. Runs fullscreen as a dedicated Wayland kiosk — no desktop environment needed.

## Features

- **QR/Barcode scanning** with command tiles (scanner or mouse/touch)
- **Quantity workflow** with numpad overlay and multi-digit scanning
- **Correction commands** (REDO BADGE, REDO ITEM)
- **Log overlay** with scroll support
- **Admin dashboard** with login, CSV export, and user manager
- **DB-backed user accounts** — create, edit, deactivate, and delete admin/operator accounts
- **HTTP Basic Auth** for remote access, local kiosk bypasses auth automatically
- **HTTPS ready** via nginx reverse proxy with local CA

## Requirements

- Raspberry Pi 4 (4GB recommended) running Raspberry Pi OS (Bookworm or later)
- Network connection
- USB barcode/QR scanner (acts as keyboard input)

## Quick Start

```bash
git clone https://github.com/hfsc2004/toolroom.git toolroom_app
cd toolroom_app
sudo ./install.sh
sudo reboot
```

The Pi will boot directly into the kiosk. No desktop, no login prompt — just the app fullscreen.

## What the installer does

1. Installs system packages (cage, cog, sqlite3, python3-venv)
2. Creates a dedicated `toolroom` user
3. Copies the app to `/home/toolroom/toolroom_app`
4. Sets up a Python virtual environment with Flask and Gunicorn
5. Initializes the SQLite database
6. Configures TTY1 auto-login and kiosk auto-start
7. Sets boot target to console (no desktop)

## Managing the Kiosk

All management is done via SSH.

| Action | Command |
|---|---|
| Stop kiosk | `sudo systemctl stop getty@tty1` |
| Restart kiosk | `sudo systemctl restart getty@tty1` |
| View status | `ps aux \| grep -E "cage\|cog\|gunicorn"` |
| Restore desktop | `sudo systemctl set-default graphical.target && sudo reboot` |
| Return to kiosk mode | `sudo systemctl set-default multi-user.target && sudo reboot` |

## Architecture

```
[Pi boots] -> TTY1 auto-login (toolroom) -> .bash_profile -> start.sh
  start.sh:
    1. Gunicorn (Flask app) on 127.0.0.1:5000
    2. cage (Wayland compositor) -> cog (WebKit browser) -> localhost:5000
    3. EXIT trap kills everything on shutdown
```

- **cage** — minimal Wayland kiosk compositor, owns the entire screen
- **cog** — WebKit-based browser, renders the Flask app
- **Gunicorn** — WSGI server running the Flask backend
- **nginx** (optional) — reverse proxy for HTTPS and remote access

## Network Access

The kiosk UI is also accessible from other devices on the network. With nginx configured:

- `https://<pi-ip>/` — requires HTTP Basic Auth
- Default login: **admin** / **change-me** — change this immediately in the User Manager
- Admin dashboard: `https://<pi-ip>/admin`
- User Manager: `https://<pi-ip>/admin/users` — add, edit, deactivate, or delete accounts

## Project Structure

```
├── app.py              # Flask application
├── install.sh          # One-command kiosk provisioner
├── start.sh            # Runtime launcher (gunicorn + cage/cog)
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   ├── index.html
│   ├── admin_dashboard.html
│   ├── admin_login.html
│   └── admin_users.html
├── static/             # CSS, JS, images
└── data/               # Created at runtime (gitignored)
    ├── inventory.db
    ├── app.log
    └── gunicorn.pid
```

## Development

To run on a Pi with Raspberry Pi OS desktop (without kiosk mode):

```bash
./install.sh            # Skip if deps already installed
./start.sh              # Ctrl+C to stop
```

Note: When running under the desktop, cage opens as a window. Use Ctrl+C in the terminal to shut down cleanly.
