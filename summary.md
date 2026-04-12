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

## Deployment / Runtime Changes
- **Installer Hardening (`install.sh`):**
  - Uses `python -m pip`/`ensurepip` path-safe flow.
  - Verifies Flask/Gunicorn availability after install.
- **Startup Hardening (`start.sh`):**
  - Uses `python -m gunicorn`.
  - Auto-heals venv/pip/dependencies when needed.
  - Binds backend to `127.0.0.1:5000` for reverse-proxy mode.
  - Includes aggressive stop/cleanup routines.

## HTTPS Status
- Local CA-based HTTPS setup has been completed on the Pi side (no Let's Encrypt).
- Nginx reverse proxy now fronts the app; direct `:5000` exposure is no longer required externally.

## Open Issue
- **Kiosk close behavior is still not fully deterministic:** closing with window `X` does not always terminate all backend processes; `Ctrl+C` reliably triggers cleanup.
- Current focus area: ensure cage/cog lifecycle reliably triggers backend shutdown without manual interrupt.
