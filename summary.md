# Toolroom Kiosk System - Project Summary

## Current Features
- **Scanner + Mouse Parity:** QR command tiles can be triggered by scanner or mouse/touch.
- **Hardened Scanner Burst Parsing:** Command/data bursts are normalized and handled via a central parser.
- **Qty Workflow Updates:**
  - Qty labels simplified to `Qty`.
  - Numpad moved to an overlay modal.
  - Overlay includes live Qty display and `CLEAR QTY` command.
  - Multi-digit qty scanning (e.g., `11`, `123`) works.
  - Manual Qty typing is synced to submission state.
- **Correction Simplification:** `REDO BADGE` and `REDO ITEM` act directly; separate `CORRECT FIELD` step removed.
- **Log Access Improvement:** Added a dedicated log overlay (`VIEW LOG`) with close controls and mouse wheel scroll support.

## Security / Admin
- **Admin Login + Dashboard Implemented:**
  - `/admin/login`, `/admin`, `/admin/logout`, `/admin/users` (stub).
  - Protected CSV export flow from admin dashboard.
- **User Manager Stub Added:** Backend-only placeholder page for future kiosk/admin account management.
- **HTTP Basic Auth Gate Added:** Port access challenge implemented with local kiosk bypass logic for reverse-proxy scenarios.

## Deployment / Runtime
- **One-command install:** `sudo ./install.sh` handles everything — system deps, Python venv, database init, `toolroom` user creation, TTY1 autologin, boot target, and kiosk auto-start.
- **Direct boot kiosk:** Pi boots to TTY1, auto-logs in as `toolroom`, `start.sh` launches cage+cog as the sole Wayland compositor. No desktop environment.
- **Clean shutdown:** `start.sh` uses a bash EXIT trap — when cage exits (power button, `systemctl stop getty@tty1`), gunicorn is killed automatically.
- **Gunicorn** binds to `127.0.0.1:5000` (localhost only, for reverse-proxy via nginx).
- **Management via SSH:**
  - Stop kiosk: `sudo systemctl stop getty@tty1`
  - Restart kiosk: `sudo systemctl restart getty@tty1`
  - Restore desktop: `sudo systemctl set-default graphical.target && sudo reboot`

## HTTPS Status
- Local CA-based HTTPS setup has been completed on the Pi side (no Let's Encrypt).
- Nginx reverse proxy now fronts the app; direct `:5000` exposure is no longer required externally.
